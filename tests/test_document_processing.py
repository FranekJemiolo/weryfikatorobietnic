"""Testy jednostkowe modułu przetwarzania dokumentów PDF, chunkingu i analizy OSR."""

import fitz  # type: ignore[import-untyped]

from src.ai.analyzer import AIAnalyzer
from src.parsers.document_parser import LegalDocumentParser


def test_legal_document_parser_pdf_and_chunking() -> None:
    """Weryfikuje ekstrakcję tekstu z syntetycznego pliku PDF oraz podział na artykuły."""
    # Tworzenie syntetycznego dokumentu PDF w pamięci za pomocą PyMuPDF
    doc = fitz.open()
    page = doc.new_page()
    sample_text = (
        "USTAWA\nz dnia 15 marca 2024 r.\n\n"
        "Art. 1. Finansowanie procedury in vitro odbywa sie ze srodkow budzetowych.\n\n"
        "Art. 2. Minister wlasciwy do spraw zdrowia okresli coroczny plan wydatkow w kwocie nie mniejszej niz 500 mln zl.\n\n"
        "Art. 3a. Ustawa wchodzi w zycie z dniem 1 czerwca 2024 r."
    )
    page.insert_textbox(fitz.Rect(50, 50, 550, 750), sample_text)
    pdf_bytes = doc.write()
    doc.close()

    parser = LegalDocumentParser()
    extracted_text = parser.extract_text(pdf_bytes)

    assert "Art. 1." in extracted_text
    assert "Finansowanie procedury" in extracted_text

    chunks = parser.chunk_bill_text(extracted_text)
    assert len(chunks) == 3
    assert chunks[0]["article_number"] == "Art. 1."
    assert "in vitro odbywa sie" in chunks[0]["raw_text"]
    assert chunks[1]["article_number"] == "Art. 2."
    assert "500 mln zl" in chunks[1]["raw_text"]
    assert chunks[2]["article_number"] == "Art. 3a."


def test_ai_analyzer_embeddings_generation() -> None:
    """Weryfikuje generowanie wektorów osadzeń o wymiarowości 1536 dla pgvector."""
    analyzer = AIAnalyzer()
    chunks = [
        "Art. 1. Podatek dochodowy od osób fizycznych.",
        "Art. 2. Kwota wolna od podatku wynosi 60 000 zł.",
    ]
    embeddings = analyzer.generate_embeddings(chunks)

    assert len(embeddings) == 2
    assert len(embeddings[0]) == 1536
    assert len(embeddings[1]) == 1536
    assert all(isinstance(val, float) for val in embeddings[0])


def test_ai_analyzer_osr_financial_extraction() -> None:
    """Weryfikuje ekstrakcję szacunkowych kosztów i podsumowania z tekstu OSR."""
    analyzer = AIAnalyzer()
    sample_osr = (
        "Ocena Skutków Regulacji (OSR):\n"
        "Wprowadzenie regulacji spowoduje obniżenie dochodów sektora finansów publicznych o 35 mld zł "
        "w pierwszym roku obowiązywania ustawy. Wpływ na mikroprzedsiębiorstwa szacuje się jako pozytywny."
    )

    result = analyzer.analyze_osr_financials(sample_osr)

    assert isinstance(result, dict)
    assert "estimated_budget_impact_pln" in result
    assert "summary" in result
    # Heurystyka lub LLM powinny wyłapać kwotę rzędu 35 mld (35 000 000 000)
    assert result["estimated_budget_impact_pln"] == 35_000_000_000.0
    assert len(result["summary"]) > 10


def test_download_pdf_to_file(tmp_path: fitz.Rect) -> None:
    """Weryfikuje strumieniowe pobieranie PDF bezpośrednio na dysk."""
    from pathlib import Path

    import respx
    from httpx import Response

    from src.parsers.document_parser import download_pdf_to_file

    fake_url = "https://example.com/test_bill.pdf"
    fake_pdf = b"%PDF-1.4 test document content for streaming"
    target_file = Path(str(tmp_path)) / "test_bill.pdf"

    with respx.mock:
        respx.get(fake_url).mock(return_value=Response(200, content=fake_pdf))
        saved_path = download_pdf_to_file(fake_url, target_file)

        assert saved_path.exists()
        assert saved_path.read_bytes() == fake_pdf
