from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from src.api import app
from src.database.engine import get_session, init_db
from src.database.models import MP, Promise, PromiseStatus

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db() -> Generator[None, None, None]:
    """Inicjalizuje bazę in-memory SQLite ze StaticPool dla endpointów FastAPI."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)

    with Session(engine) as session:
        mp = MP(id=1, first_name="Donald", last_name="Tusk", club="KO", active=True)
        promise = Promise(
            id="KO-01",
            party="KO",
            title="Kwota wolna 60 000 zł",
            full_text="Podniesiemy kwotę wolną od podatku do 60 tys. zł.",
            category="Gospodarka",
            status=PromiseStatus.IN_PROGRESS,
        )
        session.add(mp)
        session.add(promise)
        session.commit()

    def override_get_session() -> Generator[Session, None, None]:
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    yield
    app.dependency_overrides.clear()


def test_health_check() -> None:
    """Weryfikuje endpoint sprawdzania stanu aplikacji oraz nagłówki diagnostyczne middleware."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database_connected" in data
    assert data["version"] == "1.0.0"
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time" in response.headers


def test_get_promises_list() -> None:
    """Weryfikuje pobieranie listy obietnic z zagregowaną oceną i kosztem OSR."""
    response = client.get("/api/v1/promises")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["id"] == "KO-01"


def test_get_promise_evaluation_404() -> None:
    """Weryfikuje obsługę błędu 404 dla nieistniejącej obietnicy."""
    response = client.get("/api/v1/promises/NIE-ISTNIEJE-999/evaluation")
    assert response.status_code == 404
    detail = response.json().get("detail", "")
    assert "Nie znaleziono" in detail


def test_get_mp_voting_activity_endpoint() -> None:
    """Weryfikuje endpoint /api/v1/mps/{id}/voting-activity dla heatmapy."""
    response = client.get("/api/v1/mps/1/voting-activity")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        assert "date" in data[0]
        assert "total_votes" in data[0]
        assert "attendance_rate" in data[0]
        assert "dominant_status" in data[0]


def test_get_promise_status_known_mock() -> None:
    """Weryfikuje pobieranie zamockowanego statusu obietnicy dla znanego ID."""
    response = client.get("/api/v1/promises/KO-100K-042/status")
    assert response.status_code == 200
    data = response.json()

    assert data["promise_id"] == "KO-100K-042"
    assert "kwoty wolnej" in data["promise_title"]
    assert data["llm_alignment_status"] == "CZESCIOWO"
    assert len(data["llm_justification"]) > 10
    assert data["time_elapsed_days"] == 280
    assert "Konsultacje" in data["current_stage"]
    assert 0 <= data["stage_progress_percent"] <= 100
    assert data["source_print_number"] == "UD-124"


def test_get_promise_status_fallback_mock() -> None:
    """Weryfikuje automatyczny mock dla dynamicznego, nieznanego wcześniej ID."""
    test_id = "NOWA-PARTIA-999"
    response = client.get(f"/api/v1/promises/{test_id}/status")
    assert response.status_code == 200
    data = response.json()

    assert data["promise_id"] == test_id
    assert test_id in data["promise_title"]
    assert data["llm_alignment_status"] in ["W_PELNI", "CZESCIOWO", "SPRZECZNA", "BRAK_POWIAZANIA"]
    assert data["time_elapsed_days"] > 0
    assert data["current_stage"]


def test_get_mp_daily_activity() -> None:
    """Weryfikuje pobieranie historii aktywności posła pod kątem heatmapy."""
    response = client.get("/api/v1/mps/42/daily-activity")
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 30

    first_day = data[0]
    assert "date" in first_day
    assert "total_votes" in first_day
    assert "attendance_rate" in first_day
    assert "rebellion_rate" in first_day
    assert first_day["dominant_status"] in [
        "LOYAL",
        "REBELLIOUS",
        "ABSENT",
        "MIXED",
        "NO_VOTES",
    ]


def test_get_promise_timeline_success() -> None:
    """Weryfikuje poprawne pobieranie osi czasu (TimelineEvent) dla istniejącej obietnicy."""
    response = client.get("/api/v1/promises/KO-01/timeline")
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 5
    first_event = data[0]
    assert "date" in first_event
    assert "stage_name" in first_event
    assert "description" in first_event
    assert "is_completed" in first_event
    assert first_event["is_completed"] is True
    assert "Deklaracja programowa" in first_event["stage_name"]


def test_get_promise_timeline_404() -> None:
    """Weryfikuje zwrócenie błędu HTTP 404 dla nieistniejącej obietnicy na osi czasu."""
    response = client.get("/api/v1/promises/NIE-ISTNIEJE-404/timeline")
    assert response.status_code == 404
    error_detail = response.json().get("detail", "")
    assert "Nie znaleziono" in error_detail


def test_get_analytics_summary() -> None:
    """Weryfikuje globalne statystyki rządu z zapytania SQL."""
    response = client.get("/api/v1/analytics/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_promises" in data
    assert "fulfilled_count" in data
    assert "in_progress_count" in data
    assert "broken_count" in data
    assert data["total_promises"] >= 1
    assert data["in_progress_count"] >= 1


def test_search_promises_endpoint() -> None:
    """Weryfikuje działanie wyszukiwarki z parametrami q, party, limit."""
    response = client.get("/api/v1/promises/search?q=Kwota&party=KO&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert data["items"][0]["id"] == "KO-01"

    # Test wyszukiwania z brakiem wyników
    empty_resp = client.get("/api/v1/promises/search?q=ZupelnieNieistniejacaFraza999")
    assert empty_resp.status_code == 200
    assert empty_resp.json()["total"] == 0
    assert empty_resp.json()["items"] == []
