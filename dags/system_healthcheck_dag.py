"""DAG Airflow weryfikujący stan zdrowia całego ekosystemu Weryfikator Obietnic.

Sprawdza łączność z bazą PostgreSQL oraz dostępność Sejm OpenAPI.
"""

from datetime import datetime, timedelta
from typing import Any

try:
    from airflow.decorators import dag, task

    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False

    # Fallback atrapy dla środowisk lokalnych bez zainstalowanego Airflow w IDE
    def dag(*args: Any, **kwargs: Any):  # type: ignore[no-redef]
        def decorator(f: Any) -> Any:
            return f

        return decorator

    def task(*args: Any, **kwargs: Any):  # type: ignore[no-redef]
        def decorator(f: Any) -> Any:
            return f

        return decorator


from src.collectors.sejm_api import SejmClient
from src.core.database import db_manager


@dag(
    dag_id="system_healthcheck_dag",
    schedule_interval=timedelta(hours=6),
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["monitoring", "healthcheck", "weryfikator"],
    doc_md=__doc__,
)
def system_healthcheck_pipeline() -> None:
    """Potok orkiestracji weryfikujący stan infrastruktury i serwisów zewnętrznych."""

    @task(task_id="verify_database_connection")
    def verify_database() -> dict[str, Any]:
        """Sprawdza łączność z instancją PostgreSQL oraz poprawność wykonywania zapytań."""
        is_healthy = db_manager.check_health()
        if not is_healthy:
            raise ConnectionError("Baza PostgreSQL nie odpowiada na zapytanie kontrolne.")
        return {"database": "healthy", "timestamp": datetime.utcnow().isoformat()}

    @task(task_id="verify_sejm_openapi")
    def verify_sejm_api() -> dict[str, Any]:
        """Odpytuje Sejm OpenAPI sprawdzając dostępność procesów legislacyjnych."""
        client = SejmClient()
        processes = client.get_legislative_processes(limit=3)
        return {
            "sejm_api": "healthy",
            "sample_count": len(processes),
            "timestamp": datetime.utcnow().isoformat(),
        }

    db_task = verify_database()
    sejm_task = verify_sejm_api()
    db_task >> sejm_task


pipeline = system_healthcheck_pipeline()
