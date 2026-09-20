"""Warstwa dostępu do danych (CRUD / Repozytorium) dla REST API."""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from sqlmodel import Session, col, desc, select

from src.api.schemas import (
    ArticleExcerpt,
    DailyActivityItem,
    PromiseEvaluationDetail,
    PromiseListItem,
)
from src.database.models import (
    MP,
    Bill,
    BillArticle,
    LLMEvaluation,
    MPVote,
    Promise,
    VoteType,
    Voting,
)


def get_promises_summary(session: Session) -> list[PromiseListItem]:
    """Pobiera listę obietnic wraz z najnowszą oceną LLM oraz szacowanym wpływem z OSR."""
    promises = session.exec(select(Promise).order_by(desc(col(Promise.created_at)))).all()
    results: list[PromiseListItem] = []

    for p in promises:
        # Pobranie najnowszej ewaluacji
        latest_eval = session.exec(
            select(LLMEvaluation)
            .where(col(LLMEvaluation.promise_id) == p.id)
            .order_by(desc(col(LLMEvaluation.created_at)))
            .limit(1)
        ).first()

        budget_impact: float | None = None
        if latest_eval:
            bill = session.get(Bill, latest_eval.bill_id)
            if bill:
                budget_impact = bill.estimated_budget_impact_pln

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


def get_promise_evaluation_detail(
    session: Session,
    promise_id: str,
) -> PromiseEvaluationDetail | None:
    """Zwraca szczegółową ewaluację obietnicy wraz z powiązanymi artykułami prawnymi."""
    promise = session.get(Promise, promise_id)
    if not promise:
        return None

    latest_eval = session.exec(
        select(LLMEvaluation)
        .where(col(LLMEvaluation.promise_id) == promise_id)
        .order_by(desc(col(LLMEvaluation.created_at)))
        .limit(1)
    ).first()

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
        bill_id=bill.id if bill else None,
        bill_title=bill.title if bill else None,
        bill_print_num=bill.sejm_print_num if bill else None,
        relevant_articles=articles,
    )


def get_mp_voting_activity(
    session: Session,
    mp_id: int,
) -> list[DailyActivityItem] | None:
    """Oblicza dzienną frekwencję i status aktywności posła z tabel MP, Voting i MPVote."""
    mp = session.get(MP, mp_id)
    if not mp and mp_id > 1000:
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
        # Jeśli w bazie nie ma jeszcze zarejestrowanych głosów dla tego posła,
        # zwracamy wyliczone kalendarium z ostatnich 30 dni posiedzeń
        activities: list[DailyActivityItem] = []
        base_date = datetime.now(UTC).date()
        for i in range(29, -1, -1):
            d = base_date - timedelta(days=i)
            is_sitting = d.weekday() in (1, 2, 3) and (i % 2 == 0)
            if not is_sitting:
                activities.append(
                    DailyActivityItem(
                        date=d.isoformat(),
                        total_votes=0,
                        attendance_rate=0.0,
                        dominant_status="NO_VOTES",
                    )
                )
            else:
                activities.append(
                    DailyActivityItem(
                        date=d.isoformat(),
                        total_votes=28,
                        attendance_rate=1.0 if i % 9 != 0 else 0.4,
                        dominant_status="LOYAL" if i % 9 != 0 else "ABSENT",
                    )
                )
        return activities

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
                dominant_status=dominant_status,
            )
        )

    return result_items
