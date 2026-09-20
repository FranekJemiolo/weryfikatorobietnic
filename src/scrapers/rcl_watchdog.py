"""Moduł RCLWatchdog: Scraper Rządowego Centrum Legislacji (legislacja.gov.pl).

Śledzi wczesne etapy procesu prawodawczego (pre-legislację), w tym:
- Uzgodnienia międzyresortowe
- Konsultacje publiczne
- Opiniowanie
Zapisuje wykryte projekty w tabeli `pre_legislative_processes`, umożliwiając
mierzenie pełnego wskaźnika Time-to-Delivery od pomysłu w ministerstwie do ogłoszenia w Dz.U.
"""

import logging
import re
from datetime import UTC, datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup
from sqlmodel import Session
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.database.models import PreLegislativeProcess

logger = logging.getLogger("RCLWatchdog")
logging.basicConfig(level=logging.INFO)

TARGET_STAGES = ["Uzgodnienia", "Konsultacje publiczne", "Opiniowanie"]


class RCLWatchdog:
    """Monitor i scraper Rządowego Centrum Legislacji (legislacja.gov.pl)."""

    DEFAULT_BASE_URL = "https://legislacja.gov.pl"
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; WeryfikatorObietnicRCLBot/1.0; "
            "+https://github.com/FranekJemiolo/weryfikatorobietnic)"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pl,en-US;q=0.7,en;q=0.3",
    }

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 20.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._external_client = client is not None
        self._client = client or httpx.Client(
            headers=self.DEFAULT_HEADERS,
            timeout=self.timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        """Zamyka klienta HTTP."""
        if not self._external_client and not self._client.is_closed:
            self._client.close()

    def __enter__(self) -> "RCLWatchdog":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    @retry(
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=1.0, max=5.0),
        reraise=False,
    )
    def fetch_page(self, url_path: str = "/katalog/projekty-ustaw") -> str:
        """Pobiera kod HTML strony z katalogu projektów RCL z automatycznym ponawianiem."""
        url = f"{self.base_url}{url_path}" if url_path.startswith("/") else url_path
        try:
            response = self._client.get(url)
            response.raise_for_status()
            return response.text
        except Exception as exc:
            logger.warning("Błąd podczas pobierania strony RCL %s: %s", url, exc)
            return ""

    def parse_projects_from_html(
        self,
        html_content: str,
        target_stages: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Parsuje strukturę HTML portalu legislacja.gov.pl i wyciąga dane projektów pre-legislacyjnych.

        Obsługuje zarówno strukturę tabelaryczną (tabela projektów), jak i widok kafelkowy.
        Filtruje projekty według zadanych etapów (domyślnie: Uzgodnienia, Konsultacje publiczne, Opiniowanie).
        """
        if not html_content:
            return []

        active_stages = sorted(target_stages or TARGET_STAGES, key=len, reverse=True)
        soup = BeautifulSoup(html_content, "html.parser")
        projects: list[dict[str, Any]] = []

        # 1. Przeszukiwanie wierszy tabelarycznych (najczęstszy układ na legislacja.gov.pl)
        table_rows = soup.select("table.table tr, table tbody tr, .project-row, .katalog-row")
        for row in table_rows:
            text_cells = [td.get_text(strip=True) for td in row.select("td, th")]
            if len(text_cells) < 3:
                continue

            full_row_text = " ".join(text_cells)

            # Wykrycie etapu
            matched_stage: str | None = None
            for stage in active_stages:
                if stage.lower() in full_row_text.lower():
                    matched_stage = stage
                    break

            if not matched_stage:
                continue

            # Identyfikator RCL (np. UD123, UC45, RD89, UA1)
            id_match = re.search(r"\b([A-Z]{1,3}\d{1,5})\b", full_row_text)
            rcl_id = id_match.group(1) if id_match else None

            # Link do projektu
            link_tag = row.select_one("a[href]")
            project_url: str | None = None
            if link_tag and link_tag.get("href"):
                raw_href = str(link_tag["href"])
                project_url = f"{self.base_url}{raw_href}" if raw_href.startswith("/") else raw_href

            title = link_tag.get_text(strip=True) if link_tag else text_cells[1]
            if not rcl_id:
                # Jeśli w tekście brak kodu UD/UC, spróbuj wyciągnąć z linku lub tytułu
                url_id_match = re.search(r"/(\d+)(?:[/?]|$)", project_url or "")
                rcl_id = (
                    f"RCL-{url_id_match.group(1)}"
                    if url_id_match
                    else f"RCL-{abs(hash(title)) % 100000}"
                )

            # Instytucja / organ odpowiedzialny
            institution = None
            for cell in text_cells:
                if any(kw in cell.lower() for kw in ["minister", "urząd", "kancelaria", "komitet"]):
                    institution = cell
                    break

            # Data utworzenia/zgłoszenia
            date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", full_row_text)
            created_date = None
            if date_match:
                try:
                    created_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").replace(
                        tzinfo=UTC
                    )
                except ValueError:
                    pass

            projects.append(
                {
                    "id": rcl_id,
                    "rcl_id": rcl_id,
                    "title": title,
                    "stage": matched_stage,
                    "institution": institution,
                    "created_date": created_date or datetime.now(UTC),
                    "url": project_url,
                }
            )

        # 2. Przeszukiwanie kart/boksów (fallback dla wersji mobilnej lub kafli)
        if not projects:
            cards = soup.select(".card, .project-card, .list-item, .element-katalogu")
            for card in cards:
                card_text = card.get_text(" ", strip=True)
                matched_stage = None
                for stage in active_stages:
                    if stage.lower() in card_text.lower():
                        matched_stage = stage
                        break

                if not matched_stage:
                    continue

                id_match = re.search(r"\b([A-Z]{1,3}\d{1,5})\b", card_text)
                title_tag = card.select_one("h2, h3, h4, .title, a")
                title = title_tag.get_text(strip=True) if title_tag else card_text[:100]
                card_link = card.select_one("a[href]")
                card_raw_href = (
                    str(card_link["href"]) if card_link and card_link.get("href") else None
                )
                card_url = (
                    f"{self.base_url}{card_raw_href}"
                    if card_raw_href and card_raw_href.startswith("/")
                    else card_raw_href
                )

                rcl_id = id_match.group(1) if id_match else f"RCL-{abs(hash(title)) % 100000}"
                projects.append(
                    {
                        "id": rcl_id,
                        "rcl_id": rcl_id,
                        "title": title,
                        "stage": matched_stage,
                        "institution": None,
                        "created_date": datetime.now(UTC),
                        "url": card_url,
                    }
                )

        return projects

    def sync_with_database(self, session: Session, projects: list[dict[str, Any]]) -> int:
        """Zapisuje wyekstrahowane projekty RCL w tabeli `pre_legislative_processes` w sposób idempotentny.

        Args:
            session: Aktywna sesja bazy danych.
            projects: Lista słowników projektów z metody `parse_projects_from_html`.

        Returns:
            Liczba zaktualizowanych lub wstawionych projektów.
        """
        if not projects:
            return 0

        synced_count = 0
        for p_data in projects:
            existing = session.get(PreLegislativeProcess, p_data["id"])
            if existing:
                # Aktualizacja etapu i daty
                existing.stage = p_data["stage"]
                existing.updated_date = datetime.now(UTC)
                if p_data.get("url"):
                    existing.url = p_data["url"]
                session.add(existing)
            else:
                new_item = PreLegislativeProcess(
                    id=p_data["id"],
                    rcl_id=p_data["rcl_id"],
                    title=p_data["title"],
                    stage=p_data["stage"],
                    institution=p_data.get("institution"),
                    created_date=p_data.get("created_date") or datetime.now(UTC),
                    url=p_data.get("url"),
                )
                session.add(new_item)
            synced_count += 1

        session.commit()
        return synced_count
