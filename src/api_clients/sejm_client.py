"""Klient asynchroniczny do komunikacji z oficjalnym Sejm OpenAPI (api.sejm.gov.pl).

Zapewnia odporność na awarie sieciowe, limity zapytań (HTTP 429) z wykorzystaniem
biblioteki Tenacity (Exponential Backoff) oraz ścisłą walidację schematów Pydantic v2.
"""

from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.models.sejm_models import (
    InterpellationModel,
    MPModel,
    PrintDetailModel,
    ProcessModel,
    VotingResultModel,
)


class SejmApiError(Exception):
    """Bazowy wyjątek dla błędów komunikacji z API Sejmu."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class SejmNotFoundError(SejmApiError):
    """Zasób nie został odnaleziony w API Sejmu (HTTP 404)."""


class SejmServerError(SejmApiError):
    """Błąd wewnętrzny serwerów Kancelarii Sejmu (HTTP 5xx)."""


class SejmRateLimitError(SejmApiError):
    """Przekroczono limit dopuszczalnych zapytań (HTTP 429 Too Many Requests)."""


class SejmApiClient:
    """Klient HTTP do asynchronicznego pobierania danych z Sejm OpenAPI."""

    DEFAULT_BASE_URL: str = "https://api.sejm.gov.pl/sejm"

    def __init__(
        self,
        term: int = 10,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 15.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Inicjalizuje klienta Sejm OpenAPI.

        Args:
            term: Numer kadencji Sejmu (domyślnie 10 dla obecnej kadencji).
            base_url: Bazowy URL do API Sejmu.
            timeout: Dopuszczalny czas oczekiwania na odpowiedź w sekundach.
            client: Opcjonalna zewnętrzna instancja httpx.AsyncClient (np. do testów).
        """
        self.term = term
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._external_client = client is not None
        self._client = client or httpx.AsyncClient(
            headers={
                "User-Agent": "WeryfikatorObietnic/1.0 (+https://github.com/FranekJemiolo/weryfikatorobietnic)",
                "Accept": "application/json",
            },
            timeout=self.timeout,
        )

    async def close(self) -> None:
        """Zamyka wewnętrznego klienta HTTP, o ile nie został przekazany z zewnątrz."""
        if not self._external_client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> "SejmApiClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    @retry(
        retry=retry_if_exception_type((SejmRateLimitError, httpx.RequestError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.02, min=0.02, max=0.2),
        reraise=True,
    )
    async def _request(
        self, method: str, endpoint: str, params: dict[str, Any] | None = None
    ) -> Any:
        """Wykonuje żądanie HTTP z automatycznym ponawianiem (Exponential Backoff dla HTTP 429)."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = await self._client.request(method, url, params=params)
        except httpx.RequestError as exc:
            raise SejmApiError(f"Błąd sieciowy podczas łączenia z {url}: {exc}") from exc

        if response.status_code == 429:
            raise SejmRateLimitError(
                "Przekroczono limit zapytań do Sejm OpenAPI (HTTP 429).", status_code=429
            )

        if response.status_code == 404:
            raise SejmNotFoundError(
                f"Nie odnaleziono zasobu w Sejm API (HTTP 404): {url}", status_code=404
            )

        if response.status_code >= 500:
            raise SejmServerError(
                f"Serwery Sejmu zwróciły błąd wewnętrzny (HTTP {response.status_code}): {response.text}",
                status_code=response.status_code,
            )

        if response.status_code >= 400:
            raise SejmApiError(
                f"Błąd zapytania Sejm API (HTTP {response.status_code}): {response.text}",
                status_code=response.status_code,
            )

        return response.json()

    async def get_mps(self) -> list[MPModel]:
        """Pobiera listę wszystkich posłów obecnej kadencji wraz z ich klubami parlamentarnymi.

        Endpoint: GET /sejm/term{term}/MP
        """
        data = await self._request("GET", f"/term{self.term}/MP")
        if not isinstance(data, list):
            raise SejmApiError(
                "Nieprawidłowy format odpowiedzi z listy posłów - oczekiwano tablicy JSON."
            )

        return [MPModel.model_validate(item) for item in data]

    async def get_processes(
        self,
        offset: int = 0,
        limit: int = 50,
        since: str | None = None,
    ) -> list[ProcessModel]:
        """Pobiera procesy legislacyjne (projekty ustaw i uchwał) z obsługą paginacji i daty.

        Endpoint: GET /sejm/term{term}/processes
        """
        params: dict[str, Any] = {
            "offset": offset,
            "limit": limit,
        }
        if since:
            params["since"] = since

        data = await self._request("GET", f"/term{self.term}/processes", params=params)
        if not isinstance(data, list):
            raise SejmApiError(
                "Nieprawidłowy format procesów legislacyjnych - oczekiwano tablicy JSON."
            )

        return [ProcessModel.model_validate(item) for item in data]

    async def get_print_details(self, print_id: str | int) -> PrintDetailModel:
        """Pobiera szczegółowe metadane i załączniki pojedynczego druku sejmowego.

        Endpoint: GET /sejm/term{term}/prints/{print_id}
        """
        data = await self._request("GET", f"/term{self.term}/prints/{print_id}")
        return PrintDetailModel.model_validate(data)

    async def get_voting_results(self, sitting_num: int, voting_num: int) -> VotingResultModel:
        """Pobiera szczegółowy, imienny wynik wskazanego głosowania plenarnego.

        Endpoint: GET /sejm/term{term}/votings/{sitting_num}/{voting_num}
        """
        data = await self._request("GET", f"/term{self.term}/votings/{sitting_num}/{voting_num}")
        return VotingResultModel.model_validate(data)

    async def get_interpellations(
        self,
        offset: int = 0,
        limit: int = 50,
        from_mp: int | None = None,
        since: str | None = None,
        modified_since: str | None = None,
    ) -> list[InterpellationModel]:
        """Pobiera interpelacje poselskie obecnej kadencji Sejmu (np. /sejm/term10/interpellations).

        Endpoint: GET /sejm/term{term}/interpellations
        """
        params: dict[str, Any] = {
            "offset": offset,
            "limit": limit,
        }
        if from_mp is not None:
            params["from"] = from_mp
        if since:
            params["since"] = since
        if modified_since:
            params["modifiedSince"] = modified_since

        data = await self._request("GET", f"/term{self.term}/interpellations", params=params)
        if not isinstance(data, list):
            raise SejmApiError(
                "Nieprawidłowy format interpelacji poselskich - oczekiwano tablicy JSON."
            )

        return [InterpellationModel.model_validate(item) for item in data]
