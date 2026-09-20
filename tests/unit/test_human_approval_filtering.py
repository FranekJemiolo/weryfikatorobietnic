"""Testy weryfikacji Human-in-the-Loop, transferów poselskich i pól legislacyjnych."""

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

from src.api.main import app
from src.database.engine import get_session, init_db
from src.database.models import (
    MP,
    AlignmentStatus,
    Bill,
    LLMEvaluation,
    MPClubAffiliation,
    Promise,
    PromiseStatus,
)


@pytest.fixture(name="test_engine")
def test_engine_fixture() -> Engine:
    """Tworzy bazę testową w pamięci (SQLite) ze współdzieloną pulą połączeń."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    return engine


@pytest.fixture(name="db_session")
def db_session_fixture(test_engine: Engine) -> Generator[Session, None, None]:
    """Zwraca sesję powiązaną ze współdzieloną bazą testową."""
    with Session(test_engine) as session:
        yield session


def test_human_approval_filtering_in_promises_api(db_session: Session, test_engine: Engine) -> None:
    """Weryfikuje, że endpoint GET /api/v1/promises zwraca tylko oceny zatwierdzone przez człowieka."""
    # Obietnica 1: z oceną zatwierdzoną przez człowieka
    promise_approved = Promise(
        id="KO-APP-001",
        party="KO",
        title="Obietnica zatwierdzona",
        full_text="Treść obietnicy",
        category="Gospodarka",
        status=PromiseStatus.IN_PROGRESS,
    )
    db_session.add(promise_approved)

    # Obietnica 2: z surową oceną LLM (jeszcze niezweryfikowaną przez człowieka)
    promise_raw = Promise(
        id="PIS-RAW-002",
        party="PiS",
        title="Obietnica surowa",
        full_text="Treść obietnicy",
        category="Podatki",
        status=PromiseStatus.IN_PROGRESS,
    )
    db_session.add(promise_raw)
    db_session.commit()

    bill = Bill(
        id="druk-100",
        sejm_print_num="100",
        title="Projekt ustawy budżetowej",
        status="UCHWALONA",
    )
    db_session.add(bill)
    db_session.commit()

    eval1 = LLMEvaluation(
        promise_id="KO-APP-001",
        bill_id=bill.id,
        alignment_status=AlignmentStatus.W_PELNI,
        confidence_score=0.95,
        justification="Zweryfikowane przez eksperta.",
        source_quotes=["Cytat"],
        key_differences=[],
        model_name="gemini-1.5-pro",
        prompt_version="v1.0",
        is_approved_by_human=True,  # Zatwierdzona
    )
    eval2 = LLMEvaluation(
        promise_id="PIS-RAW-002",
        bill_id=bill.id,
        alignment_status=AlignmentStatus.CZESCIOWO,
        confidence_score=0.60,
        justification="Surowy wynik LLM bez zatwierdzenia.",
        source_quotes=["Cytat 2"],
        key_differences=[],
        model_name="gemini-1.5-pro",
        prompt_version="v1.0",
        is_approved_by_human=False,  # Brak zatwierdzenia
    )
    db_session.add(eval1)
    db_session.add(eval2)
    db_session.commit()

    # Konfiguracja klienta testowego z podmianą sesji
    def override_get_session() -> Generator[Session, None, None]:
        with Session(test_engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)

    # 1. Domyślne wywołanie publiczne: only_approved=True
    response = client.get("/api/v1/promises")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2

    # Obietnica 1 ma status W_PELNI
    item_approved = next(i for i in items if i["id"] == "KO-APP-001")
    assert item_approved["latest_alignment_status"] == "W_PELNI"

    # Obietnica 2 NIE powinna ujawniać niezweryfikowanego statusu LLM publicznemu użytkownikowi
    item_unapproved = next(i for i in items if i["id"] == "PIS-RAW-002")
    assert item_unapproved["latest_alignment_status"] is None

    # 2. Wywołanie administracyjne: only_approved=False
    response_all = client.get("/api/v1/promises?only_approved=false")
    assert response_all.status_code == 200
    items_all = response_all.json()
    item_unapproved_all = next(i for i in items_all if i["id"] == "PIS-RAW-002")
    assert item_unapproved_all["latest_alignment_status"] == "CZESCIOWO"

    app.dependency_overrides.clear()


def test_mp_club_affiliation_and_political_transfers(db_session: Session) -> None:
    """Weryfikuje model MPClubAffiliation i historię transferów partyjnych posła."""
    mp = MP(id=42, first_name="Jan", last_name="Kowalski", club="KO", active=True)
    db_session.add(mp)
    db_session.commit()

    # Historia przynależności: najpierw w klubie X, potem transfer do KO
    aff1 = MPClubAffiliation(
        mp_id=mp.id,
        club_name="Polska2050",
        start_date=datetime(2023, 11, 13, tzinfo=UTC),
        end_date=datetime(2024, 6, 1, tzinfo=UTC),
    )
    aff2 = MPClubAffiliation(
        mp_id=mp.id,
        club_name="KO",
        start_date=datetime(2024, 6, 2, tzinfo=UTC),
        end_date=None,  # Aktualna przynależność
    )
    db_session.add(aff1)
    db_session.add(aff2)
    db_session.commit()

    saved_affiliations = db_session.exec(
        select(MPClubAffiliation).where(MPClubAffiliation.mp_id == mp.id)
    ).all()
    assert len(saved_affiliations) == 2
    clubs = [a.club_name for a in saved_affiliations]
    assert "Polska2050" in clubs
    assert "KO" in clubs

    # Weryfikacja relacji zwrotnej
    assert mp.club_affiliations is not None
    assert len(mp.club_affiliations) == 2


def test_bill_legislative_fields(db_session: Session) -> None:
    """Weryfikuje nowe pola legislacyjne w modelu Bill: Senat, Prezydent i ISAP."""
    sig_date = datetime(2024, 4, 15, 12, 0, tzinfo=UTC)
    bill = Bill(
        id="druk-250",
        sejm_print_num="250",
        title="Ustawa o ochronie sygnalistów",
        status="PODPISANA",
        senate_status="PRZYJĘTA_Z_POPRAWKAMI",
        president_signature_date=sig_date,
        isap_publication_id="WDU/2024/928",
    )
    db_session.add(bill)
    db_session.commit()

    saved_bill = db_session.get(Bill, "druk-250")
    assert saved_bill is not None
    assert saved_bill.senate_status == "PRZYJĘTA_Z_POPRAWKAMI"
    assert saved_bill.president_signature_date is not None
    assert saved_bill.president_signature_date.replace(tzinfo=UTC) == sig_date
    assert saved_bill.isap_publication_id == "WDU/2024/928"
