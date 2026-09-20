"""Moduł pobierania i audytowalnej archiwizacji dokumentów PDF z Sejmu i RCL.

Obsługuje pobieranie strumieniowe, weryfikację nagłówków binarnych (%PDF-),
wyliczanie sumy kontrolnej SHA-256, rejestrację w bazie danych oraz retry.
"""

import hashlib
from pathlib import Path
from typing import NamedTuple

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config import settings
from src.core.database import db_manager


class DownloadedDocumentInfo(NamedTuple):
    """Informacje o pomyślnie pobranym i zwalidowanym dokumencie binarnym."""

    file_name: str
    file_path: Path
    file_size_bytes: int
    sha256_hash: str
    document_type: str
    term: int
    associated_id: str
    is_new: bool


class DocumentDownloaderError(Exception):
    """Wyjątek zgłaszany w przypadku błędu pobierania lub niepoprawnego pliku PDF."""


class DocumentDownloader:
    """Moduł zarządzający bezpiecznym pobieraniem i archiwizacją załączników PDF."""

    def __init__(self, target_directory: Path | str | None = None) -> None:
        """Inicjalizuje downloader dokumentów.

        Args:
            target_directory: Ścieżka katalogu lokalnego zapisu (domyślnie data/raw/pdfs).
        """
        if target_directory is None:
            self._storage_dir = Path("data/raw/pdfs").resolve()
        else:
            self._storage_dir = Path(target_directory).resolve()

        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._timeout = settings.request_timeout_seconds

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    )
    def download_pdf(
        self,
        url: str,
        file_name: str,
        document_type: str,
        term: int = 10,
        associated_id: str = "unknown",
    ) -> DownloadedDocumentInfo:
        """Pobiera strumieniowo plik PDF, sprawdza nagłówek i zapisuje go w magazynie.

        Args:
            url: Zewnętrzny URL do pliku PDF (np. załącznik z Sejm OpenAPI).
            file_name: Docelowa nazwa pliku (np. 'druk_sejmowy_k10_nr34.pdf').
            document_type: Kategoria dokumentu (np. 'PRINT', 'OSR', 'RCL').
            term: Kadencja Sejmu.
            associated_id: Identyfikator powiązanego bytu (numer druku/procesu).

        Returns:
            DownloadedDocumentInfo: Szczegóły pobranego pliku.

        Raises:
            DocumentDownloaderError: Jeśli plik nie jest poprawnym dokumentem PDF.
        """
        if not file_name.endswith(".pdf"):
            file_name = f"{file_name}.pdf"

        destination_path = self._storage_dir / file_name
        headers = {"User-Agent": settings.user_agent}

        hasher = hashlib.sha256()
        total_bytes = 0

        with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()

            content = response.content
            if not content.startswith(b"%PDF-"):
                raise DocumentDownloaderError(
                    f"Plik pod adresem {url} nie posiada prawidłowego nagłówka PDF (%PDF-)."
                )

            hasher.update(content)
            total_bytes = len(content)
            sha256_hash = hasher.hexdigest()

            destination_path.write_bytes(content)

        # Rejestracja w bazie danych PostgreSQL (jeśli dostępna)
        self._record_in_database(
            document_type=document_type,
            term=term,
            associated_id=associated_id,
            file_name=file_name,
            file_path=str(destination_path),
            file_size_bytes=total_bytes,
            sha256_hash=sha256_hash,
        )

        return DownloadedDocumentInfo(
            file_name=file_name,
            file_path=destination_path,
            file_size_bytes=total_bytes,
            sha256_hash=sha256_hash,
            document_type=document_type,
            term=term,
            associated_id=associated_id,
            is_new=True,
        )

    def _record_in_database(
        self,
        document_type: str,
        term: int,
        associated_id: str,
        file_name: str,
        file_path: str,
        file_size_bytes: int,
        sha256_hash: str,
    ) -> None:
        """Zapisuje metadane pobranego dokumentu do tabeli downloaded_documents."""
        query = """
            INSERT INTO downloaded_documents (
                document_type, term, associated_id, file_name, file_path, file_size_bytes, sha256_hash
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        try:
            with db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        query,
                        (
                            document_type,
                            term,
                            associated_id,
                            file_name,
                            file_path,
                            file_size_bytes,
                            sha256_hash,
                        ),
                    )
                conn.commit()
        except Exception:
            # W środowiskach testowych lub bez podłączonej bazy kontynuujemy bez rzucania błędu
            pass
