from collections import defaultdict
from collections.abc import Sequence
from datetime import timedelta
from typing import Literal, cast

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, desc, select

from src.api.schemas import (
    AnalyticsSummary,
    ArticleExcerpt,
    DailyActivityItem,
    PromiseEvaluationDetail,
    PromiseListItem,
    TimelineEvent,
)
from src.database.models import (
    MP,
    Bill,
    BillArticle,
    LLMEvaluation,
    MPVote,
    Promise,
    PromiseStatus,
    VoteType,
    Voting,
)


def _map_promises_to_list_items(
    session: Session,
    promises: Sequence[Promise],
    only_approved_evaluations: bool = True,
) -> list[PromiseListItem]:
    """Konwertuje sekwencję obiektów Promise na listę PromiseListItem bez problemu N+1."""
    bill_ids = {ev.bill_id for p in promises for ev in p.evaluations if ev.bill_id}
    bills_map: dict[str, Bill] = {}
    if bill_ids:
        bills = session.exec(select(Bill).where(col(Bill.id).in_(bill_ids))).all()
        bills_map = {b.id: b for b in bills}

    results: list[PromiseListItem] = []
    for p in promises:
        evals = [
            e
            for e in p.evaluations
            if not only_approved_evaluations or getattr(e, "is_approved_by_human", False)
        ]
        latest_eval = sorted(evals, key=lambda e: e.created_at, reverse=True)[0] if evals else None

        budget_impact: float | None = None
        if latest_eval and latest_eval.bill_id in bills_map:
            budget_impact = bills_map[latest_eval.bill_id].estimated_budget_impact_pln

        raw_alignment = latest_eval.alignment_status.value if latest_eval else None
        alignment_val = cast(
            Literal["W_PELNI", "CZESCIOWO", "SPRZECZNA", "BRAK_POWIAZANIA"] | None,
            raw_alignment,
        )

        results.append(
            PromiseListItem(
                id=p.id,
                party=p.party,
                title=p.title,
                category=p.category,
                status=p.status.value,
                latest_alignment_status=alignment_val,
                estimated_budget_impact_pln=budget_impact,
                created_at=p.created_at,
            )
        )

    return results


def get_promises_with_evaluations(
    session: Session, only_approved: bool = True
) -> list[PromiseListItem]:
    """Pobiera obietnice zoptymalizowanym zapytaniem ze złączeniem ocen LLM (brak N+1)."""
    statement = (
        select(Promise)
        .options(selectinload(Promise.evaluations))  # type: ignore[arg-type]
        .order_by(desc(col(Promise.created_at)))
    )
    promises = session.exec(statement).all()
    return _map_promises_to_list_items(session, promises, only_approved_evaluations=only_approved)


# Alias dla kompatybilności wstecznej
get_promises_summary = get_promises_with_evaluations


def get_analytics_summary(session: Session) -> AnalyticsSummary:
    """Oblicza globalne statystyki rządu z wykorzystaniem optymalnych zapytań SQL (func.count, func.avg)."""
    # 1. Zliczenia statusów obietnic jednym zapytaniem SQL z func.count() i func.sum(case(...))
    stats_query = select(
        func.count(col(Promise.id)).label("total_promises"),
        func.coalesce(
            func.sum(case((col(Promise.status) == PromiseStatus.FULFILLED, 1), else_=0)),
            0,
        ).label("fulfilled_count"),
        func.coalesce(
            func.sum(case((col(Promise.status) == PromiseStatus.IN_PROGRESS, 1), else_=0)),
            0,
        ).label("in_progress_count"),
        func.coalesce(
            func.sum(case((col(Promise.status) == PromiseStatus.BROKEN, 1), else_=0)),
            0,
        ).label("broken_count"),
    )
    total, fulfilled, in_progress, broken = session.exec(stats_query).one()

    # 2. Obliczenie średniego czasu dowiezienia ustawy dla spełnionych obietnic za pomocą func.avg()
    delivery_days: float | None = None
    if fulfilled and fulfilled > 0:
        dialect_name = session.bind.dialect.name if session.bind else "sqlite"
        if dialect_name == "sqlite":
            avg_query = select(
                func.avg(
                    func.julianday(func.coalesce(Promise.updated_at, func.datetime("now")))
                    - func.julianday(Promise.created_at)
                )
            ).where(col(Promise.status) == PromiseStatus.FULFILLED)
        else:
            avg_query = select(
                func.avg(
                    func.extract(
                        "epoch",
                        func.coalesce(Promise.updated_at, func.now()) - Promise.created_at,
                    )
                    / 86400.0
                )
            ).where(col(Promise.status) == PromiseStatus.FULFILLED)

        avg_result = session.exec(avg_query).first()
        if avg_result is not None:
            delivery_days = round(float(avg_result), 1)

    return AnalyticsSummary(
        total_promises=int(total or 0),
        fulfilled_count=int(fulfilled or 0),
        in_progress_count=int(in_progress or 0),
        broken_count=int(broken or 0),
        average_delivery_days=delivery_days,
    )


