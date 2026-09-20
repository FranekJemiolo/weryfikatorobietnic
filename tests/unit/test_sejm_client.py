"""Testy jednostkowe klienta Sejm OpenAPI."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.collectors.sejm_api import SejmAPIError, SejmClient


def test_sejm_client_init() -> None:
    """Weryfikuje poprawną inicjalizację klienta."""
    client = SejmClient(base_url="https://api.sejm.gov.pl/sejm/", timeout=15, term=10)
    assert client._base_url == "https://api.sejm.gov.pl/sejm"
    assert client._timeout == 15
    assert client._term == 10
    assert "User-Agent" in client._session.headers


@patch.object(requests.Session, "get")
def test_get_legislative_processes_success(mock_get: MagicMock) -> None:
    """Sprawdza pomyślne pobieranie procesów legislacyjnych."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"number": 1, "title": "Projekt ustawy o zmianie podatku", "documentType": "USTAWA"},
        {"number": 2, "title": "Projekt uchwały Sejmu", "documentType": "UCHWAŁA"},
    ]
    mock_get.return_value = mock_response

    client = SejmClient()
    processes = client.get_legislative_processes(offset=0, limit=10)

    assert len(processes) == 2
    assert processes[0]["number"] == 1
    mock_get.assert_called_once_with(
        "https://api.sejm.gov.pl/sejm/term10/processes",
        params={"offset": 0, "limit": 10},
        timeout=client._timeout,
    )


@patch.object(requests.Session, "get")
def test_get_legislative_processes_error(mock_get: MagicMock) -> None:
    """Sprawdza obsługę błędu sieciowego przy zapytaniu do API."""
    mock_get.side_effect = requests.RequestException("Connection timeout")

    client = SejmClient()
    with pytest.raises(SejmAPIError) as exc_info:
        client.get_legislative_processes()

    assert "Błąd podczas odpytywania Sejm API" in str(exc_info.value)
