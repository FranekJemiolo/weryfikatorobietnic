"""Testy jednostkowe i integracyjne dla rozszerzeń civic-tech:

1. Interpelacje poselskie i wskaźnik proaktywności (interpellations_count).
2. Poprawki komisji (BillAmendment) i ponowna ewaluacja LLM (requires_re_evaluation).
3. Pre-legislacja w RCL (RCLWatchdog, PreLegislativeProcess) i oś czasu.
4. Hybrydowa weryfikacja (external_factchecks).
"""

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

from dags.external_factcheck_dag import extract_verdict, is_factcheck_matching_promise
from src.api.crud import get_mp_voting_activity, get_promise_timeline
from src.collectors.rss_collector import RSSFeedItemData
from src.database.engine import init_db
from src.database.models import (
    MP,
    AlignmentStatus,
    Bill,
    BillAmendment,
    Committee,
    CommitteeSitting,
    Interpellation,
    LLMEvaluation,
    MPVote,
    PreLegislativeProcess,
    Promise,
    PromiseStatus,
    VoteType,
    Voting,
)
from src.parsers.document_parser import LegalDocumentParser, flag_evaluations_for_re_evaluation
from src.scrapers.rcl_watchdog import RCLWatchdog


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


def test_interpellation_model_and_mp_voting_activity(db_session: Session) -> None:
    """Weryfikuje zapisywanie interpelacji oraz obliczanie interpellations_count w get_mp_voting_activity."""
    mp = MP(id=101, first_name="Klaudia", last_name="Jachira", club="KO", active=True)
    db_session.add(mp)

    day1 = datetime(2024, 3, 10, 10, 0, tzinfo=UTC)
    voting = Voting(
        id=501,
        sitting_num=8,
        voting_num=1,
        date=day1,
        title="Głosowanie nad ustawą budżetową",
    )
    db_session.add(voting)

    vote = MPVote(voting_id=501, mp_id=101, vote_type=VoteType.YES)
    db_session.add(vote)

    # Interpelacja w tym samym dniu
    interp1 = Interpellation(
        id=1001,
        mp_id=101,
        title="Interpelacja w sprawie czystego powietrza w miastach",
        receipt_date=day1,
        is_answered=True,
    )
    # Druga interpelacja w innym dniu (bez głosowań)
    day2 = datetime(2024, 3, 15, 14, 0, tzinfo=UTC)
    interp2 = Interpellation(
        id=1002,
        mp_id=101,
        title="Interpelacja w sprawie ochrony lasów państwowych",
        receipt_date=day2,
        is_answered=False,
    )
    db_session.add(interp1)
    db_session.add(interp2)
    db_session.commit()

    activity = get_mp_voting_activity(db_session, mp_id=101)
    assert activity is not None
    assert len(activity) == 2

    # Dzień 1: obecny na głosowaniu i 1 złożona interpelacja
    item_day1 = next(item for item in activity if item.date == "2024-03-10")
    assert item_day1.total_votes == 1
    assert item_day1.attendance_rate == 1.0
    assert item_day1.interpellations_count == 1

    # Dzień 2: brak głosowań plenarnych, ale aktywny poselsko (1 interpelacja)
    item_day2 = next(item for item in activity if item.date == "2024-03-15")
    assert item_day2.total_votes == 0
    assert item_day2.interpellations_count == 1


