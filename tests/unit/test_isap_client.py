"""Testy jednostkowe klienta Internetowego Systemu Aktów Prawnych (ISAPClient)."""

import respx

from src.api_clients.isap_client import ISAPClient


def test_isap_client_get_act_details_success() -> None:
    """Weryfikuje pobieranie szczegółów aktu prawnego po identyfikatorze Dziennika Ustaw."""
    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get("https://api.sejm.gov.pl/eli/acts/WDU/2024/123").respond(
            status_code=200,
            json={
                "publisher": "WDU",
                "year": 2024,
                "pos": 123,
                "title": "Ustawa o wsparciu przedsiębiorców",
                "status": "obowiązujący",
                "entryIntoForceDate": "2024-03-01",
            },
        )

        client = ISAPClient()
        act = client.get_act_details("WDU", 2024, 123)

        assert act is not None
        assert act["year"] == 2024
        assert act["pos"] == 123
        assert act["status"] == "obowiązujący"


def test_isap_client_get_act_details_404() -> None:
    """Weryfikuje obsługę nieznalezionego aktu prawnego w ISAP."""
    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get("https://api.sejm.gov.pl/eli/acts/WDU/2024/99999").respond(status_code=404)

        client = ISAPClient()
        act = client.get_act_details("WDU", 2024, 99999)
        assert act is None


def test_isap_client_check_bill_in_force_with_publication_id() -> None:
    """Weryfikuje potwierdzenie wejścia ustawy w życie na podstawie znanego identyfikatora publikacji."""
    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get("https://api.sejm.gov.pl/eli/acts/WDU/2024/456").respond(
            status_code=200,
            json={
                "publisher": "WDU",
                "year": 2024,
                "pos": 456,
                "status": "akt posiada tekst jednolity",
                "entryIntoForceDate": "2024-01-01",
            },
        )

        client = ISAPClient()
        in_force, pub_id, force_date = client.check_bill_in_force(
            bill_title="Dowolny tytuł",
            isap_publication_id="WDU/2024/456",
        )

        assert in_force is True
        assert pub_id == "WDU/2024/456"
        assert force_date is not None
        assert force_date.year == 2024


def test_isap_client_check_bill_not_in_force() -> None:
    """Weryfikuje sytuację, gdy projekt nie został jeszcze opublikowany w ISAP."""
    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get("https://api.sejm.gov.pl/eli/acts/search").respond(
            status_code=200,
            json={"items": []},
        )

        client = ISAPClient()
        in_force, pub_id, force_date = client.check_bill_in_force(
            bill_title="Projekt nieistniejący",
            year=2024,
        )

        assert in_force is False
        assert pub_id is None
        assert force_date is None
