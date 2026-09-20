"""DAG Apache Airflow: Ewaluacja semantyczna projektów ustaw względem obietnic (RAG + LLM).

Potok uruchamiany po dodaniu nowych projektów ustaw (lub wyzwalany automatycznie),
który kojarzy aktywne deklaracje wyborcze z przetworzonymi ustawami, wykonuje wyszukiwanie
semantyczne w pgvector i zapisuje ustrukturyzowane oceny w tabeli LLMEvaluation.
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

    def dag(*args: Any, **kwargs: Any):
        def decorator(f: Any) -> Any:
            return f

        return decorator

    def task(*args: Any, **kwargs: Any):
        def decorator(f: Any) -> Any:
            def wrapper(*call_args: Any, **call_kwargs: Any) -> MockTask:
                return MockTask(getattr(f, "__name__", str(f)))

            wrapper.__name__ = getattr(f, "__name__", str(f))
            wrapper.__doc__ = getattr(f, "__doc__", "")
            return wrapper

        if args and callable(args[0]):
            return decorator(args[0])
        return decorator


from sqlmodel import Session, select

from src.ai.evaluator import PromiseEvaluator
from src.database.engine import get_engine
from src.database.models import Bill, BillArticle, Promise, PromiseStatus

logger = logging.getLogger("airflow.task")


@dag(
    dag_id="evaluation_dag",
    schedule="@daily",
    start_date=datetime(2024, 1, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    tags=["evaluation", "rag", "llm", "promises"],
    doc_md=__doc__,
)
def evaluation_pipeline() -> None:
    """Potok orkiestracji Airflow realizujący ewaluację ustaw z obietnicami."""

    @task
    def get_candidate_pairs() -> list[dict[str, str]]:
        """Wyszukuje projekty ustaw z artykułami oraz aktywne obietnice."""
        engine = get_engine()
        pairs: list[dict[str, str]] = []

        with Session(engine) as session:
            # Aktywne obietnice wyborcze
            promises = session.exec(
                select(Promise).where(
                    Promise.status.in_([PromiseStatus.NEW, PromiseStatus.IN_PROGRESS])  # type: ignore[attr-defined]
                )
            ).all()

            # Projekty ustaw posiadające wygenerowane artykuły do RAG
            bills = session.exec(select(Bill).join(BillArticle).distinct()).all()

            for bill in bills:
                for promise in promises:
                    pairs.append(
                        {
                            "promise_id": promise.id,
                            "bill_id": bill.id,
                        }
                    )

        logger.info("Wyznaczono %d par (Obietnica, Ustawa) do ewaluacji RAG.", len(pairs))
        return pairs

    @task
    def run_rag_evaluations(pairs: list[dict[str, str]]) -> dict[str, int]:
        """Krzyżuje pary i wywołuje silnik PromiseEvaluator zapisując wynik w bazie."""
        engine = get_engine()
        evaluator = PromiseEvaluator(engine=engine)
        evaluated_count = 0

        for pair in pairs:
            p_id = pair["promise_id"]
            b_id = pair["bill_id"]
            try:
                evaluator.evaluate_and_persist(promise_id=p_id, bill_id=b_id, top_k=5)
                evaluated_count += 1
                logger.info("Pomyślnie oceniono relację: Obietnica %s <-> Projekt %s", p_id, b_id)
            except Exception as err:
                logger.error("Błąd ewaluacji pary (%s, %s): %s", p_id, b_id, err)

        return {
            "total_pairs": len(pairs),
            "evaluated_count": evaluated_count,
        }

    candidate_pairs = get_candidate_pairs()
    run_rag_evaluations(candidate_pairs)


dag_instance = evaluation_pipeline()