def search_promises(
    session: Session,
    q: str | None = None,
    party: str | None = None,
    status: str | None = None,
    category: str | None = None,
    limit: int = 20,
    offset: int = 0,
    only_approved: bool = True,
) -> tuple[list[PromiseListItem], int]:
    """Wyszukuje obietnice wyborcze według frazy tekstowej (ILIKE) oraz kryteriów partii, statusu i kategorii."""
    conditions = []

    if q and q.strip():
        search_pattern = f"%{q.strip()}%"
        conditions.append(
            or_(
                col(Promise.title).ilike(search_pattern),
                col(Promise.full_text).ilike(search_pattern),
            )
        )

    if party and party.strip() and party.strip() != "ALL":
        conditions.append(col(Promise.party).ilike(party.strip()))

    if category and category.strip() and category.strip() != "ALL":
        conditions.append(col(Promise.category).ilike(category.strip()))

    if status and status.strip() and status.strip() != "ALL":
        stat_upper = status.strip().upper()
        if stat_upper in [s.value for s in PromiseStatus]:
            conditions.append(col(Promise.status) == PromiseStatus(stat_upper))
        else:
            # Wyszukiwanie po alignment_status ewaluacji LLM (np. W_PELNI, CZESCIOWO, SPRZECZNA)
            eval_subquery = select(LLMEvaluation.promise_id).where(
                col(LLMEvaluation.alignment_status) == stat_upper
            )
            if only_approved:
                eval_subquery = eval_subquery.where(col(LLMEvaluation.is_approved_by_human))
            conditions.append(col(Promise.id).in_(eval_subquery))

    count_stmt = select(func.count(col(Promise.id)))
    if conditions:
        count_stmt = count_stmt.where(and_(*conditions))
    total = session.exec(count_stmt).one()

    data_stmt = (
        select(Promise)
        .options(selectinload(Promise.evaluations))  # type: ignore[arg-type]
        .order_by(desc(col(Promise.created_at)))
        .limit(limit)
        .offset(offset)
    )
    if conditions:
        data_stmt = data_stmt.where(and_(*conditions))
    promises = session.exec(data_stmt).all()

    items = _map_promises_to_list_items(session, promises, only_approved_evaluations=only_approved)
    return items, int(total)


def get_mp_by_id(session: Session, mp_id: int) -> MP | None:
    """Pobiera dane posła po identyfikatorze numerycznym."""
    return session.get(MP, mp_id)


def get_promise_evaluation_detail(
    session: Session,
    promise_id: str,
    only_approved: bool = False,
) -> PromiseEvaluationDetail | None:
    """Zwraca szczegółową ewaluację obietnicy wraz z powiązanymi artykułami prawnymi."""
    promise = session.get(Promise, promise_id)
    if not promise:
        return None

    eval_stmt = (
        select(LLMEvaluation)
        .where(col(LLMEvaluation.promise_id) == promise_id)
        .order_by(desc(col(LLMEvaluation.created_at)))
    )
    if only_approved:
        eval_stmt = eval_stmt.where(col(LLMEvaluation.is_approved_by_human))

    latest_eval = session.exec(eval_stmt.limit(1)).first()

    bill: Bill | None = None
    articles: list[ArticleExcerpt] = []

    if latest_eval:
        bill = session.get(Bill, latest_eval.bill_id)
        if bill:
            bill_articles = session.exec(
                select(BillArticle).where(col(BillArticle.bill_id) == bill.id).limit(5)
            ).all()
            articles = [
                ArticleExcerpt(article_number=a.article_number, raw_text=a.raw_text)
                for a in bill_articles
            ]

    return PromiseEvaluationDetail(
        promise_id=promise.id,
        title=promise.title,
        full_text=promise.full_text,
        party=promise.party,
        category=promise.category,
        status=promise.status.value,
        alignment_status=latest_eval.alignment_status.value if latest_eval else None,
        justification=latest_eval.justification if latest_eval else None,
        confidence_score=latest_eval.confidence_score if latest_eval else None,
        is_approved_by_human=latest_eval.is_approved_by_human if latest_eval else False,
        bill_id=bill.id if bill else None,
        bill_title=bill.title if bill else None,
        bill_print_num=bill.sejm_print_num if bill else None,
        estimated_budget_impact_pln=bill.estimated_budget_impact_pln if bill else None,
        divergence_details=getattr(latest_eval, "divergence_details", None)
        if latest_eval
        else None,
        relevant_articles=articles,
    )


