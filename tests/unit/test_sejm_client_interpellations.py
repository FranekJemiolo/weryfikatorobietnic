"""Testy jednostkowe asynchronicznego klienta SejmApiClient w zakresie interpelacji poselskich."""

import pytest
import respx

from src.api_clients.sejm_client import SejmApiClient, SejmApiError


@pytest.mark.anyio
async def test_get_interpellations_success() -> None:
    """Weryfikuje pobieranie i walidację listy interpelacji poselskich z Sejm API."""
    mock_interpellations = [
        {
            "term": 10,
            "num": 1420,
            "title": "Interpelacja w sprawie finansowania szpitali powiatowych",
            "receiptDate": "2024-03-01",
            "lastModified": "2024-03-15",
            "from": [101, 102],
            "to": ["Minister Zdrowia"],
            "sentDate": "2024-03-02",
            "replies": [
                {
                    "key": "ODP-1",
                    "receiptDate": "2024-03-14",
                    "from": "Podsekretarz Stanu",
                }
            ],
        },
        {
            "term": 10,
            "num": 1421,
            "title": "Interpelacja w sprawie budowy obwodnicy miejscowości",
            "receiptDate": "2024-03-05",
            "from": [205],
            "to": ["Minister Infrastruktury"],
            "replies": [],
        },
    ]

    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get("https://api.sejm.gov.pl/sejm/term10/interpellations").respond(
            status_code=200, json=mock_interpellations
        )

        client = SejmApiClient(term=10)
        interpellations = await client.get_interpellations()
        await client.close()

        assert len(interpellations) == 2
        assert interpellations[0].num == 1420
        assert interpellations[0].receipt_date == "2024-03-01"
        assert interpellations[0].from_mp == [101, 102]
        assert interpellations[0].is_answered is True

        assert interpellations[1].num == 1421
        assert interpellations[1].is_answered is False


@pytest.mark.anyio
async def test_get_interpellations_invalid_format() -> None:
    """Weryfikuje rzucenie SejmApiError w przypadku nieprawidłowego formatu odpowiedzi (np. słownik zamiast listy)."""
    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get("https://api.sejm.gov.pl/sejm/term10/interpellations").respond(
            status_code=200, json={"error": "Not a list"}
        )

        client = SejmApiClient(term=10)
        with pytest.raises(SejmApiError, match="Nieprawidłowy format interpelacji poselskich"):
            await client.get_interpellations()
        await client.close()
