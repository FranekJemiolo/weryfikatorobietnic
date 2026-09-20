"""Klient HTTP do Internetowego Systemu Aktów Prawnych (ISAP / ELI API Kancelarii Sejmu).

Odpowiada za weryfikację publikacji uchwalonych ustaw w Dzienniku Ustaw (WDU)
oraz potwierdzanie, czy dany akt prawny faktycznie wszedł w życie ('PRAWO OBOWIĄZUJĄCE').
"""

import logging
import re
from datetime import UTC, datetime
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger("ISAPClient")


class ISAPClient:
    """Klient API do bazy aktów prawnych ISAP / ELI (api.sejm.gov.pl/eli)."""

    DEFAULT_BASE_URL: str = "https://api.sejm.gov.pl/eli"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 15.0,
        client: httpx.Client | None = None,
    ) -> None:
        """Inicjalizuje klienta ISAP ELI.

        Args:
            base_url: Bazowy adres API ELI Sejmu.
            timeout: Maksymalny czas oczekiwania na odpowiedź w sekundach.
            client: Opcjonalna zewnętrzna instancja httpx.Client (np. do mockowania w testach).
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._external_client = client is not None
        self._client = client or httpx.Client(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; WeryfikatorObietnicISAPBot/1.0; "
                    "+https://github.com/FranekJemiolo/weryfikatorobietnic)"
                ),
                "Accept": "application/json",
            },
            timeout=self.timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        """Zamyka klienta HTTP."""
        if not self._external_client and not self._client.is_closed:
            self._client.close()

    def __enter__(self) -> "ISAPClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    @retry(
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=1.0, max=5.0),
        reraise=False,
    )
    def get_act_details(self, publisher: str, year: int, position: int) -> dict[str, Any] | None:
        """Pobiera metadane konkretnego aktu prawnego po identyfikatorze Dziennika Ustaw.

        Endpoint: GET /eli/acts/{publisher}/{year}/{position}
        Przykład: /eli/acts/WDU/2024/123
        """
        url = f"{self.base_url}/acts/{publisher.upper()}/{year}/{position}"
        try:
            response = self._client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]
        except Exception as exc:
            logger.warning("Błąd zapytania o akt ISAP %s: %s", url, exc)
            return None

    def search_acts_by_title(
        self, title_phrase: str, year: int | None = None
    ) -> list[dict[str, Any]]:
        """Wyszukuje akty prawne w ISAP po słowach kluczowych w tytule."""
        url = f"{self.base_url}/acts/search"
        clean_title = re.sub(r"[^\w\s]", "", title_phrase).strip()
        params: dict[str, Any] = {"title": clean_title[:80]}
        if year:
            params["year"] = year

        try:
            response = self._client.get(url, params=params)
            if response.status_code == 404:
                return []
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and "items" in data:
                return list(data["items"])
            return list(data) if isinstance(data, list) else []
        except Exception as exc:
            logger.warning("Błąd wyszukiwania aktu w ISAP po tytule '%s': %s", title_phrase, exc)
            return []

    def check_bill_in_force(
        self,
        bill_title: str,
        year: int | None = None,
        isap_publication_id: str | None = None,
    ) -> tuple[bool, str | None, datetime | None]:
        """Sprawdza, czy ustawa została ogłoszona w Dzienniku Ustaw i weszła w życie.

        Returns:
            Krotka: (is_in_force, publication_id, entry_into_force_date)
        """
        now = datetime.now(UTC)

        # 1. Jeśli znamy już konkretny identyfikator publikacji (np. 'WDU/2024/543' lub 'DU/2024/543')
        if isap_publication_id:
            raw_parts = [p.strip() for p in isap_publication_id.split("/") if p.strip()]
            if len(raw_parts) == 3 and raw_parts[1].isdigit() and raw_parts[2].isdigit():
                pub = raw_parts[0].upper()
                if pub == "DU":
                    pub = "WDU"
                act = self.get_act_details(
                    publisher=pub,
                    year=int(raw_parts[1]),
                    position=int(raw_parts[2]),
                )
                if act:
                    status_text = str(act.get("status", "")).lower()
                    force_date_str = act.get("entryIntoForceDate")
                    force_date = None
                    if force_date_str:
                        try:
                            force_date = datetime.fromisoformat(force_date_str).replace(tzinfo=UTC)
                        except Exception:
                            pass

                    # Akt obowiązujący, jeśli ma status 'obowiązujący' lub data wejścia w życie minęła
                    in_force = "obowiązuj" in status_text or (
                        force_date is not None and force_date <= now
                    )
                    return in_force, isap_publication_id, force_date

        # 2. Wyszukanie po tytule projektu w Dzienniku Ustaw
        search_results = self.search_acts_by_title(bill_title, year=year)
        for act_summary in search_results:
            status_text = str(act_summary.get("status", "")).lower()
            pub_id = (
                f"{act_summary.get('publisher', 'WDU')}/"
                f"{act_summary.get('year')}/"
                f"{act_summary.get('pos')}"
            )
            force_date_str = act_summary.get("entryIntoForceDate")
            force_date = None
            if force_date_str:
                try:
                    force_date = datetime.fromisoformat(force_date_str).replace(tzinfo=UTC)
                except Exception:
                    pass

            in_force = "obowiązuj" in status_text or (force_date is not None and force_date <= now)
            if in_force:
                return True, pub_id, force_date or now

        return False, None, None
