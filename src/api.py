from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.collectors.sejm_api import SejmClient
from src.core.database import db_manager


class PromiseStatusResponse(BaseModel):
    """Ustrukturyzowana odpowiedź statusu weryfikacji obietnicy wyborczej dla frontendu."""

    promise_id: str = Field(..., description="Identyfikator obietnicy, np. KO-100K-042")
    promise_title: str = Field(..., description="Tytuł lub zwięzła treść obietnicy wyborczej")
    llm_alignment_status: Literal["W_PELNI", "CZESCIOWO", "SPRZECZNA", "BRAK_POWIAZANIA"] = Field(
        ..., description="Kategoryczna ocena zgodności dokonana przez model LLM"
    )
    llm_justification: str = Field(
        ..., description="Bezstronne, syntetyczne uzasadnienie wygenerowane przez model"
    )
    time_elapsed_days: int = Field(
        ..., description="Liczba dni, które upłynęły od ogłoszenia lub rozpoczęcia kadencji"
    )
    current_stage: str = Field(
        ..., description="Aktualny etap procesu legislacyjnego (np. Druk sejmowy, Podpisana)"
    )
    stage_progress_percent: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Wskaźnik procentowy zaawansowania na ścieżce legislacyjnej (0-100%)",
    )
    divergence_details: str | None = Field(
        default=None,
        description="Precyzyjne wskazanie rozbieżności, wyjątków lub przesunięć czasowych",
    )
    source_print_number: str | None = Field(
        default=None,
        description="Numer druku sejmowego lub oznaczenie projektu w wykazie prac rządu",
    )


# Baza przykładowych zamockowanych odpowiedzi pod testy frontendu PWA
MOCK_PROMISES_STATUS: dict[str, dict[str, Any]] = {
    "KO-100K-042": {
        "promise_id": "KO-100K-042",
        "promise_title": "Podniesienie kwoty wolnej od podatku do 60 000 zł dla osób na skali podatkowej",
        "llm_alignment_status": "CZESCIOWO",
        "llm_justification": "Rząd przedstawił założenia reformy kwoty wolnej, jednak termin jej wdrożenia odroczono poza horyzont pierwszych 100 dni rządu z uwagi na regułę wydatkową UE.",
        "time_elapsed_days": 280,
        "current_stage": "Konsultacje publiczne i uzgodnienia międzyresortowe",
        "stage_progress_percent": 35,
        "divergence_details": "Warunek kwotowy (60 000 zł) został zachowany, lecz pierwotnie deklarowany termin wejścia w życie nie został dotrzymany.",
        "source_print_number": "UD-124",
    },
    "KO-100K-001": {
        "promise_id": "KO-100K-001",
        "promise_title": "Finansowanie procedury in vitro bezpośrednio z budżetu państwa (min. 500 mln zł)",
        "llm_alignment_status": "W_PELNI",
        "llm_justification": "Ustawa o zmianie ustawy o świadczeniach opieki zdrowotnej została uchwalona przez Sejm, Senat i podpisana przez Prezydenta RP.",
        "time_elapsed_days": 310,
        "current_stage": "Ustawa ogłoszona w Dzienniku Ustaw (Wdrożona)",
        "stage_progress_percent": 100,
        "divergence_details": None,
        "source_print_number": "Druk nr 18",
    },
    "TD-GWAR-015": {
        "promise_id": "TD-GWAR-015",
        "promise_title": "Dobrowolny ZUS dla mikroprzedsiębiorców w trudnej sytuacji finansowej",
        "llm_alignment_status": "CZESCIOWO",
        "llm_justification": "Wprowadzono tzw. wakacje składkowe obejmujące 1 miesiąc w roku kalendarzowym, co stanowi realizację ulgową zamiast stałej dobrowolności.",
        "time_elapsed_days": 245,
        "current_stage": "Ustawa podpisana i wdrożona w ZUS",
        "stage_progress_percent": 80,
        "divergence_details": "Ustawa uchwaliła zwolnienie za 1 wybrany miesiąc rocznie, a nie stałą dobrowolność opłacania ubezpieczeń społecznych.",
        "source_print_number": "Druk nr 341",
    },
    "PIS-POL-089": {
        "promise_id": "PIS-POL-089",
        "promise_title": "Wprowadzenie zerowej stawki VAT na podstawowe produkty żywnościowe na stałe",
        "llm_alignment_status": "SPRZECZNA",
        "llm_justification": "Decyzją Ministerstwa Finansów zrezygnowano z przedłużenia tarczy antyinflacyjnej i przywrócono standardową stawkę 5% VAT na żywność.",
        "time_elapsed_days": 180,
        "current_stage": "Decyzja wykonawcza (Zakończono obowiązywanie ulgi)",
        "stage_progress_percent": 100,
        "divergence_details": "Stawka 0% VAT wygasła, powrócono do standardowego opodatkowania 5%, co stoi w sprzeczności z deklaracją stałego utrzymania zerowej stawki.",
        "source_print_number": "Rozporządzenie MF",
    },
}

app = FastAPI(
    title="Weryfikator Obietnic API",
    description="Otwarte REST API udostępniające dane o realizacji obietnic wyborczych i pracach Sejmu RP.",
    version="0.1.0",
)

# Konfiguracja CORS pod nowoczesny frontend (Vite / Next.js / PWA)
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


@app.get(
    "/api/v1/promises/{promise_id}/status",
    response_model=PromiseStatusResponse,
    tags=["Obietnice"],
    summary="Pobiera aktualny status ewaluacji obietnicy i postęp legislacyjny",
)
def get_promise_status(promise_id: str) -> PromiseStatusResponse:
    """Zwraca status weryfikacji LLM oraz postęp legislacyjny dla wskazanej obietnicy.

    W obecnej fazie zwraca dane zamockowane (lub automatycznie generowany stan
    dla dowolnego identyfikatora), co pozwala na testowanie i rozwijanie komponentów
    frontendu PWA bez konieczności ciągłego połączenia z bazą PostgreSQL.
    """
    if promise_id in MOCK_PROMISES_STATUS:
        return PromiseStatusResponse(**MOCK_PROMISES_STATUS[promise_id])

    # Fallback dla dowolnego identyfikatora przekazanego z frontendu
    return PromiseStatusResponse(
        promise_id=promise_id,
        promise_title=f"Weryfikacja obietnicy {promise_id}",
        llm_alignment_status="CZESCIOWO",
        llm_justification=(
            f"Projekt powiązany z obietnicą {promise_id} znajduje się w toku procedowania "
            "parlamentarnego. Trwa weryfikacja zgodności poprawek sejmowych z deklaracją."
        ),
        time_elapsed_days=180,
        current_stage="I Czytanie w Sejmie (Prace w komisjach)",
        stage_progress_percent=45,
        divergence_details="Wstępna analiza tekstu druku sejmowego wykazuje częściową zbieżność.",
        source_print_number="Druk nr 105",
    )


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
