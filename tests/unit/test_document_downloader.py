"""Testy jednostkowe modułu DocumentDownloader."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.collectors.document_downloader import DocumentDownloader, DocumentDownloaderError


def test_download_pdf_success(tmp_path: Path) -> None:
    """Weryfikuje pomyślne pobieranie pliku PDF, nagłówek %PDF- oraz sumę SHA-256."""
    fake_pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = fake_pdf_bytes

    with patch("httpx.Client.get", return_value=mock_response):
        downloader = DocumentDownloader(target_directory=tmp_path)
        info = downloader.download_pdf(
            url="https://api.sejm.gov.pl/term10/prints/42/42.pdf",
            file_name="druk_sejmowy_k10_nr42.pdf",
            document_type="PRINT",
            term=10,
            associated_id="42",
        )

        assert info.file_name == "druk_sejmowy_k10_nr42.pdf"
        assert info.file_size_bytes == len(fake_pdf_bytes)
        assert info.file_path.exists()
        assert info.file_path.read_bytes() == fake_pdf_bytes
        assert len(info.sha256_hash) == 64


def test_download_pdf_invalid_header(tmp_path: Path) -> None:
    """Sprawdza odrzucenie pliku, który nie jest poprawnym dokumentem PDF."""
    html_error_page = b"<html><body>404 Not Found</body></html>"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = html_error_page

    with patch("httpx.Client.get", return_value=mock_response):
        downloader = DocumentDownloader(target_directory=tmp_path)
        with pytest.raises(DocumentDownloaderError) as exc_info:
            downloader.download_pdf(
                url="https://api.sejm.gov.pl/term10/prints/fake.pdf",
                file_name="corrupted.pdf",
                document_type="PRINT",
            )

        assert "nie posiada prawidłowego nagłówka PDF" in str(exc_info.value)