def test_committee_models_and_amendments_parsing_and_re_evaluation(db_session: Session) -> None:
    """Weryfikuje modele komisji, parsowanie poprawek ze sprawozdania oraz flagowanie requires_re_evaluation."""
    committee = Committee(id="FPB", name="Komisja Finansów Publicznych")
    sitting = CommitteeSitting(
        id=1, committee_id="FPB", date=datetime(2024, 2, 20, 11, 0, tzinfo=UTC)
    )
    db_session.add(committee)
    db_session.add(sitting)

    bill = Bill(
        id="druk-88",
        sejm_print_num="88",
        title="Projekt ustawy o podatku dochodowym",
        status="W_KOMISJI",
    )
    promise = Promise(
        id="KO-TAX-01",
        party="KO",
        title="Obniżenie podatków",
        full_text="Obniżymy podatek PIT",
        category="Podatki",
        status=PromiseStatus.IN_PROGRESS,
    )
    db_session.add(bill)
    db_session.add(promise)
    db_session.commit()

    evaluation = LLMEvaluation(
        promise_id=promise.id,
        bill_id=bill.id,
        alignment_status=AlignmentStatus.W_PELNI,
        justification="Wstępnie projekt realizuje obietnicę.",
        confidence_score=0.9,
        requires_re_evaluation=False,
    )
    db_session.add(evaluation)
    db_session.commit()

    sample_report_text = """
    DODATKOWE SPRAWOZDANIE KOMISJI FINANSÓW PUBLICZNYCH
    o rządowym projekcie ustawy o podatku dochodowym (druk nr 88).
    Komisja po rozpatrzeniu projektu na posiedzeniu w dniu 20 lutego 2024 r. przedstawia następujące wnioski:

    Poprawka 1.
    w art. 4 ust. 1 skreśla się wyrazy "w terminie 14 dni" i zastępuje "w terminie 30 dni".
    Komisja wnosi o przyjęcie poprawki.

    Wniosek mniejszości nr 2
    w art. 12 dodaje się ust. 5 w brzmieniu: "Zwolnieniu nie podlegają dochody z działalności..."
    Komisja wnosi o odrzucenie wniosku.
    """

    parser = LegalDocumentParser()
    assert parser.is_committee_report(sample_report_text, "Sprawozdanie Komisji") is True

    amendments = parser.parse_committee_report_amendments(sample_report_text)
    assert len(amendments) == 2

    # Poprawka 1 - przyjęta, art. 4
    assert amendments[0]["article_reference"] == "Art. 4"
    assert amendments[0]["is_accepted"] is True
    assert amendments[0]["is_minority_report"] is False

    # Wniosek mniejszości - nieprzyjęty, art. 12
    assert amendments[1]["article_reference"] == "Art. 12"
    assert amendments[1]["is_accepted"] is False
    assert amendments[1]["is_minority_report"] is True

    # Oznaczenie ewaluacji LLM flagą ponownej weryfikacji
    flagged = flag_evaluations_for_re_evaluation(
        db_session, bill_id="druk-88", amendments=amendments
    )
    assert flagged == 1

    # Sprawdzenie w bazie
    updated_eval = db_session.get(LLMEvaluation, evaluation.id)
    assert updated_eval is not None
    assert updated_eval.requires_re_evaluation is True

    saved_amendments = db_session.exec(
        select(BillAmendment).where(BillAmendment.bill_id == "druk-88")
    ).all()
    assert len(saved_amendments) == 2


