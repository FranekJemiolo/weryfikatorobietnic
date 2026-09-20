"""Moduł scrapera stron internetowych partii politycznych i kanałów informacyjnych.

Odpowiada za pobieranie treści HTML, usuwanie elementów dynamicznych (szumu)
oraz wyliczanie hashy kryptograficznych SHA-256 w celu wykrywania zmian w obietnicach.
"""

import hashlib
import re
from typing import NamedTuple

import requests
from bs4 import BeautifulSoup

from src.config import settings


class ContentSnapshot(NamedTuple):
    """Niezmienny rekord reprezentujący stan pobranej i oczyszczonej strony."""

    url: str
    content_hash: str
    cleaned_text: str
    raw_html: str


class WebContentTracker:
    """Klasa monitorująca zmiany treści na stronach www i kanałach programowych."""

    def __init__(self, timeout: int | None = None) -> None:
        """Inicjalizuje moduł śledzenia stron.

        Args:
            timeout: Maksymalny czas oczekiwania na odpowiedź w sekundach.
        """
        self._timeout = timeout or settings.request_timeout_seconds
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": settings.user_agent})

    def clean_html_content(self, raw_html: str) -> str:
        """Usuwa tagi techniczne, skrypty, style i elementy dynamiczne z HTML.

        Args:
            raw_html: Surowy kod strony w HTML.

        Returns:
            str: Znormalizowany i oczyszczony tekst merytoryczny.
        """
        soup = BeautifulSoup(raw_html, "html.parser")

        # Usuwamy elementy niebędące treścią merytoryczną
        for element in soup(
            ["script", "style", "noscript", "svg", "nav", "footer", "header", "form"]
        ):
            element.decompose()

        text = soup.get_text(separator=" ")
        # Redukcja wielokrotnych spacji i nowych linii
        cleaned = re.sub(r"\s+", " ", text).strip()
        return cleaned

    def compute_sha256(self, text: str) -> str:
        """Oblicza sumę kontrolną SHA-256 dla przekazanego tekstu.

        Args:
            text: Tekst źródłowy.

        Returns:
            str: 64-znakowy ciąg heksadecymalny hash SHA-256.
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def fetch_and_snapshot(self, url: str) -> ContentSnapshot:
        """Pobiera zawartość strony pod danym URL i tworzy jej znormalizowany snapshot.

        Args:
            url: Adres URL strony do pobrania.

        Returns:
            ContentSnapshot: Obiekt zawierający oczyszczony tekst i hash SHA-256.

        Raises:
            requests.RequestException: W przypadku błędu sieciowego podczas pobierania.
        """
        response = self._session.get(url, timeout=self._timeout)
        response.raise_for_status()
        raw_html = response.text
        cleaned_text = self.clean_html_content(raw_html)
        content_hash = self.compute_sha256(cleaned_text)

        return ContentSnapshot(
            url=url,
            content_hash=content_hash,
            cleaned_text=cleaned_text,
            raw_html=raw_html,
        )

    def has_content_changed(self, new_hash: str, previous_hash: str | None) -> bool:
        """Sprawdza, czy zawartość strony uległa zmianie względem poprzedniego snapshota.

        Args:
            new_hash: Nowo wyliczony hash SHA-256.
            previous_hash: Wcześniejszy hash zapisany w bazie danych.

        Returns:
            bool: True jeśli zawartość uległa zmianie (lub poprzedni stan nie istniał).
        """
        if not previous_hash:
            return True
        return new_hash != previous_hash
