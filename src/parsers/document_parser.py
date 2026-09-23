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


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=1.0, max=5.0),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True,
)
def download_pdf_to_file(url: str, target_path: Path, timeout: float = 60.0) -> Path:
    """Strumieniowe pobieranie pliku PDF bezpośrednio na dysk bez buforowania całości w pamięci RAM.

    Chroni procesy Airflow przed błędem OOM Killer przy pobieraniu załączników i wielotomowych projektów ustaw.

    Args:
        url: Bezpośredni adres URL do pliku PDF.
        target_path: Ścieżka docelowa pliku na dysku.
        timeout: Maksymalny czas pobierania w sekundach.

    Returns:
        Ścieżka do zapisanego pliku PDF.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(
        headers=DEFAULT_PDF_HEADERS, timeout=timeout, follow_redirects=True
    ) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            with open(target_path, "wb") as f:
                first_chunk = True
                for chunk in response.iter_bytes(chunk_size=65536):
                    if first_chunk:
                        if not chunk.startswith(b"%PDF-"):
                            raise ValueError(
                                f"Pobrany zasób z {url} nie jest poprawnym plikiem PDF (brak sygnatury %PDF-)."
                            )
                        first_chunk = False
                    f.write(chunk)
    return target_path


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

    def is_committee_report(self, text: str, document_title: str | None = None) -> bool:
        """Sprawdza, czy analizowany druk jest sprawozdaniem komisji sejmowej."""
        title_norm = (document_title or "").lower()
        if "sprawozdanie komisji" in title_norm or "dodatkowe sprawozdanie" in title_norm:
            return True

        header_sample = text[:2000].lower()
        return (
            "sprawozdanie komisji" in header_sample
            or "dodatkowe sprawozdanie komisji" in header_sample
            or ("komisja" in header_sample and "po rozpatrzeniu projektu" in header_sample)
        )

    def parse_committee_report_amendments(
        self, text: str, document_title: str | None = None
    ) -> list[dict[str, Any]]:
        """Wyodrębnia poprawki oraz wnioski mniejszości ze sprawozdania komisji sejmowej.

        Wyszukuje bloki poprawek (np. 'Poprawka 1.', 'Wniosek mniejszości nr 2') oraz identyfikuje
        zmieniane jednostki redakcyjne (artykuły) i rekomendację komisji (przyjęcie/odrzucenie).

        Args:
            text: Pełny tekst sprawozdania komisji sejmowej.
            document_title: Opcjonalny tytuł druku z Sejm API.

        Returns:
            Lista słowników ze strukturą poprawki:
            [
                {
                    'article_reference': 'Art. 4',
                    'text_content': '...',
                    'is_accepted': True,
                    'is_minority_report': False
                }
            ]
        """
        if not text or not self.is_committee_report(text, document_title):
            return []

        # Wzorzec dzielący na kolejne poprawki lub wnioski mniejszości
        amendment_pattern = re.compile(
            r"(?:^|\n)\s*((?:Poprawka|Wniosek mniejszości)(?:\s+(?:nr\s*)?\d+)?[:.\-]?\s*)",
            re.IGNORECASE,
        )
        splits = list(amendment_pattern.finditer(text))
        if not splits:
            # Próba wyłapania struktury punktowej, np. '1) w art. 5...', '2) skreśla się art. 8...'
            alt_pattern = re.compile(
                r"(?:^|\n)\s*(\d+\)\s+(?:w\s+art\.|dodaje\s+się\s+art\.|skreśla\s+się\s+art\.))",
                re.IGNORECASE,
            )
            splits = list(alt_pattern.finditer(text))

        if not splits:
            return []

        amendments: list[dict[str, Any]] = []
        for i, match in enumerate(splits):
            start_pos = match.start()
            end_pos = splits[i + 1].start() if i + 1 < len(splits) else len(text)
            chunk = text[start_pos:end_pos].strip()

            # Wyodrębnienie powiązanego artykułu
            art_match = re.search(
                r"(?:w\s+|dodaje\s+się\s+|skreśla\s+się\s+)(art\.\s*\d+[a-z]?)",
                chunk,
                re.IGNORECASE,
            )
            art_ref = re.sub(r"\s+", " ", art_match.group(1)).capitalize() if art_match else None

            # Wykrycie rekomendacji komisji (przyjęta vs wniosek o odrzucenie)
            lower_chunk = chunk.lower()
            is_minority = "wniosek mniejszości" in lower_chunk
            is_accepted = True
            if is_minority or "wnosi o odrzucenie" in lower_chunk or "odrzucić" in lower_chunk:
                is_accepted = False

            amendments.append(
                {
                    "article_reference": art_ref,
                    "text_content": chunk[:1500].strip(),
                    "is_accepted": is_accepted,
                    "is_minority_report": is_minority,
                }
            )

        return amendments


def flag_evaluations_for_re_evaluation(
    session: Any,
    bill_id: str,
    amendments: list[dict[str, Any]],
) -> int:
    """Oznacza powiązane ewaluacje LLM flagą requires_re_evaluation=True, jeśli wykryto kluczowe poprawki.

    Zapisuje wyciągnięte poprawki do tabeli `bill_amendments` oraz wymusza ponowną ocenę RAG
    w przypadku ingerencji w treść procedowanej ustawy (np. tzw. 'wrzutki legislacyjne').

    Args:
        session: Aktywna sesja bazy danych (SQLModel/SQLAlchemy).
        bill_id: ID procedowanego projektu ustawy (np. 'druk-124').
        amendments: Lista sparsowanych poprawek z raportu komisji.

    Returns:
        Liczba zaktualizowanych ewaluacji LLM.
    """
    if not amendments:
        return 0

    from sqlmodel import col, select

    from src.database.models import BillAmendment, LLMEvaluation

    # Zapis poprawek w bazie danych
    for am in amendments:
        db_amendment = BillAmendment(
            bill_id=bill_id,
            article_reference=am.get("article_reference"),
            text_content=am.get("text_content", ""),
            is_accepted=bool(am.get("is_accepted", False)),
        )
        session.add(db_amendment)

    # Wyszukanie istniejących ocen dla tego projektu ustawy
    eval_stmt = select(LLMEvaluation).where(
        col(LLMEvaluation.bill_id) == bill_id,
        col(LLMEvaluation.requires_re_evaluation) == False,  # noqa: E712
    )
    evaluations = session.exec(eval_stmt).all()
    count = 0
    for evaluation in evaluations:
        evaluation.requires_re_evaluation = True
        session.add(evaluation)
        count += 1

    session.commit()
    return count