def test_rcl_watchdog_parser_and_timeline_event(db_session: Session) -> None:
    """Weryfikuje parsowanie projektów RCL oraz obecność etapu pre-legislacji w osi czasu."""
    sample_rcl_html = """
    <html>
      <body>
        <table class="table">
          <tr>
            <th>Numer</th><th>Tytuł</th><th>Etap</th><th>Organ</th><th>Data</th>
          </tr>
          <tr>
            <td><a href="/projekt/12345">UD124</a></td>
            <td>Projekt ustawy o zmianie ustawy o podatku dochodowym od osób fizycznych</td>
            <td>Konsultacje publiczne i uzgodnienia</td>
            <td>Ministerstwo Finansów</td>
            <td>2024-01-10</td>
          </tr>
          <tr>
            <td><a href="/projekt/67890">UC45</a></td>
            <td>Projekt założeń do ustawy o prawie energetycznym</td>
            <td>Opiniowanie</td>
            <td>Ministerstwo Klimatu i Środowiska</td>
            <td>2024-01-12</td>
          </tr>
        </table>
      </body>
    </html>
    """

    watchdog = RCLWatchdog()
    projects = watchdog.parse_projects_from_html(sample_rcl_html)
    assert len(projects) == 2
    assert projects[0]["rcl_id"] == "UD124"
    assert "Konsultacje publiczne" in projects[0]["stage"]
    assert projects[0]["institution"] == "Ministerstwo Finansów"

    # Synchronizacja z bazą
    saved_count = watchdog.sync_with_database(db_session, projects)
    assert saved_count == 2

    # Powiązanie projektu RCL z drukiem sejmowym i obietnicą
    bill = Bill(
        id="druk-99",
        sejm_print_num="99",
        title="Projekt ustawy o podatku",
        status="UCHWALONA",
    )
    db_session.add(bill)
    db_session.commit()

    rcl_proj = db_session.get(PreLegislativeProcess, "UD124")
    assert rcl_proj is not None
    rcl_proj.bill_id = bill.id
    db_session.add(rcl_proj)

    promise = Promise(
        id="KO-TAX-99",
        party="KO",
        title="Podatek kwota wolna",
        full_text="Podniesiemy kwotę wolną",
        category="Podatki",
        status=PromiseStatus.IN_PROGRESS,
        created_at=datetime(2024, 2, 1, tzinfo=UTC),
    )
    db_session.add(promise)
    db_session.commit()

    evaluation = LLMEvaluation(
        promise_id=promise.id,
        bill_id=bill.id,
        alignment_status=AlignmentStatus.W_PELNI,
        justification="Zgodna z deklaracją",
    )
    db_session.add(evaluation)
    db_session.commit()

    # Sprawdzenie osi czasu
    timeline = get_promise_timeline(db_session, promise_id="KO-TAX-99")
    assert timeline is not None
    assert len(timeline) >= 5

    # Pierwszy etap na osi czasu to pre-legislacja w RCL
    first_event = timeline[0]
    assert "Pre-legislacja" in first_event.stage_name
    assert "UD124" in first_event.stage_name
    assert first_event.is_completed is True


def test_factcheck_matching_logic() -> None:
    """Weryfikuje dopasowywanie artykułów fact-checkingowych i ekstrakcję werdyktów."""
    promise = Promise(
        id="KO-WAKACJE-01",
        party="KO",
        title="Wakacje od ZUS dla mikroprzedsiębiorców",
        full_text="Wprowadzimy jeden miesiąc wolny od składek na ubezpieczenie społeczne w roku.",
        category="Gospodarka",
    )

    # 1. Pasujący artykuł z Demagoga
    matching_item = RSSFeedItemData(
        source_name="Demagog",
        feed_url="https://demagog.org.pl/feed/",
        title="Czy rząd wprowadził wakacje od ZUS dla przedsiębiorców? Sprawdzamy stan obietnicy",
        link="https://demagog.org.pl/analizy_i_artykuly/wakacje-od-zus-stan-obietnicy",
        summary="Koalicja zapowiadała miesiąc bez składek. Sejm uchwalił ustawę, która weszła w życie. Werdykt: ZREALIZOWANA.",
        published_at=datetime(2024, 5, 20, tzinfo=UTC),
    )
    assert is_factcheck_matching_promise(matching_item, promise) is True
    assert extract_verdict(matching_item.summary) == "ZREALIZOWANA"

    # 2. Niepasujący artykuł o innej tematyce
    unrelated_item = RSSFeedItemData(
        source_name="OKO.press",
        feed_url="https://oko.press/feed",
        title="Sytuacja na granicy polsko-białoruskiej w maju 2024",
        link="https://oko.press/granica-maj-2024",
        summary="Liczba prób nielegalnego przekroczenia granicy wzrosła w ostatnich tygodniach.",
        published_at=datetime(2024, 5, 21, tzinfo=UTC),
    )
    assert is_factcheck_matching_promise(unrelated_item, promise) is False
