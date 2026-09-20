"""Testy jednostkowe kolektora kanałów informacyjnych RSS/Atom (RSSCollector)."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock

import httpx
import pytest
import respx
from sqlmodel import Session, create_engine, select

from src.collectors.rss_collector import RSSCollector, RSSFeedItemData
from src.database.engine import init_db
from src.database.models import RSSFeedItem

SAMPLE_RSS_20 = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
  <title>Komunikaty KPRM</title>
  <link>https://www.gov.pl/web/premier</link>
  <description>Oficjalne komunikaty Centrum Informacyjnego Rządu</description>
  <item>
    <title>Rząd przyjął projekt ustawy o wsparciu przedsiębiorców</title>
    <link>https://www.gov.pl/web/premier/projekt-wsparcie-przedsiebiorcow</link>
    <description><![CDATA[<p>Rada Ministrów przyjęła dzisiaj kluczowy <b>projekt ustawy</b> wspierający MŚP.</p>]]></description>
    <pubDate>Mon, 20 Sep 2026 14:00:00 GMT</pubDate>
    <guid>https://www.gov.pl/web/premier/projekt-wsparcie-przedsiebiorcow</guid>
  </item>
  <item>
    <title>Premier zapowiada realizację kolejnych deklaracji</title>
    <link>https://www.gov.pl/web/premier/deklaracje-gospodarcze</link>
    <description>Podsumowanie prac rządu i planowane ustawy.</description>
    <pubDate>Sun, 19 Sep 2026 10:30:00 GMT</pubDate>
    <guid>https://www.gov.pl/web/premier/deklaracje-gospodarcze</guid>
  </item>
</channel>
</rss>
"""

SAMPLE_ATOM_10 = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Aktualności Partii Razem</title>
  <link href="https://partiarazem.pl/feed" rel="self"/>
  <updated>2026-09-20T12:00:00Z</updated>
  <id>https://partiarazem.pl/</id>
  <entry>
    <title>Razem przedstawia projekt o skróconym czasie pracy</title>
    <link href="https://partiarazem.pl/aktualnosci/skrocony-czas-pracy"/>
    <id>urn:uuid:1225c695-cfb8-4ebb-aaaa-80da344efa6a</id>
    <updated>2026-09-20T11:00:00Z</updated>
    <summary type="html">Klub parlamentarny składa postulat 35-godzinnego tygodnia pracy.</summary>
  </entry>
</feed>
"""


@pytest.fixture(name="db_session")
def db_session_fixture() -> Generator[Session, None, None]:
    """Tworzy czystą sesję SQLite w pamięci do testów zapisu RSS."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    init_db(engine)
    with Session(engine) as session:
        yield session


def test_rss_collector_parse_rss_20() -> None:
    """Weryfikuje poprawne pobieranie i parsowanie kanału w formacie RSS 2.0."""
    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get("https://example.gov.pl/rss").respond(
            status_code=200,
            text=SAMPLE_RSS_20,
            headers={"Content-Type": "application/rss+xml"},
        )

        collector = RSSCollector(timeout=5.0)
        items = collector.fetch_feed(
            url="https://example.gov.pl/rss",
            source_name="KPRM Komunikaty",
            category="GOVERNMENT",
        )

        assert len(items) == 2
        first = items[0]
        assert first.title == "Rząd przyjął projekt ustawy o wsparciu przedsiębiorców"
        assert first.link == "https://www.gov.pl/web/premier/projekt-wsparcie-przedsiebiorcow"
        # Sprawdzenie oczyszczenia HTML
        assert (
            "Rada Ministrów przyjęła dzisiaj kluczowy projekt ustawy wspierający MŚP."
            in first.summary
        )
        assert "<p>" not in first.summary
        assert "<b>" not in first.summary
        assert first.source_name == "KPRM Komunikaty"
        assert first.category == "GOVERNMENT"


def test_rss_collector_parse_atom_10() -> None:
    """Weryfikuje poprawne pobieranie i parsowanie kanału w formacie Atom 1.0."""
    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get("https://partiarazem.pl/feed").respond(
            status_code=200,
            text=SAMPLE_ATOM_10,
            headers={"Content-Type": "application/atom+xml"},
        )

        collector = RSSCollector(timeout=5.0)
        items = collector.fetch_feed(
            url="https://partiarazem.pl/feed",
            source_name="Partia Razem",
            category="RAZEM",
        )

        assert len(items) == 1
        item = items[0]
        assert "Razem przedstawia projekt o skróconym czasie pracy" in item.title
        assert item.link == "https://partiarazem.pl/aktualnosci/skrocony-czas-pracy"
        assert "35-godzinnego tygodnia pracy" in item.summary
        assert item.category == "RAZEM"


