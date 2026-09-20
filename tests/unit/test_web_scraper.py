"""Testy jednostkowe modułu śledzenia zmian stron (WebContentTracker)."""

from unittest.mock import MagicMock, patch

from src.collectors.web_scraper import WebContentTracker


def test_clean_html_content_strips_unwanted_tags() -> None:
    """Weryfikuje usuwanie tagów skryptów, styli i nawigacji z kodu HTML."""
    tracker = WebContentTracker()
    raw_html = """
    <html>
        <head>
            <script>alert('cookie banner');</script>
            <style>.banner { color: red; }</style>
        </head>
        <body>
            <nav><a href="/home">Home</a></nav>
            <main>
                <h1>Program partii 2024</h1>
                <p>Wprowadzimy reformę finansów publicznych.</p>
            </main>
            <footer>Kontakt: info@partia.pl</footer>
        </body>
    </html>
    """
    cleaned = tracker.clean_html_content(raw_html)
    assert "alert" not in cleaned
    assert "cookie" not in cleaned
    assert "Home" not in cleaned
    assert "Program partii 2024" in cleaned
    assert "Wprowadzimy reformę finansów publicznych." in cleaned


def test_compute_sha256_consistency() -> None:
    """Weryfikuje deterministyczność hasha SHA-256."""
    tracker = WebContentTracker()
    text = "Wprowadzimy zerowy VAT na żywność."
    hash1 = tracker.compute_sha256(text)
    hash2 = tracker.compute_sha256(text)
    assert hash1 == hash2
    assert len(hash1) == 64


def test_has_content_changed_detection() -> None:
    """Sprawdza logikę detekcji zmian na podstawie sum kontrolnych."""
    tracker = WebContentTracker()
    initial_hash = tracker.compute_sha256("Wersja A programu")
    new_hash = tracker.compute_sha256("Wersja B programu (po cichu zmieniona)")

    assert tracker.has_content_changed(new_hash, None) is True
    assert tracker.has_content_changed(new_hash, initial_hash) is True
    assert tracker.has_content_changed(initial_hash, initial_hash) is False


@patch("requests.Session.get")
def test_fetch_and_snapshot(mock_get: MagicMock) -> None:
    """Weryfikuje pełny przepływ tworzenia snapshota strony."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<article><h1>Konkret 1</h1><p>Obniżka składki zdrowotnej.</p></article>"
    mock_get.return_value = mock_response

    tracker = WebContentTracker()
    snapshot = tracker.fetch_and_snapshot("https://partia.example/program")

    assert snapshot.url == "https://partia.example/program"
    assert "Obniżka składki zdrowotnej" in snapshot.cleaned_text
    assert len(snapshot.content_hash) == 64
