"""Testy jednostkowe schematu bazy danych SQLModel i relacji ORM."""

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from sqlmodel import Session, create_engine, select

from src.database.engine import init_db
from src.database.models import (
    MP,
    AlignmentStatus,
    Bill,
    LLMEvaluation,
    MPVote,
    Promise,
    PromiseStatus,
    VoteType,
    Voting,
)


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    """Tworzy czystą sesję bazy danych w pamięci (SQLite) na czas trwania testu."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    init_db(engine)
    with Session(engine) as session:
        yield session


def test_create_mp_and_voting_with_vote(session: Session) -> None:
    """Weryfikuje tworzenie posła, głosowania oraz relacji asocjacyjnej MPVote."""
    mp = MP(id=1, first_name="Donald", last_name="Tusk", club="KO", active=True)
    session.add(mp)

    voting = Voting(
        id=100,
        sitting_num=10,
        voting_num=25,
        date=datetime.now(UTC),
        title="Głosowanie nad ustawą o in vitro",
    )
    session.add(voting)
    session.commit()

    mp_vote = MPVote(voting_id=voting.id, mp_id=mp.id, vote_type=VoteType.YES)
    session.add(mp_vote)
    session.commit()

    saved_vote = session.exec(select(MPVote).where(MPVote.mp_id == mp.id)).first()
    assert saved_vote is not None
    assert saved_vote.vote_type == VoteType.YES
    assert saved_vote.mp is not None
    assert saved_vote.mp.last_name == "Tusk"
    assert saved_vote.voting is not None
    assert saved_vote.voting.title == "Głosowanie nad ustawą o in vitro"


def test_promise_bill_and_llm_evaluation_relationship(session: Session) -> None:
    """Weryfikuje relacje między obietnicą, projektem ustawy a ewaluacją LLM."""
    promise = Promise(
        id="KO-100K-001",
        party="KO",
        title="Finansowanie procedury in vitro",
        full_text="Przywrócimy pełne państwowe finansowanie procedury in vitro.",
        category="Zdrowie",
        status=PromiseStatus.FULFILLED,
    )
    session.add(promise)

    bill = Bill(
        id="druk-18",
        sejm_print_num="18",
        title="Ustawa o zmianie ustawy o świadczeniach opieki zdrowotnej",
        status="UCHWALONA",
        author="Obywatelski",
    )
    session.add(bill)
    session.commit()

    eval_record = LLMEvaluation(
        promise_id=promise.id,
        bill_id=bill.id,
        alignment_status=AlignmentStatus.W_PELNI,
        justification="Ustawa w całości realizuje finansowanie ze środków budżetowych.",
        confidence_score=0.98,
    )
    session.add(eval_record)
    session.commit()

    retrieved = session.exec(
        select(LLMEvaluation).where(LLMEvaluation.promise_id == promise.id)
    ).first()
    assert retrieved is not None
    assert retrieved.alignment_status == AlignmentStatus.W_PELNI
    assert retrieved.promise is not None
    assert retrieved.promise.category == "Zdrowie"
    assert retrieved.bill is not None
    assert retrieved.bill.sejm_print_num == "18"
