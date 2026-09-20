"""DAG Apache Airflow: Watchdog stron partii politycznych i detekcja cichych modyfikacji.

Cyklicznie (schedule="@daily") audytuje oficjalne strony programowe partii politycznych,
czyści kod HTML z szumu i bada spójność hashy SHA-256 z historią w tabeli PromiseRevision.
Wykryte modyfikacje są rejestrowane jako nowe wersje z natychmiastowym alertem.
"""

import logging
from datetime import UTC, datetime
from typing import Any

try:
    from airflow.decorators import dag, task
except ImportError:
    # Kompatybilność z lokalnym środowiskiem testowym bez zainstalowanego Apache Airflow
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


from src.database.engine import get_engine
from src.scrapers.party_watchdog import PartyWatchdog

logger = logging.getLogger("airflow.task")

# Domyślna lista monitorowanych stron partii i powiązanych deklaracji
DEFAULT_WATCHDOG_TARGETS: list[dict[str, str]] = [
    {
        "url": "https://koalicjaobywatelska.pl/program",
        "promise_id": "KO-100K-042",
    },
    {
        "url": "https://polska2050.pl/gwarancje",
        "promise_id": "TD-GWAR-015",
    },
]


@dag(
    dag_id="party_watchdog_dag",
    schedule="@daily",
    start_date=datetime(2024, 1, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    tags=["watchdog", "parties", "silent-changes", "scraping"],
    doc_md=__doc__,
)
def party_watchdog_pipeline() -> None:
    """Potok orkiestracji Airflow sprawdzający ciche zmiany w obietnicach wyborczych."""

    @task(retries=2)  # type: ignore[untyped-decorator]
    def run_party_watchdog(targets: list[dict[str, str]]) -> list[dict[str, Any]]:
        """Zadanie Airflow: Pobiera strony, czyści HTML i rejestruje rewizje w SQLModel."""
        engine = get_engine()
        watchdog = PartyWatchdog(engine=engine)
        logger.info("Uruchamianie PartyWatchdog dla %d adresów URL...", len(targets))

        results = watchdog.monitor_all(targets)
        logger.info("Zakończono audyt. Przetworzono adresów: %d", len(results))
        return results

    @task  # type: ignore[untyped-decorator]
    def alert_on_silent_changes(audit_results: list[dict[str, Any]]) -> dict[str, int]:
        """Zadanie Airflow: Analizuje wyniki i raportuje liczbę cichych modyfikacji."""
        changed_items = [r for r in audit_results if r.get("is_changed")]
        initial_items = [r for r in audit_results if r.get("is_initial")]

        for item in changed_items:
            logger.warning(
                "🚨 [ALARM - CICHA ZMIANA] Wykryto zmianę deklaracji %s pod adresem: %s (Nowy hash: %s)",
                item.get("promise_id"),
                item.get("url"),
                str(item.get("content_hash", ""))[:8],
            )

        logger.info(
            "Podsumowanie audytu: Nowych stron: %d, Zmienionych (Alert): %d, Bez zmian: %d",
            len(initial_items),
            len(changed_items),
            len(audit_results) - len(changed_items) - len(initial_items),
        )

        return {
            "total_checked": len(audit_results),
            "changed_count": len(changed_items),
            "initial_count": len(initial_items),
        }

    # Zdefiniowanie przepływu zadań w DAG-u
    audit_data = run_party_watchdog(DEFAULT_WATCHDOG_TARGETS)
    alert_on_silent_changes(audit_data)


# Rejestracja instancji DAG w module
dag_instance = party_watchdog_pipeline()
