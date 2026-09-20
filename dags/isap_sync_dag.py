"""DAG Apache Airflow: Synchronizacja z Internetowym Systemem Aktów Prawnych (ISAP / Dziennik Ustaw).

Sprawdza, czy projekty ustaw podpisane przez Prezydenta RP lub uchwalone przez parlament
zostały oficjalnie ogłoszone w Dzienniku Ustaw (WDU) i weszły w życie.
Dopiero po potwierdzeniu wejścia w życie w ISAP, status ustawy zmienia się na 'PRAWO OBOWIĄZUJĄCE',
a powiązane z nią obietnice wyborcze uzyskują status 'FULFILLED'.
"""

import logging
from datetime import UTC, datetime
from typing import Any

try:
    from airflow.decorators import dag, task
except ImportError:

    class MockTask:
        def __init__(self, name: str) -> None:
            self.name = name

        def __rshift__(self, other: Any) -> Any:
            return other

        def __lshift__(self, other: Any) -> Any:
            return other

    def dag(*args: Any, **kwargs: Any):  # type: ignore[no-redef]
        def decorator(f: Any) -> Any:
            return f

        return decorator

    def task(*args: Any, **kwargs: Any):  # type: ignore[no-redef]
        def decorator(f: Any) -> Any:
            def wrapper(*call_args: Any, **call_kwargs: Any) -> MockTask:
                return MockTask(getattr(f, "__name__", str(f)))

            wrapper.__name__ = getattr(f, "__name__", str(f))
            wrapper.__doc__ = getattr(f, "__doc__", "")
            return wrapper

        if args and callable(args[0]):
            return decorator(args[0])
        return decorator


from sqlmodel import Session, col, or_, select

from src.api_clients.isap_client import ISAPClient
from src.database.engine import get_engine
from src.database.models import AlignmentStatus, Bill, LLMEvaluation, Promise, PromiseStatus

logger = logging.getLogger("airflow.task")


@dag(
    dag_id="isap_sync_dag",
    schedule="@daily",
    start_date=datetime(2024, 1, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    tags=["isap", "acts", "promulgation", "drogaprawa"],
    doc_md=__doc__,
)
def isap_sync_pipeline() -> None:
    """Potok weryfikujący wejście w życie ustaw w Dzienniku Ustaw (ISAP)."""

    @task(retries=2)  # type: ignore[untyped-decorator]
    def get_candidate_bills() -> list[dict[str, Any]]:
        """Zadanie Airflow: Pobiera projekty ustaw oczekujące na wejście w życie."""
        engine = get_engine()
        candidates: list[dict[str, Any]] = []

        with Session(engine) as session:
            statement = (
                select(Bill)
                .where(
                    or_(
                        col(Bill.status).in_(
                            ["UCHWALONA", "SENAT", "PODPISANA", "OCZEKUJE_NA_OGLOSZENIE"]
                        ),
                        col(Bill.president_signature_date).is_not(None),
                    )
                )
                .where(col(Bill.status) != "PRAWO OBOWIĄZUJĄCE")
            )
            bills = session.exec(statement).all()

            for b in bills:
                candidates.append(
                    {
                        "id": b.id,
                        "title": b.title,
                        "sejm_print_num": b.sejm_print_num,
                        "status": b.status,
                        "isap_publication_id": b.isap_publication_id,
                    }
                )

        logger.info(
            "Znaleziono %d projektów ustaw kandydujących do weryfikacji w ISAP.", len(candidates)
        )
        return candidates

    @task  # type: ignore[untyped-decorator]
    def verify_and_apply_isap_status(candidates: list[dict[str, Any]]) -> dict[str, int]:
        """Zadanie Airflow: Sprawdza ISAP i aktualizuje status ustaw oraz powiązanych obietnic."""
        engine = get_engine()
        client = ISAPClient()
        promulgated_count = 0
        promises_fulfilled_count = 0

        with Session(engine) as session:
            for item in candidates:
                bill_id = item["id"]
                title = item["title"]
                isap_pub_id = item.get("isap_publication_id")

                in_force, publication_id, force_date = client.check_bill_in_force(
                    bill_title=title,
                    isap_publication_id=isap_pub_id,
                )

                if in_force:
                    bill = session.get(Bill, bill_id)
                    if not bill:
                        continue

                    bill.status = "PRAWO OBOWIĄZUJĄCE"
                    if publication_id:
                        bill.isap_publication_id = publication_id
                    session.add(bill)
                    promulgated_count += 1

                    logger.info(
                        "🏛️ [ISAP SUKCES] Ustawa '%s' (Druk: %s) weszła w życie jako '%s'! "
                        "Status zmieniony na PRAWO OBOWIĄZUJĄCE.",
                        bill.title,
                        bill.sejm_print_num,
                        publication_id or "ISAP",
                    )

                    # Kaskadowa aktualizacja powiązanych obietnic na FULFILLED
                    evaluations = session.exec(
                        select(LLMEvaluation)
                        .where(col(LLMEvaluation.bill_id) == bill_id)
                        .where(col(LLMEvaluation.alignment_status) == AlignmentStatus.W_PELNI)
                    ).all()

                    for ev in evaluations:
                        promise = session.get(Promise, ev.promise_id)
                        if promise and promise.status != PromiseStatus.FULFILLED:
                            promise.status = PromiseStatus.FULFILLED
                            promise.updated_at = force_date or datetime.now(UTC)
                            session.add(promise)
                            promises_fulfilled_count += 1
                            logger.info(
                                "🎯 [OBIETNICA SPEŁNIONA] Obietnica %s (%s) uzyskała status FULFILLED "
                                "w oparciu o wejście w życie ustawy %s.",
                                promise.id,
                                promise.title,
                                bill.title,
                            )

            session.commit()

        logger.info(
            "Podsumowanie synchronizacji ISAP: Ustaw wprowadzonych w życie: %d, Obietnic sfinalizowanych: %d",
            promulgated_count,
            promises_fulfilled_count,
        )
        return {
            "promulgated_bills": promulgated_count,
            "fulfilled_promises": promises_fulfilled_count,
        }

    candidates_list = get_candidate_bills()
    verify_and_apply_isap_status(candidates_list)


dag_instance = isap_sync_pipeline()
