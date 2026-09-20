"""Główny punkt wejściowy (entrypoint) aplikacji FastAPI dla Weryfikatora Obietnic.

Zawiera pełną konfigurację metadanych OpenAPI, middleware ustrukturyzowanego
logowania requestów HTTP (structlog) oraz bezpieczną politykę CORS dla Next.js.
"""

import os
import time
import uuid
from typing import Any

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from src.api.routes import router
from src.collectors.sejm_api import SejmClient
from src.core.database import db_manager
from src.core.logger import configure_logging, get_logger

# Inicjalizacja ustrukturyzowanego loggera
configure_logging()
logger = get_logger("src.api.main")

API_DESCRIPTION = """
# Weryfikator Obietnic API 🇵🇱

Otwarte, zautomatyzowane REST API zderzające deklaracje wyborcze partii politycznych
z realnymi projektami ustaw procedowanymi w **Sejmie RP X Kadencji**.

## Główne Funkcjonalności:
- **Ewaluacja RAG (AI)**: Analiza zgodności normatywnej postulatów ze zwektoryzowanymi artykułami prawnymi (pgvector + Gemini).
- **Time-to-Delivery**: Śledzenie etapów legislacyjnych (od wpłynięcia do Sejmu, przez czytania, aż po podpis Prezydenta RP).
- **Finanse Publiczne**: Szacunki kosztów budżetowych z Ocen Skutków Regulacji (OSR).
- **Profile Poselskie**: Heatmapy frekwencji i zgodności głosowań z linią klubu.
- **Big Picture Dashboard**: Agregacje statystyczne i wskaźnik realizacji obietnic rządu (Government Score).

---
*Projekt open-source dedykowany transparentności życia publicznego i kontroli obywatelskiej.*
"""

TAGS_METADATA = [
    {
        "name": "Obietnice",
        "description": "Katalog deklaracji wyborczych, szczegółowa ocena RAG oraz etapy legislacyjne (Time-to-Delivery).",
    },
    {
        "name": "Analityka",
        "description": "Globalne metryki efektywności rządu (Overall Government Score) oraz średni czas dowiezienia ustawy.",
    },
    {
        "name": "Posłowie",
        "description": "Profile parlamentarzystów, frekwencja oraz dzienne wskaźniki aktywności do heatmap.",
    },
    {
        "name": "Monitoring",
        "description": "Healthcheck bazy danych, statusy dostępności usług i łączność z zewnętrznymi API.",
    },
    {
        "name": "Sejm",
        "description": "Bezpośrednia telemetria i integracja na żywo z oficjalnym Sejm OpenAPI.",
    },
]

app = FastAPI(
    title="Weryfikator Obietnic API",
    description=API_DESCRIPTION,
    version="1.0.0",
    openapi_tags=TAGS_METADATA,
    contact={
        "name": "Zespół Weryfikator Obietnic",
        "url": "https://github.com/FranekJemiolo/weryfikatorobietnic",
        "email": "kontakt@weryfikator-obietnic.pl",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
)


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware przechwytujący każdy request HTTP i rejestrujący telemetrię w JSON."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Generowanie lub propagacja unikalnego ID zapytania
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            http_method=request.method,
            path=request.url.path,
        )

        start_time = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"

        try:
            response = await call_next(request)
            process_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # Wstrzyknięcie nagłówków diagnostycznych
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time_ms}ms"

            log_method = logger.info if response.status_code < 400 else logger.warning
            log_method(
                "http_request_completed",
                status_code=response.status_code,
                duration_ms=process_time_ms,
                client_ip=client_ip,
                user_agent=request.headers.get("User-Agent", "unknown"),
            )
            return response

        except Exception as exc:
            process_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                "http_request_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                duration_ms=process_time_ms,
                client_ip=client_ip,
                exc_info=True,
            )
            raise exc


# Rejestracja middleware ustrukturyzowanego logowania
app.add_middleware(StructuredLoggingMiddleware)

# Bezpieczna konfiguracja CORS pod frontend Next.js / PWA
raw_cors = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000")
allowed_origins = [origin.strip() for origin in raw_cors.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time"],
)

# Podpięcie routera REST API
app.include_router(router)


@app.get("/health", tags=["Monitoring"])
async def health_check() -> dict[str, Any]:
    """Sprawdza stan zdrowia aplikacji, łączność z PostgreSQL i migracje."""
    db_alive = db_manager.check_health()
    return {
        "status": "healthy" if db_alive else "degraded",
        "database_connected": db_alive,
        "version": "1.0.0",
        "service": "weryfikator-obietnic-api",
    }


@app.get("/api/v1/sejm/live-status", tags=["Sejm"])
async def check_sejm_api_status() -> dict[str, Any]:
    """Weryfikuje łączność na żywo z oficjalnym Sejm OpenAPI (api.sejm.gov.pl)."""
    client = SejmClient()
    try:
        processes = client.get_legislative_processes(limit=1)
        return {
            "sejm_api_online": True,
            "sample_processes_fetched": len(processes),
        }
    except Exception as err:
        logger.warning("sejm_api_unreachable", error=str(err))
        return {
            "sejm_api_online": False,
            "error": str(err),
        }