def test_rss_collector_non_blocking_on_http_error() -> None:
    """Weryfikuje, że błędy serwera HTTP (np. 500, 404) są izolowane i nie rzucają wyjątków."""
    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get("https://broken.party.pl/rss").respond(
            status_code=500, text="Internal Error"
        )

        collector = RSSCollector(timeout=2.0)
        items = collector.fetch_feed(
            url="https://broken.party.pl/rss",
            source_name="Zepsute Źródło",
        )

        # Zwraca pustą listę zamiast przerwać działanie programu
        assert items == []


def test_rss_collector_non_blocking_on_network_timeout() -> None:
    """Weryfikuje, że timeout sieciowy nie zawiesza ani nie przerywa działania skryptu."""
    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get("https://timeout.sejm.gov.pl/rss").mock(
            side_effect=httpx.ConnectTimeout("Połączenie przedawnione")
        )

        collector = RSSCollector(timeout=1.0)
        items = collector.fetch_feed(
            url="https://timeout.sejm.gov.pl/rss",
            source_name="Timeout Source",
        )

        assert items == []


def test_rss_collector_non_blocking_on_malformed_xml() -> None:
    """Weryfikuje obsługę uszkodzonego pliku XML/RSS."""
    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get("https://corrupt.pl/rss").respond(
            status_code=200,
            text="<xml>to nie jest poprawny rss",
        )

        collector = RSSCollector()
        items = collector.fetch_feed(
            url="https://corrupt.pl/rss",
            source_name="Uszkodzony RSS",
        )

        assert items == []


def test_rss_collector_save_items_idempotency(db_session: Session) -> None:
    """Weryfikuje idempotentny zapis wpisów do bazy danych (brak duplikatów linków)."""
    collector = RSSCollector()
    items = [
        RSSFeedItemData(
            source_name="KPRM",
            feed_url="https://gov.pl/rss",
            title="Wpis testowy 1",
            link="https://gov.pl/news/1",
            summary="Opis wpisu 1",
            published_at=datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
            guid="guid-1",
            category="GOVERNMENT",
        ),
        RSSFeedItemData(
            source_name="KPRM",
            feed_url="https://gov.pl/rss",
            title="Wpis testowy 2",
            link="https://gov.pl/news/2",
            summary="Opis wpisu 2",
            published_at=datetime(2026, 9, 20, 13, 0, tzinfo=UTC),
            guid="guid-2",
            category="GOVERNMENT",
        ),
    ]

    # Pierwszy zapis
    saved_first = collector.save_items_to_db(db_session, items)
    assert saved_first == 2

    # Sprawdzenie w bazie
    all_db = db_session.exec(select(RSSFeedItem)).all()
    assert len(all_db) == 2

    # Ponowny zapis tych samych wpisów (plus jeden nowy)
    items_with_new = items + [
        RSSFeedItemData(
            source_name="Sejm",
            feed_url="https://sejm.gov.pl/rss",
            title="Nowy wpis 3",
            link="https://sejm.gov.pl/news/3",
            summary="Opis wpisu 3",
            published_at=datetime(2026, 9, 20, 14, 0, tzinfo=UTC),
            guid="guid-3",
            category="PARLIAMENT",
        )
    ]
    saved_second = collector.save_items_to_db(db_session, items_with_new)
    assert saved_second == 1  # Tylko 1 nowy wpis został zapisany

    total_in_db = db_session.exec(select(RSSFeedItem)).all()
    assert len(total_in_db) == 3


def test_rss_collector_fetch_all_with_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """Weryfikuje, że metoda fetch_all stosuje opóźnienie między odpytywaniem kolejnych feedów."""
    sleep_mock = MagicMock()
    monkeypatch.setattr("time.sleep", sleep_mock)

    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get("https://feed1.pl/rss").respond(status_code=200, text=SAMPLE_RSS_20)
        respx_mock.get("https://feed2.pl/rss").respond(status_code=200, text=SAMPLE_ATOM_10)

        collector = RSSCollector(delay=1.5)
        feeds = [
            {"name": "Feed 1", "url": "https://feed1.pl/rss", "category": "GOV"},
            {"name": "Feed 2", "url": "https://feed2.pl/rss", "category": "PARTY"},
        ]

        all_items = collector.fetch_all(feeds=feeds, delay=1.5)
        assert len(all_items) == 3
        # Powinno wywołać time.sleep dokładnie raz między 2 żądaniami
        sleep_mock.assert_called_once_with(1.5)