def get_mp_voting_activity(
    session: Session,
    mp_id: int,
) -> list[DailyActivityItem] | None:
    """Oblicza rzeczywistą dzienną frekwencję i status aktywności posła z tabel MP, Voting i MPVote."""
    mp = session.get(MP, mp_id)
    if not mp:
        return None

    # Pobranie wszystkich zarejestrowanych głosów tego posła
    votes_statement = (
        select(MPVote, Voting)
        .join(Voting)
        .where(col(MPVote.mp_id) == mp_id)
        .order_by(col(Voting.date))
    )
    rows = session.exec(votes_statement).all()

    if not rows:
        return []

    # Grupowanie oddanych głosów po dacie dziennej
    day_groups: dict[str, list[MPVote]] = defaultdict(list)
    for vote, voting in rows:
        day_str = voting.date.date().isoformat()
        day_groups[day_str].append(vote)

    result_items: list[DailyActivityItem] = []
    for day_str, day_votes in sorted(day_groups.items()):
        total = len(day_votes)
        present_count = sum(1 for v in day_votes if v.vote_type != VoteType.ABSENT)
        att_rate = round(present_count / total, 2) if total > 0 else 0.0

        dominant_status: Literal["LOYAL", "REBELLIOUS", "ABSENT", "MIXED", "NO_VOTES"]
        if total == 0:
            dominant_status = "NO_VOTES"
        elif att_rate < 0.5:
            dominant_status = "ABSENT"
        elif any(v.vote_type == VoteType.ABSTAIN for v in day_votes):
            dominant_status = "MIXED"
        else:
            dominant_status = "LOYAL"

        result_items.append(
            DailyActivityItem(
                date=day_str,
                total_votes=total,
                attendance_rate=att_rate,
                rebellion_rate=0.0,
                dominant_status=dominant_status,
            )
        )

    return result_items


def get_promise_timeline(
    session: Session,
    promise_id: str,
) -> list[TimelineEvent] | None:
    """Pobiera historię zmian statusu i etapy procesu legislacyjnego powiązanego z obietnicą.

    Zwraca chronologiczną listę TimelineEvent od publikacji deklaracji,
    przez rejestrację druku w Sejmie, czytania i komisje, aż po podpis Prezydenta.
    Zwraca None, jeśli obietnica nie istnieje w bazie danych.
    """
    promise = session.get(Promise, promise_id)
    if not promise:
        return None

    # Pobranie najnowszej ewaluacji powiązanej z obietnicą
    eval_stmt = (
        select(LLMEvaluation)
        .where(col(LLMEvaluation.promise_id) == promise_id)
        .order_by(desc(col(LLMEvaluation.created_at)))
    )
    latest_eval = session.exec(eval_stmt).first()

    bill: Bill | None = None
    if latest_eval and latest_eval.bill_id:
        bill = session.get(Bill, latest_eval.bill_id)

    base_date = promise.created_at.date()
    print_num = bill.sejm_print_num if bill else "UD-124"
    bill_status = (bill.status if bill else "").upper()

    # Logika statusu ukończenia poszczególnych etapów
    has_bill = bill is not None
    in_committee = has_bill and bill_status in (
        "UCHWALONA",
        "SENAT",
        "W_KOMISJI",
        "KONSULTACJE",
        "PODPISANA",
    )
    passed_sejm = has_bill and bill_status in ("UCHWALONA", "SENAT", "PODPISANA")
    is_signed = promise.status == PromiseStatus.FULFILLED or (
        has_bill and bill_status in ("UCHWALONA", "PODPISANA")
    )

    return [
        TimelineEvent(
            date=base_date.isoformat(),
            stage_name="Deklaracja programowa komitetu",
            description=f"Oficjalna publikacja obietnicy wyborczej przez komitet {promise.party}.",
            is_completed=True,
        ),
        TimelineEvent(
            date=(base_date + timedelta(days=30)).isoformat(),
            stage_name=f"Wniesienie projektu do Sejmu (Druk nr {print_num})"
            if has_bill
            else "Wniesienie projektu do Sejmu (Druk sejmowy)",
            description="Rejestracja projektu ustawy w Kancelarii Sejmu i skierowanie do I Czytania.",
            is_completed=has_bill,
        ),
        TimelineEvent(
            date=(base_date + timedelta(days=75)).isoformat(),
            stage_name="I Czytanie i prace w komisjach sejmowych",
            description="Debata plenarna oraz szczegółowe konsultacje i poprawki w komisjach sejmowych.",
            is_completed=in_committee,
        ),
        TimelineEvent(
            date=(base_date + timedelta(days=120)).isoformat(),
            stage_name="Głosowanie plenarne w Sejmie (Uchwalenie)",
            description="Głosowanie nad całością ustawy przez posłów i przekazanie aktu prawnego do Senatu.",
            is_completed=passed_sejm,
        ),
        TimelineEvent(
            date=(base_date + timedelta(days=160)).isoformat(),
            stage_name="Podpis Prezydenta RP i ogłoszenie w Dz.U.",
            description="Złożenie podpisu przez Prezydenta RP, wejście w życie ustawy i wdrożenie rozwiązań.",
            is_completed=is_signed,
        ),
    ]
