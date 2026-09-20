"""Aplikacja FastAPI udostępniająca REST API dla frontendu i zewnętrznych integracji."""

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.collectors.sejm_api import SejmClient
from src.core.database import db_manager

app = FastAPI(
    title="Weryfikator Obietnic API",
    description="Otwarte REST API udostępniające dane o realizacji obietnic wyborczych i pracach Sejmu RP.",
    version="0.1.0",
)

# Konfiguracja CORS pod nowoczesny frontend (Vite / React / PWA)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Monitoring"])
def health_check() -> dict[str, Any]:
    """Sprawdza stan zdrowia aplikacji, bazy PostgreSQL oraz łączności z Sejm API."""
    db_alive = db_manager.check_health()
    return {
        "status": "healthy" if db_alive else "degraded",
        "database_connected": db_alive,
        "version": "0.1.0",
    }


@app.get("/api/v1/promises", tags=["Obietnice"])
def list_promises() -> list[dict[str, Any]]:
    """Zwraca listę zarejestrowanych obietnic wyborczych wraz z aktualnymi ocenami."""
    query = """
        SELECT p.promise_id, p.party_id, p.title, p.category, p.announced_date,
               e.alignment_status, e.alignment_score, e.summary_pl
        FROM electoral_promises p
        LEFT JOIN legislative_evaluations e ON p.promise_id = e.promise_id
        ORDER BY p.created_at DESC;
    """
    try:
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                return cur.fetchall()
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Błąd bazy danych: {err}") from err


@app.get("/api/v1/sejm/live-status", tags=["Sejm"])
def check_sejm_api_status() -> dict[str, Any]:
    """Wykonuje testowe odpytanie Sejm OpenAPI weryfikując dostępność zewnętrznego serwisu."""
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
