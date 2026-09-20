"""DAG Apache Airflow: Ingestia procesów legislacyjnych i druków z Sejm OpenAPI.

Cyklicznie pobiera listę procesów legislacyjnych X kadencji, porównuje daty zmian
z rekordami w PostgreSQL i pobiera pełne detale oraz powiązane druki dla nowych
lub zaktualizowanych spraw. Zapisuje surowe dane do tabeli stagingowej raw_sejm_data.
"""

from datetime import datetime, timedelta
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

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
                return MockTask(f.__name__)

            wrapper.__name__ = f.__name__
            wrapper.__doc__ = f.__doc__
            return wrapper

        return decorator


from psycopg.types.json import Jsonb

from src.collectors.sejm_api import SejmClient
from src.config import settings
from src.core.database import db_manager
from src.models.sejm_api import SejmProcessRaw


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True,
)
def fetch_details_with_retry(client: SejmClient, process_number: str) -> dict[str, Any]:
    """Pobiera szczegóły procesu z obsługą exponential backoff."""
    return client.get_process_details(process_number)


@dag(
    dag_id="sejm_ingest_dag",
    schedule_interval=timedelta(hours=6),
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["sejm", "ingest", "processes", "prints"],
    doc_md=__doc__,
)
def sejm_ingestion_pipeline() -> None:
    """Potok orkiestracji pobierający i wersjonujący procesy legislacyjne z Sejmu."""

    @task(task_id="fetch_active_processes")
    def fetch_active_processes() -> list[dict[str, Any]]:
        """Pobiera listę procesów z Sejm OpenAPI i waliduje je modelem Pydantic."""
        client = SejmClient()
        raw_list = client.get_legislative_processes(offset=0, limit=200)

        validated_processes: list[dict[str, Any]] = []
        for item in raw_list:
            try:
                proc = SejmProcessRaw.model_validate(item)
                validated_processes.append(
                    {
                        "process_id": proc.process_id,
                        "number": str(proc.number),
                        "term": proc.term,
                        "title": proc.title,
                        "document_type": proc.document_type,
                        "change_date": (
                            proc.change_date.isoformat()
                            if isinstance(proc.change_date, datetime)
                            else str(proc.change_date)
                            if proc.change_date
                            else None
                        ),
                        "prints": [str(p) for p in proc.prints],
                    }
                )
            except Exception:
                continue

        return validated_processes

    @task(task_id="filter_changed_processes")
    def filter_changed_processes(processes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Porównuje pobrane procesy z bazą PostgreSQL i wybiera nowe lub zmodyfikowane."""
        if not processes:
            return []

        existing_records: dict[str, str | None] = {}
        query = "SELECT process_id, change_date FROM legislative_processes WHERE term = %s;"
        try:
            with db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (settings.default_sejm_term,))
                    for row in cur.fetchall():
                        pid = str(row["process_id"])
                        cdate = row["change_date"].isoformat() if row["change_date"] else None
                        existing_records[pid] = cdate
        except Exception:
            # W przypadku świeżej bazy wszystkie rekordy kwalifikujemy jako nowe
            existing_records = {}

        to_update: list[dict[str, Any]] = []
        for proc in processes:
            pid = proc["process_id"]
            incoming_date = proc.get("change_date")
            if pid not in existing_records or existing_records[pid] != incoming_date:
                to_update.append(proc)

        return to_update

    @task(task_id="ingest_process_details_and_prints")
    def ingest_process_details_and_prints(to_update: list[dict[str, Any]]) -> dict[str, int]:
        """Pobiera pełne detale zaktualizowanych procesów oraz druków i zapisuje do bazy."""
        client = SejmClient()
        success_count = 0

        for item in to_update:
            process_num = item["number"]
            process_id = item["process_id"]
            term = item["term"]

            try:
                details = fetch_details_with_retry(client, process_num)

                # 1. Zapis surowego ładunku JSONB do warstwy stagingowej (raw_sejm_data)
                db_manager.insert_raw_sejm_record(
                    endpoint="processes",
                    term=term,
                    external_id=process_id,
                    payload=details,
                )

                # 2. Upsert znormalizowanych danych do tabeli legislative_processes
                upsert_query = """
                    INSERT INTO legislative_processes (
                        process_id, term, title, description, author, author_type,
                        status, change_date, print_numbers, timeline, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (process_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        author = EXCLUDED.author,
                        author_type = EXCLUDED.author_type,
                        status = EXCLUDED.status,
                        change_date = EXCLUDED.change_date,
                        print_numbers = EXCLUDED.print_numbers,
                        timeline = EXCLUDED.timeline,
                        updated_at = CURRENT_TIMESTAMP;
                """
                with db_manager.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            upsert_query,
                            (
                                process_id,
                                term,
                                details.get("title", item.get("title", "")),
                                details.get("description"),
                                details.get("author"),
                                details.get("authorType"),
                                details.get("documentType", "W_TOKU"),
                                item.get("change_date"),
                                Jsonb(details.get("prints", item.get("prints", []))),
                                Jsonb(details.get("stages", [])),
                            ),
                        )
                    conn.commit()
                success_count += 1
            except Exception:
                continue

        return {"processed_count": success_count, "total_candidates": len(to_update)}

    all_procs = fetch_active_processes()
    changed_procs = filter_changed_processes(all_procs)
    ingest_process_details_and_prints(changed_procs)


sejm_dag = sejm_ingestion_pipeline()
