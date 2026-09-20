"""Testy jednostkowe endpointów REST API FastAPI."""

from fastapi.testclient import TestClient

from src.api import app

client = TestClient(app)


def test_health_check() -> None:
    """Weryfikuje endpoint sprawdzania stanu aplikacji."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database_connected" in data
    assert data["version"] == "0.1.0"


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

