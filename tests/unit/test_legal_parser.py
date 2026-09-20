"""Testy jednostkowe modułu LegalTextParser (Legal AST)."""

from src.parsers.legal_parser import LegalTextParser


def test_parse_provisions_with_sections_chapters_and_articles() -> None:
    """Weryfikuje poprawne wyodrębnianie hierarchii Dział -> Rozdział -> Artykuł -> Ustęp."""
    legal_text = """
    DZIAŁ I. PRZEPISY OGÓLNE
    ROZDZIAŁ 1. ZAKRES USTAWY

    Art. 1. Ustawa określa warunki prowadzenia działalności gospodarczej.

    Art. 2.
    1. Przedsiębiorcą jest osoba fizyczna, osoba prawna lub jednostka organizacyjna.
    2. Zasady podejmowania działalności regulują odrębne przepisy.

    ROZDZIAŁ 2. PODATKI I OPŁATY

    Art. 3. Kwotę wolną od podatku ustala się na poziomie 60 000 zł.
    """
    parser = LegalTextParser()
    provisions = parser.parse_provisions(legal_text)

    assert len(provisions) == 4

    # Art. 1
    assert provisions[0].article == "Art. 1"
    assert provisions[0].paragraph is None
    assert "PRZEPISY OGÓLNE" in provisions[0].context_path
    assert "ROZDZIAŁ 1" in provisions[0].context_path
    assert "warunki prowadzenia działalności" in provisions[0].text

    # Art. 2 ust. 1
    assert provisions[1].article == "Art. 2"
    assert provisions[1].paragraph == "ust. 1"
    assert "osoba fizyczna" in provisions[1].text
    assert "Art. 2 > ust. 1" in provisions[1].context_path

    # Art. 2 ust. 2
    assert provisions[2].article == "Art. 2"
    assert provisions[2].paragraph == "ust. 2"
    assert "Zasady podejmowania" in provisions[2].text

    # Art. 3
    assert provisions[3].article == "Art. 3"
    assert "60 000 zł" in provisions[3].text
    assert "ROZDZIAŁ 2" in provisions[3].context_path


def test_parse_provisions_alphanumeric_articles() -> None:
    """Sprawdza obsługę artykułów nowelizacyjnych z literami (np. Art. 15zzr)."""
    text = """
    Art. 15zzr. W okresie stanu zagrożenia epidemicznego bieg terminów nie rozpoczyna się.
    Art. 16. Ustawa wchodzi w życie z dniem ogłoszenia.
    """
    parser = LegalTextParser()
    provisions = parser.parse_provisions(text)

    assert len(provisions) == 2
    assert provisions[0].article == "Art. 15zzr"
    assert provisions[1].article == "Art. 16"
