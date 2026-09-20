"""Moduł parsowania tekstów prawnych i budowania hierarchicznej struktury przepisów (Legal AST).

Wyodrębnia tekst z plików PDF (pypdf) i rozbija go za pomocą zaawansowanych wyrażeń regularnych
na spójne, adresowalne encje: Dział -> Rozdział -> Artykuł -> Ustęp -> Punkt.
"""

import re
from io import BytesIO
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from pypdf import PdfReader


class ParsedProvision(BaseModel):
    """Pojedynczy wyodrębniony przepis prawny z pełnym kontekstem hierarchicznym."""

    article: str = Field(..., description="Numer artykułu, np. 'Art. 5' lub 'Art. 12a'")
    paragraph: str | None = Field(default=None, description="Numer ustępu, np. 'ust. 1'")
    point: str | None = Field(default=None, description="Numer punktu, np. 'pkt 2'")
    section: str | None = Field(default=None, description="Tytuł działu, np. 'Dział I'")
    chapter: str | None = Field(default=None, description="Tytuł rozdziału, np. 'Rozdział 2: Podatki'")
    text: str = Field(..., description="Treść merytoryczna przepisu")
    context_path: str = Field(..., description="Ścieżka hierarchiczna, np. 'Rozdział 2 > Art. 5 ust. 1'")

    model_config = ConfigDict(frozen=True)


class LegalTextParser:
    """Parser strukturyzujący płaski tekst polskich aktów prawnych."""

    # Wzorce Regex dla struktury polskiego prawa (z tolerancją na wcięcia i białe znaki)
    RE_SECTION = re.compile(r"^\s*(DZIAŁ\s+[IVXLCDM]+[^\n]*)", re.IGNORECASE | re.MULTILINE)
    RE_CHAPTER = re.compile(r"^\s*(ROZDZIAŁ\s+[\dIVXLCDM]+[^\n]*)", re.IGNORECASE | re.MULTILINE)
    RE_ARTICLE_SPLIT = re.compile(r"(?=^\s*Art\.\s*\d+[a-z]*\.)", re.MULTILINE)
    RE_ARTICLE_HEADER = re.compile(r"^\s*Art\.\s*(\d+[a-z]*)\.\s*", re.MULTILINE)
    RE_PARAGRAPH_SPLIT = re.compile(r"(?=^\s*\d+[a-z]*\.\s+)", re.MULTILINE)

    def extract_text_from_pdf(self, source: Path | str | bytes) -> str:
        """Ekstrahuje czysty tekst ze stron pliku PDF.

        Args:
            source: Ścieżka do pliku lub surowe bajty PDF.

        Returns:
            str: Połączony tekst wszystkich stron dokumentu.
        """
        if isinstance(source, (str, Path)):
            reader = PdfReader(str(source))
        else:
            reader = PdfReader(BytesIO(source))

        pages_text: list[str] = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)

        raw_content = "\n".join(pages_text)
        return self._normalize_whitespace(raw_content)

    def _normalize_whitespace(self, text: str) -> str:
        """Usuwa wielokrotne spacje i standaryzuje znaki nowej linii."""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Usunięcie numerów stron lub powtarzających się nagłówków sejmowych
        text = re.sub(r"^\s*-\s*\d+\s*-\s*$", "", text, flags=re.MULTILINE)
        return text

    def parse_provisions(self, full_text: str) -> list[ParsedProvision]:
        """Rozbija tekst ustawy na listę pojedynczych artykułów i ustępów.

        Args:
            full_text: Kompletny tekst aktu prawnego.

        Returns:
            list[ParsedProvision]: Lista wyodrębnionych jednostek redakcyjnych.
        """
        provisions: list[ParsedProvision] = []
        current_section: str | None = None
        current_chapter: str | None = None

        # Wstępne wykrycie bloków artykułowych
        chunks = self.RE_ARTICLE_SPLIT.split(full_text)

        for chunk in chunks:
            chunk_trimmed = chunk.strip()
            if not chunk_trimmed:
                continue

            # Aktualizacja sekcji i rozdziału, jeśli występują przed artykułem
            sec_match = self.RE_SECTION.search(chunk_trimmed)
            if sec_match:
                current_section = sec_match.group(1).strip()

            chap_match = self.RE_CHAPTER.search(chunk_trimmed)
            if chap_match:
                current_chapter = chap_match.group(1).strip()

            # Sprawdzenie, czy blok zaczyna się od artykułu
            art_match = self.RE_ARTICLE_HEADER.search(chunk_trimmed)
            if not art_match:
                continue

            art_num = art_match.group(1)
            article_label = f"Art. {art_num}"

            # Usunięcie nagłówka artykułu z treści
            article_body = chunk_trimmed[art_match.end() :].strip()

            # Sprawdzenie, czy artykuł dzieli się na ustępy (np. 1. Treść, 2. Treść)
            paragraphs = self.RE_PARAGRAPH_SPLIT.split(article_body)
            has_multiple_paragraphs = len(paragraphs) > 1 and bool(
                re.match(r"^\s*\d+[a-z]*\.\s+", paragraphs[0])
                or re.match(r"^\s*\d+[a-z]*\.\s+", paragraphs[1])
            )

            if has_multiple_paragraphs:
                for para_chunk in paragraphs:
                    para_chunk_clean = para_chunk.strip()
                    if not para_chunk_clean:
                        continue

                    para_match = re.match(r"^(\d+[a-z]*)\.\s*(.*)", para_chunk_clean, re.DOTALL)
                    if para_match:
                        para_num = f"ust. {para_match.group(1)}"
                        para_text = para_match.group(2).strip()
                    else:
                        para_num = None
                        para_text = para_chunk_clean

                    context_parts = [
                        p for p in [current_section, current_chapter, article_label, para_num] if p
                    ]
                    context_path = " > ".join(context_parts)

                    provisions.append(
                        ParsedProvision(
                            article=article_label,
                            paragraph=para_num,
                            section=current_section,
                            chapter=current_chapter,
                            text=para_text,
                            context_path=context_path,
                        )
                    )
            else:
                context_parts = [p for p in [current_section, current_chapter, article_label] if p]
                context_path = " > ".join(context_parts)

                provisions.append(
                    ParsedProvision(
                        article=article_label,
                        paragraph=None,
                        section=current_section,
                        chapter=current_chapter,
                        text=article_body,
                        context_path=context_path,
                    )
                )

        return provisions
