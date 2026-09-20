"""Aplikacja FastAPI wystawiająca otwarte REST API dla frontendu i integracji zewnętrznych."""

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.collectors.sejm_api import SejmClient
from src.core.database import db_manager

app = FastAPI(
    title="Weryfikator Obietnic API",
    description="Otwarte REST API udostępniające dane o realizacji obietnic wyborczych, analizach OSR i pracach Sejmu RP.",
    version="0.2.0",
)

# Konfiguracja CORS pod nowoczesny frontend (PWA / React / Next.js / Vite)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rejestracja routera API v1
app.include_router(router)


@app.get("/health", tags=["Monitoring"])
async def health_check() -> dict[str, Any]:
    """Sprawdza stan zdrowia aplikacji, bazy danych oraz łączności."""
    db_alive = db_manager.check_health()
    return {
        "status": "healthy" if db_alive else "degraded",
        "database_connected": db_alive,
        "version": "0.2.0",
    }


@app.get("/api/v1/sejm/live-status", tags=["Sejm"])
async def check_sejm_api_status() -> dict[str, Any]:
    """Weryfikuje łączność na żywo z oficjalnym Sejm OpenAPI."""
    client = SejmClient()
    try:
        processes = client.get_legislative_processes(limit=1)
        return {
            "sejm_api_online": True,
            "sample_processes_fetched": len(processes),
        }
    except Exception as err:
        return {
            "sejm_api_online": False,
            "error": str(err),
        }
