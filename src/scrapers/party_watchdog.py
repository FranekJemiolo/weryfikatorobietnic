"""Moduł PartyWatchdog: Detekcja cichych zmian w programach wyborczych partii politycznych."""

import hashlib
import logging
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml
from bs4 import BeautifulSoup
from sqlalchemy import Engine
from sqlmodel import Session, desc, select

from src.database.engine import get_engine
from src.database.models import Promise, PromiseRevision

logger = logging.getLogger("PartyWatchdog")
logging.basicConfig(level=logging.INFO)


class PartyWatchdog:
    """Monitor stron partii politycznych wykrywający ciche modyfikacje treści deklaracji."""

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; WeryfikatorObietnicBot/1.0; "
            "+https://github.com/FranekJemiolo/weryfikatorobietnic)"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    def __init__(
        self,
        urls: list[str] | None = None,
        engine: Engine | None = None,
        timeout: float = 15.0,
        delay: float = 0.5,
    ) -> None:
        """Inicjalizuje monitora stron partii.

        Args:
            urls: Lista monitorowanych adresów URL.
            engine: Opcjonalny silnik SQLAlchemy/SQLModel (np. testowy).
            timeout: Maksymalny czas oczekiwania na odpowiedź serwera w sekundach.
            delay: Odstęp czasowy między odpytywaniem kolejnych stron (polityka uprzejmości).
        """
        self.urls = urls or []
        self.engine = engine or get_engine()
        self.timeout = timeout
        self.delay = delay

    @classmethod
    def load_targets_from_yaml(
        cls, config_path: Path | str = "config/parties.yaml"
    ) -> list[dict[str, str]]:
        """Wczytuje listę celów monitoringu stron partii z pliku konfiguracyjnego YAML."""
        path = Path(config_path)
        if not path.is_file():
            logger.warning("Plik %s nie istnieje. Zwracam pustą listę celów.", path)
            return []

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        targets: list[dict[str, str]] = []
        for party in data.get("parties", []):
            party_id = party.get("id", "INNE")
            for idx, item in enumerate(party.get("monitored_urls", [])):
                url = item.get("url")
                if url:
                    targets.append(
                        {
                            "url": url,
                            "promise_id": f"{party_id}-PROG-{idx + 1:03d}",
                            "party": party_id,
                            "name": item.get("name", f"Deklaracja {party_id}"),
                        }
                    )
        return targets

    def clean_html(self, html_content: str) -> tuple[str, str]:
        """Oczyszcza HTML z elementów nawigacyjnych i dynamicznych oraz oblicza hash SHA-256.

        Skupia się na tagach semantycznych (<main>, <article>), odrzucając nagłówki,
        stopki, skrypty i elementy interfejsu.

        Args:
            html_content: Surowy kod źródłowy strony HTML.

        Returns:
            Krotka: (oczyszczony_tekst, skrót_sha256).
        """
        soup = BeautifulSoup(html_content, "html.parser")

        # Usunięcie elementów szumowych i dynamicznych
        for tag in soup(
            ["script", "style", "nav", "footer", "header", "aside", "form", "noscript", "iframe"]
        ):
            tag.decompose()

        # Poszukiwanie głównego kontenera merytorycznego
        main_content = soup.find("main") or soup.find("article") or soup.body or soup

        raw_text = main_content.get_text(separator=" ", strip=True)
        # Normalizacja spacji i białych znaków
        clean_text = re.sub(r"\s+", " ", raw_text).strip()

        # Obliczenie deterministycznego hasha SHA-256
        content_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()
        return clean_text, content_hash

    def fetch_page(self, url: str) -> str:
        """Pobiera zawartość strony HTML za pomocą biblioteki HTTP."""
        with httpx.Client(
            headers=self.DEFAULT_HEADERS, timeout=self.timeout, follow_redirects=True
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text

    def check_and_update(
        self,
        url: str,
        promise_id: str,
        html_content: str | None = None,
    ) -> dict[str, Any]:
        """Sprawdza czy strona uległa modyfikacji i w razie potrzeby rejestruje nową rewizję.

        Args:
            url: Adres URL poddawany analizie.
            promise_id: Identyfikator powiązanej obietnicy wyborczej w tabeli Promise.
            html_content: Opcjonalna zawartość HTML (np. wstrzyknięta w testach jednostkowych).

        Returns:
            Słownik ze statusem: {'url', 'promise_id', 'content_hash', 'is_changed', 'is_initial'}.
        """
        raw_html = html_content if html_content is not None else self.fetch_page(url)
        clean_text, current_hash = self.clean_html(raw_html)

        with Session(self.engine) as session:
            # Upewnij się, że obietnica istnieje w tabeli referencyjnej (Promise)
            promise = session.get(Promise, promise_id)
            if not promise:
                # Automatyczne utworzenie obietnicy bazowej, jeśli jeszcze nie istnieje w bazie
                promise = Promise(
                    id=promise_id,
                    party="INNE",
                    title=f"Deklaracja {promise_id}",
                    full_text=clean_text[:500],
                    category="Ogólne",
                )
                session.add(promise)
                session.commit()

            # Pobranie najnowszej zarejestrowanej rewizji dla tej obietnicy
            statement = (
                select(PromiseRevision)
                .where(PromiseRevision.promise_id == promise_id)
                .order_by(desc(PromiseRevision.scraped_at))
                .limit(1)
            )
            latest_revision = session.exec(statement).first()

            if latest_revision is None:
                is_initial = True
                is_changed = False
                logger.info(
                    "Pierwsza rejestracja treści dla obietnicy %s (hash: %s...)",
                    promise_id,
                    current_hash[:8],
                )
                new_revision = PromiseRevision(
                    promise_id=promise_id,
                    content_hash=current_hash,
                    full_html_content=raw_html,
                    scraped_at=datetime.now(UTC),
                )
                session.add(new_revision)
                session.commit()
            elif latest_revision.content_hash != current_hash:
                is_initial = False
                is_changed = True
                logger.warning(
                    "⚠️ [ALERT - CICHA ZMIANA] Wykryto modyfikację postulatu %s pod adresem %s! Poprzedni hash: %s, Nowy hash: %s",
                    promise_id,
                    url,
                    latest_revision.content_hash[:8],
                    current_hash[:8],
                )
                new_revision = PromiseRevision(
                    promise_id=promise_id,
                    content_hash=current_hash,
                    full_html_content=raw_html,
                    scraped_at=datetime.now(UTC),
                )
                session.add(new_revision)
                session.commit()
            else:
                is_initial = False
                is_changed = False
                logger.info(
                    "Brak zmian dla obietnicy %s (hash spójny: %s...)",
                    promise_id,
                    current_hash[:8],
                )

        return {
            "url": url,
            "promise_id": promise_id,
            "content_hash": current_hash,
            "is_changed": is_changed,
            "is_initial": is_initial,
        }

    def monitor_all(
        self,
        targets: list[dict[str, str]] | None = None,
    ) -> list[dict[str, Any]]:
        """Uruchamia cykliczny audyt dla przekazanej listy celów.

        Args:
            targets: Lista słowników o strukturze [{'url': '...', 'promise_id': '...'}]
        """
        audit_targets = targets or [
            {"url": u, "promise_id": f"PROM-{i}"} for i, u in enumerate(self.urls)
        ]
        results: list[dict[str, Any]] = []

        for idx, target in enumerate(audit_targets):
            url = target["url"]
            promise_id = target["promise_id"]
            try:
                res = self.check_and_update(url=url, promise_id=promise_id)
                results.append(res)
            except Exception as exc:
                logger.error("Błąd podczas audytu adresu %s: %s", url, exc)
                results.append(
                    {
                        "url": url,
                        "promise_id": promise_id,
                        "error": str(exc),
                        "is_changed": False,
                        "is_initial": False,
                    }
                )

            if self.delay > 0 and idx < len(audit_targets) - 1:
                time.sleep(self.delay)

        return results
