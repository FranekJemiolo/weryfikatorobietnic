"""Klient HTTP do oficjalnego interfejsu Sejm OpenAPI (api.sejm.gov.pl).

Odpowiada za pobieranie procesów legislacyjnych, druków, posiedzeń oraz imiennych wyników głosowań.
"""

from typing import Any

import requests

from src.config import settings


class SejmAPIError(Exception):
    """Bazowy wyjątek dla błędów komunikacji z Sejm OpenAPI."""


class SejmClient:
    """Klient pobierający dane z publicznego API Sejmu RP."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int | None = None,
        term: int | None = None,
    ) -> None:
        """Inicjalizuje klienta Sejm OpenAPI.

        Args:
            base_url: Opcjonalny bazowy URL API; domyślnie z konfiguracji.
            timeout: Maksymalny czas oczekiwania na odpowiedź w sekundach.
            term: Numer kadencji Sejmu (domyślnie 10).
        """
        self._base_url = (base_url or settings.sejm_api_base_url).rstrip("/")
        self._timeout = timeout or settings.request_timeout_seconds
        self._term = term or settings.default_sejm_term
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": settings.user_agent,
                "Accept": "application/json",
            }
        )

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """Wykonuje bezpieczne zapytanie GET do API Sejmu.

        Args:
            endpoint: Ścieżka relatywna endpointu.
            params: Opcjonalne parametry query string.

        Returns:
            Any: Sparsowana odpowiedź JSON (słownik lub lista).

        Raises:
            SejmAPIError: W przypadku błędu sieciowego lub statusu HTTP != 200.
        """
        url = f"{self._base_url}/{endpoint.lstrip('/')}"
        try:
            response = self._session.get(url, params=params, timeout=self._timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as err:
            raise SejmAPIError(f"Błąd podczas odpytywania Sejm API ({url}): {err}") from err

    def get_legislative_processes(
        self,
        offset: int = 0,
        limit: int = 50,
        term: int | None = None,
    ) -> list[dict[str, Any]]:
        """Pobiera listę procesów legislacyjnych dla danej kadencji.

        Args:
            offset: Indeks początkowy stronicowania.
            limit: Liczba rekordów do pobrania.
            term: Opcjonalna kadencja Sejmu (domyślnie self._term).

        Returns:
            list[dict[str, Any]]: Lista procesów legislacyjnych.
        """
        actual_term = term or self._term
        endpoint = f"term{actual_term}/processes"
        params = {"offset": offset, "limit": limit}
        result = self._get(endpoint, params=params)
        return list(result) if isinstance(result, list) else []

    def get_process_details(self, process_id: str, term: int | None = None) -> dict[str, Any]:
        """Pobiera pełne szczegóły pojedynczego procesu legislacyjnego.

        Args:
            process_id: Numer lub identyfikator procesu (np. '1-2023').
            term: Opcjonalna kadencja Sejmu.

        Returns:
            dict[str, Any]: Słownik ze szczegółami procesu.
        """
        actual_term = term or self._term
        endpoint = f"term{actual_term}/processes/{process_id}"
        result = self._get(endpoint)
        return dict(result) if isinstance(result, dict) else {}

    def get_prints(
        self,
        offset: int = 0,
        limit: int = 50,
        term: int | None = None,
    ) -> list[dict[str, Any]]:
        """Pobiera listę druków sejmowych.

        Args:
            offset: Indeks początkowy.
            limit: Maksymalna liczba druków.
            term: Kadencja Sejmu.

        Returns:
            list[dict[str, Any]]: Lista obiektów druków sejmowych.
        """
        actual_term = term or self._term
        endpoint = f"term{actual_term}/prints"
        params = {"offset": offset, "limit": limit}
        result = self._get(endpoint, params=params)
        return list(result) if isinstance(result, list) else []

    def get_voting_details(
        self,
        sitting: int,
        voting_number: int,
        term: int | None = None,
    ) -> dict[str, Any]:
        """Pobiera imienne wyniki głosowania dla danego posiedzenia i numeru głosowania.

        Args:
            sitting: Numer posiedzenia Sejmu.
            voting_number: Numer kolejny głosowania na danym posiedzeniu.
            term: Kadencja Sejmu.

        Returns:
            dict[str, Any]: Szczegóły głosowania wraz z głosami imiennymi każdego posła.
        """
        actual_term = term or self._term
        endpoint = f"term{actual_term}/votings/{sitting}/{voting_number}"
        result = self._get(endpoint)
        return dict(result) if isinstance(result, dict) else {}

    def get_members_of_parliament(self, term: int | None = None) -> list[dict[str, Any]]:
        """Pobiera listę posłów na Sejm RP w wybranej kadencji.

        Args:
            term: Kadencja Sejmu.

        Returns:
            list[dict[str, Any]]: Lista posłów z ich przynależnością klubową.
        """
        actual_term = term or self._term
        endpoint = f"term{actual_term}/MP"
        result = self._get(endpoint)
        return list(result) if isinstance(result, list) else []
