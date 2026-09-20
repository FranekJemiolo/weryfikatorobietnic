"""Moduł pobierania i parsowania dokumentów prawnych (PDF) oraz podziału na artykuły (Chunking)."""

import re
from pathlib import Path
from typing import Any

import fitz  # type: ignore[import-untyped]
import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

DEFAULT_PDF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; WeryfikatorObietnicPDFBot/1.0; "
        "+https://github.com/FranekJemiolo/weryfikatorobietnic)"
    ),
    "Accept": "application/pdf,*/*",
}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=1.0, max=5.0),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True,
)
def download_pdf(url: str, timeout: float = 30.0) -> bytes:
    """Pobiera binarną zawartość pliku PDF ze wskazanego adresu URL z automatycznym ponawianiem.

    Args:
        url: Bezpośredni adres URL do pliku PDF (np. z sejm.gov.pl lub RCL).
        timeout: Maksymalny czas pobierania w sekundach.

    Returns:
        Surowe bajty pliku PDF.
    """
    with httpx.Client(
        headers=DEFAULT_PDF_HEADERS, timeout=timeout, follow_redirects=True
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        content = response.content

        # Weryfikacja nagłówka binarnego PDF (%PDF-)
        if not content.startswith(b"%PDF-"):
            raise ValueError(
                f"Pobrany zasób z {url} nie jest poprawnym plikiem PDF (brak sygnatury %PDF-)."
            )

        return content


class LegalDocumentParser:
    """Parser dokumentów prawnych i OSR oparty na silniku PyMuPDF (fitz)."""

    def extract_text(self, source: bytes | str | Path) -> str:
        """Wyodrębnia pełny tekst ze źródła PDF (bajty w pamięci lub ścieżka do pliku).

        Args:
            source: Surowe bajty dokumentu PDF lub ścieżka na dysku.

        Returns:
            Czysty, połączony ciąg znaków z całego dokumentu.
        """
        if isinstance(source, bytes):
            doc = fitz.open(stream=source, filetype="pdf")
        else:
            doc = fitz.open(str(source))

        pages_text: list[str] = []
        try:
            for page in doc:
                text = page.get_text("text")
                if text:
                    pages_text.append(text)
        finally:
            doc.close()

        full_text = "\n".join(pages_text)
        # Normalizacja wielokrotnych pustych linii
        return re.sub(r"\n{3,}", "\n\n", full_text).strip()

    def chunk_bill_text(self, text: str) -> list[dict[str, Any]]:
        """Dzieli treść ustawy na mniejsze, logiczne jednostki redakcyjne (artykuły) dla RAG.

        Wyszukuje wzorce artykułów (np. 'Art. 1.', 'Art. 12a.') i przypisuje im ich
        zawartość. Jeśli dokument nie posiada struktury artykułowej (np. uzasadnienie),
        dzieli go na zbalansowane akapity.

        Args:
            text: Tekst dokumentu prawnego.

        Returns:
            Lista słowników w formacie: [{'article_number': 'Art. 1.', 'raw_text': '...'}]
        """
        if not text or not text.strip():
            return []

        # Wzorzec dopasowujący początek artykułu: np. "Art. 1.", "Art. 2a."
        article_pattern = re.compile(r"(?:^|\n)(Art\.\s*\d+[a-z]?\.)", re.IGNORECASE)
        splits = list(article_pattern.finditer(text))

        if not splits:
            # Fallback dla dokumentów nieartykułowych (np. ogólne załączniki): podział na bloki ~1200 znaków
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            chunks: list[dict[str, Any]] = []
            curr_chunk: list[str] = []
            curr_len = 0
            part_idx = 1

            for p in paragraphs:
                if curr_len + len(p) > 1200 and curr_chunk:
                    chunks.append(
                        {
                            "article_number": f"Fragment {part_idx}",
                            "raw_text": "\n\n".join(curr_chunk),
                        }
                    )
                    part_idx += 1
                    curr_chunk = [p]
                    curr_len = len(p)
                else:
                    curr_chunk.append(p)
                    curr_len += len(p)

            if curr_chunk:
                chunks.append(
                    {
                        "article_number": f"Fragment {part_idx}",
                        "raw_text": "\n\n".join(curr_chunk),
                    }
                )
            return chunks

        results: list[dict[str, Any]] = []

        for i, match in enumerate(splits):
            art_label = re.sub(r"\s+", " ", match.group(1).strip())
            start_pos = match.start()
            end_pos = splits[i + 1].start() if i + 1 < len(splits) else len(text)

            art_text = text[start_pos:end_pos].strip()
            results.append(
                {
                    "article_number": art_label,
                    "raw_text": art_text,
                }
            )

        return results
