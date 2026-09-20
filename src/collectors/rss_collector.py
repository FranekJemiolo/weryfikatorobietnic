"""Kolektor kanałów informacyjnych RSS i Atom dla instytucji publicznych i partii politycznych.

Zapewnia bezpieczne, nieblokujące pobieranie komunikatów z kanałów RSS KPRM, Sejmu, RCL
oraz oficjalnych kanałów partii politycznych z zachowaniem limitów czasowych (timeout),
polityki uprzejmości (politeness delay) oraz automatyczną deduplikacją wpisów w bazie.
"""

import calendar
import logging
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import feedparser  # type: ignore[import-untyped]
import httpx
import yaml
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from src.config import settings
from src.database.models import RSSFeedItem

logger = logging.getLogger("RSSCollector")


class RSSFeedItemData(BaseModel):
    """Zwalidowany rekord pojedynczej wiadomości z kanału informacyjnego."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    source_name: str
    feed_url: str
    title: str
    link: str
    summary: str
    published_at: datetime
    guid: str | None = None
    category: str | None = None


class RSSCollector:
    """Kolektor wiadomości RSS/Atom z odpornością na awarie pojedynczych źródeł."""

    DEFAULT_HEADERS = {
        "User-Agent": settings.user_agent,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    }

    def __init__(
        self,
        config_path: Path | str | None = None,
        timeout: float = 15.0,
        delay: float = 0.5,
        client: httpx.Client | None = None,
    ) -> None:
        """Inicjalizuje kolektor RSS/Atom.

        Args:
            config_path: Opcjonalna ścieżka do pliku parties.yaml z konfiguracją feedów.
            timeout: Dopuszczalny czas oczekiwania na odpowiedź serwera w sekundach.
            delay: Czas opóźnienia między odpytywaniem kolejnych serwerów (sekundy).
            client: Opcjonalny wstrzyknięty klient httpx (przydatny m.in. w testach).
        """
        self.config_path = Path(config_path) if config_path else Path("config/parties.yaml")
        self.timeout = timeout
        self.delay = delay
        self._client = client

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(
            headers=self.DEFAULT_HEADERS,
            timeout=self.timeout,
            follow_redirects=True,
        )

    def load_configured_feeds(self) -> list[dict[str, str]]:
        """Wczytuje listę zdefiniowanych feedów RSS z pliku konfiguracyjnego YAML."""
        if not self.config_path.is_file():
            logger.warning(
                "Plik konfiguracyjny feedów %s nie istnieje. Zwracam pustą listę.",
                self.config_path,
            )
            return []

        try:
            with open(self.config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            feeds: list[dict[str, str]] = []
            for item in data.get("government_feeds", []):
                feeds.append(
                    {
                        "name": str(item.get("name", "Rządowy Feed")),
                        "url": str(item.get("url", "")),
                        "category": str(item.get("category", "GOVERNMENT")),
                    }
                )
            for item in data.get("party_feeds", []):
                feeds.append(
                    {
                        "name": str(item.get("name", "Partyjny Feed")),
                        "url": str(item.get("url", "")),
                        "category": str(item.get("party_id", "PARTY")),
                    }
                )
            return [f for f in feeds if f.get("url")]
        except Exception as exc:
            logger.error("Błąd parsowania pliku konfiguracji feedów %s: %s", self.config_path, exc)
            return []

    def clean_text(self, raw_html_or_text: str) -> str:
        """Oczyszcza treść z tagów HTML oraz normalizuje wielokrotne spacje."""
        if not raw_html_or_text:
            return ""
        soup = BeautifulSoup(raw_html_or_text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        return re.sub(r"\s+", " ", text).strip()

    def _parse_published_date(self, entry: Any) -> datetime:
        """Deterministycznie wyciąga datę publikacji wpisu lub zwraca bieżący czas UTC."""
        parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
        if parsed_time:
            try:
                timestamp = calendar.timegm(parsed_time)
                return datetime.fromtimestamp(timestamp, tz=UTC)
            except Exception:
                pass
        return datetime.now(UTC)

    def fetch_feed(
        self,
        url: str,
        source_name: str,
        category: str | None = None,
    ) -> list[RSSFeedItemData]:
        """Pobiera i parsuje pojedynczy kanał RSS/Atom w sposób bezpieczny i nieblokujący.

        W razie niedostępności źródła lub błędów sieciowych loguje błąd i zwraca pustą listę.
        """
        logger.info("Pobieranie kanału informacyjnego [%s]: %s", source_name, url)
        try:
            # Użycie httpx gwarantuje rygorystyczny timeout i nagłówek User-Agent
            if self._client is not None:
                response = self._client.get(url)
            else:
                with httpx.Client(
                    headers=self.DEFAULT_HEADERS,
                    timeout=self.timeout,
                    follow_redirects=True,
                ) as client:
                    response = client.get(url)

            response.raise_for_status()
            parsed = feedparser.parse(response.content)

            if parsed.bozo and not parsed.entries:
                logger.warning(
                    "Kanał %s zwrócił nieprawidłowy format XML/RSS lub jest pusty.",
                    source_name,
                )
                return []

            items: list[RSSFeedItemData] = []
            for entry in parsed.entries:
                title = self.clean_text(str(entry.get("title", "")))
                link = str(entry.get("link", "")).strip()
                if not link or not title:
                    continue

                raw_summary = (
                    entry.get("summary")
                    or entry.get("description")
                    or (entry.get("content", [{}])[0].get("value") if entry.get("content") else "")
                    or ""
                )
                summary = self.clean_text(str(raw_summary))
                published_at = self._parse_published_date(entry)
                guid = str(entry.get("id") or entry.get("guid") or link)

                items.append(
                    RSSFeedItemData(
                        source_name=source_name,
                        feed_url=url,
                        title=title,
                        link=link,
                        summary=summary,
                        published_at=published_at,
                        guid=guid,
                        category=category,
                    )
                )

            logger.info("Pomyślnie sparsowano %d wpisów z kanału [%s].", len(items), source_name)
            return items

        except Exception as exc:
            logger.warning(
                "Nie udało się pobrać feedu [%s] (%s): %s. Pomijam bez blokowania potoku.",
                source_name,
                url,
                exc,
            )
            return []

    def fetch_all(
        self,
        feeds: list[dict[str, str]] | None = None,
        delay: float | None = None,
    ) -> list[RSSFeedItemData]:
        """Pobiera sekwencyjnie wszystkie skonfigurowane kanały RSS z opóźnieniem uprzejmości."""
        target_feeds = feeds if feeds is not None else self.load_configured_feeds()
        sleep_interval = delay if delay is not None else self.delay
        all_items: list[RSSFeedItemData] = []

        logger.info("Rozpoczynanie pobierania danych z %d kanałów RSS/Atom...", len(target_feeds))
        for idx, feed in enumerate(target_feeds):
            url = feed.get("url", "")
            name = feed.get("name", f"Feed-{idx}")
            cat = feed.get("category")
            if not url:
                continue

            feed_items = self.fetch_feed(url=url, source_name=name, category=cat)
            all_items.extend(feed_items)

            # Odstęp między zapytaniami dla uniknięcia banów i przeciążenia serwerów
            if sleep_interval > 0 and idx < len(target_feeds) - 1:
                time.sleep(sleep_interval)

        logger.info(
            "Zakończono pobieranie z kanałów RSS. Łącznie zebrano wpisów: %d",
            len(all_items),
        )
        return all_items

    def save_items_to_db(self, session: Session, items: list[RSSFeedItemData]) -> int:
        """Idempotentnie zapisuje pobrane wpisy w tabeli rss_feed_items, pomijając duplikaty."""
        if not items:
            return 0

        # Pobieramy zbiór istniejących linków dla szybkiej weryfikacji w pamięci
        incoming_links = [item.link for item in items]
        existing_stmt = select(RSSFeedItem.link).where(RSSFeedItem.link.in_(incoming_links))  # type: ignore[attr-defined]
        existing_links = set(session.exec(existing_stmt).all())

        new_records_count = 0
        for item in items:
            if item.link in existing_links:
                continue

            db_item = RSSFeedItem(
                source_name=item.source_name,
                feed_url=item.feed_url,
                title=item.title,
                link=item.link,
                summary=item.summary,
                published_at=item.published_at,
                guid=item.guid,
                category=item.category,
            )
            session.add(db_item)
            existing_links.add(item.link)
            new_records_count += 1

        session.commit()
        logger.info("Zapisano %d nowych wpisów RSS w bazie danych.", new_records_count)
        return new_records_count
