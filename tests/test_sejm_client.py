"""Testy jednostkowe asynchronicznego klienta SejmApiClient z użyciem respx i pytest."""

import pytest
import respx
from httpx import Response

from src.api_clients.sejm_client import (
    SejmApiClient,
    SejmApiError,
    SejmNotFoundError,
    SejmRateLimitError,
    SejmServerError,
)
from src.models.sejm_models import MPModel, VotingResultModel


@pytest.mark.anyio
async def test_get_mps_success() -> None:
    """Weryfikuje poprawne pobieranie i parsowanie listy posłów (HTTP 200)."""
    mock_payload = [
        {
            "id": 1,
            "firstLastName": "Jan Kowalski",
            "club": "KO",
            "active": True,
            "districtName": "Warszawa I",
        },
        {
            "id": 2,
            "firstLastName": "Anna Nowak",
            "club": "PiS",
            "active": True,
            "districtName": "Kraków II",
        },
    ]

    with respx.mock(base_url="https://api.sejm.gov.pl/sejm") as respx_mock:
        respx_mock.get("/term10/MP").mock(return_value=Response(200, json=mock_payload))

        async with SejmApiClient(term=10) as client:
            mps = await client.get_mps()

            assert len(mps) == 2
            assert isinstance(mps[0], MPModel)
            assert mps[0].id == 1
            assert mps[0].first_last_name == "Jan Kowalski"
            assert mps[0].club == "KO"
            assert mps[1].first_last_name == "Anna Nowak"


@pytest.mark.anyio
async def test_get_voting_results_success() -> None:
    """Weryfikuje pobieranie i walidację imiennych wyników głosowania (HTTP 200)."""
    mock_payload = {
        "term": 10,
        "sitting": 12,
        "votingNumber": 45,
        "date": "2024-03-15T16:30:00",
        "title": "Głosowanie nad projektem ustawy o świadczeniach rodzinnych",
        "topic": "I czytanie",
        "yes": 235,
        "no": 190,
        "abstain": 5,
        "votes": [
            {"MP": 1, "firstLastName": "Jan Kowalski", "club": "KO", "vote": "YES"},
            {"MP": 2, "firstLastName": "Anna Nowak", "club": "PiS", "vote": "NO"},
            {"MP": 3, "firstLastName": "Piotr Wiśniewski", "club": "TD", "vote": "ABSTAIN"},
        ],
    }

    with respx.mock(base_url="https://api.sejm.gov.pl/sejm") as respx_mock:
        respx_mock.get("/term10/votings/12/45").mock(return_value=Response(200, json=mock_payload))

        async with SejmApiClient(term=10) as client:
            result = await client.get_voting_results(sitting_num=12, voting_num=45)

            assert isinstance(result, VotingResultModel)
            assert result.sitting == 12
            assert result.voting_number == 45
            assert result.total_yes == 235
            assert len(result.votes) == 3
            assert result.votes[0].mp_id == 1
            assert result.votes[0].vote == "YES"


@pytest.mark.anyio
async def test_get_processes_with_pagination() -> None:
    """Weryfikuje pobieranie listy procesów z parametrami paginacji."""
    mock_processes = [
        {
            "number": "120",
            "term": 10,
            "title": "Projekt ustawy o zmianie podatków",
            "documentType": "PROJ_USTAWY",
            "changeDate": "2024-04-01T10:00:00",
            "prints": ["120", "120-A"],
        }
    ]

    with respx.mock(base_url="https://api.sejm.gov.pl/sejm") as respx_mock:
        route = respx_mock.get("/term10/processes").mock(
            return_value=Response(200, json=mock_processes)
        )

        async with SejmApiClient(term=10) as client:
            processes = await client.get_processes(offset=10, limit=20, since="2024-01-01")

            assert len(processes) == 1
            assert processes[0].number == "120"
            assert processes[0].prints == ["120", "120-A"]
            assert route.called
            assert "offset=10" in str(route.calls.last.request.url)
            assert "limit=20" in str(route.calls.last.request.url)


@pytest.mark.anyio
async def test_http_404_raises_not_found_error() -> None:
    """Weryfikuje, czy błąd HTTP 404 skutkuje rzuceniem SejmNotFoundError (podklasy SejmApiError)."""
    with respx.mock(base_url="https://api.sejm.gov.pl/sejm") as respx_mock:
        respx_mock.get("/term10/prints/99999").mock(
            return_value=Response(404, text="Print not found")
        )

        async with SejmApiClient(term=10) as client:
            with pytest.raises(SejmNotFoundError) as exc_info:
                await client.get_print_details(print_id="99999")

            assert isinstance(exc_info.value, SejmApiError)
            assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_http_500_raises_server_error() -> None:
    """Weryfikuje, czy błąd serwera HTTP 500 skutkuje rzuceniem SejmServerError."""
    with respx.mock(base_url="https://api.sejm.gov.pl/sejm") as respx_mock:
        respx_mock.get("/term10/MP").mock(return_value=Response(500, text="Internal Server Error"))

        async with SejmApiClient(term=10) as client:
            with pytest.raises(SejmServerError) as exc_info:
                await client.get_mps()

            assert isinstance(exc_info.value, SejmApiError)
            assert exc_info.value.status_code == 500


@pytest.mark.anyio
async def test_http_429_rate_limiting_retries_three_times() -> None:
    """Weryfikuje, czy dekorator tenacity ponawia żądanie co najmniej 3 razy przy HTTP 429."""
    with respx.mock(base_url="https://api.sejm.gov.pl/sejm") as respx_mock:
        route = respx_mock.get("/term10/MP").mock(
            return_value=Response(429, text="Too Many Requests")
        )

        async with SejmApiClient(term=10) as client:
            with pytest.raises(SejmRateLimitError) as exc_info:
                await client.get_mps()

            # Sprawdzenie czy wykonano dokładnie 3 próby zdefiniowane w tenacity stop_after_attempt(3)
            assert route.call_count == 3
            assert isinstance(exc_info.value, SejmApiError)
            assert exc_info.value.status_code == 429


@pytest.mark.anyio
async def test_circuit_breaker_opens_after_consecutive_failures() -> None:
    """Weryfikuje, czy po serii błędów wyłącznik Circuit Breaker odcina kolejne zapytania."""
    from src.api_clients.sejm_client import CircuitBreakerOpenError

    with respx.mock(base_url="https://api.sejm.gov.pl/sejm") as respx_mock:
        respx_mock.get("/term10/MP").mock(return_value=Response(503, text="Service Unavailable"))

        async with SejmApiClient(term=10) as client:
            client.circuit_breaker.failure_threshold = 2

            # 1. Błąd serwera (zostanie zarejestrowany przez CB)
            with pytest.raises(SejmServerError):
                await client.get_mps()

            # 2. Drugi błąd serwera
            with pytest.raises(SejmServerError):
                await client.get_mps()

            assert client.circuit_breaker.state == "OPEN"

            # 3. Kolejne wywołanie powinno zostać natychmiast zablokowane przez Circuit Breaker
            with pytest.raises(CircuitBreakerOpenError) as exc_info:
                await client.get_mps()

            assert "otwarty" in str(exc_info.value)
