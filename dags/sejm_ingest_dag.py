"""DAG Apache Airflow: Ingestia procesów legislacyjnych i zapis projektów ustaw (Bill) w SQLModel.

Uruchamia się co godzinę (schedule="@hourly"), odpytuje oficjalny Sejm OpenAPI
o najnowsze procesy legislacyjne (X kadencja) za pomocą asynchronicznego klienta SejmApiClient,
sprawdza w bazie PostgreSQL (tabela Bill), czy pojawiły się nowe projekty ustaw i zapisuje je.
"""

import asyncio
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


from sqlmodel import Session, select

from src.api_clients.sejm_client import SejmApiClient
from src.database.engine import get_engine
from src.database.models import Bill

logger = logging.getLogger("airflow.task")


@dag(
    dag_id="sejm_ingest_dag",
    schedule="@hourly",
    start_date=datetime(2024, 1, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    tags=["sejm", "ingest", "bills", "sqlmodel"],
    doc_md=__doc__,
)
def sejm_ingest_pipeline() -> None:
    """Potok orkiestracji Airflow pobierający i strukturyzujący procesy Sejmu RP."""

    @task(retries=3)  # type: ignore[untyped-decorator]
    def fetch_latest_processes(limit: int = 50) -> list[dict[str, Any]]:
        """Zadanie Airflow: Odpytuje Sejm OpenAPI o ostatnie procesy i zwraca serializowalny JSON."""

        async def _fetch() -> list[dict[str, Any]]:
            async with SejmApiClient(term=10) as client:
                processes = await client.get_processes(offset=0, limit=limit)
                return [
                    {
                        "number": str(p.number),
                        "title": p.title,
                        "document_type": p.document_type or "PROJEKT_USTAWY",
                        "change_date": str(p.change_date) if p.change_date else None,
                        "prints": [str(pr) for pr in p.prints],
                    }
                    for p in processes
                ]

        logger.info("Pobieranie najnowszych procesów legislacyjnych z Sejm OpenAPI...")
        processes_data = asyncio.run(_fetch())
        logger.info("Pobrano %d procesów legislacyjnych z API.", len(processes_data))
        return processes_data

    @task  # type: ignore[untyped-decorator]
    def persist_bills_to_database(processes_data: list[dict[str, Any]]) -> dict[str, Any]:
        """Zadanie Airflow: Sprawdza tabelę Bill w SQLModel i zapisuje wyłącznie nowe projekty ustaw."""
        engine = get_engine()
        inserted_bills: list[str] = []

        with Session(engine) as session:
            for item in processes_data:
                prints = item.get("prints", [])
                title = item.get("title", "Projekt ustawy")
                doc_type = item.get("document_type", "USTAWA")

                # Każdy proces może mieć powiązany jeden lub więcej druków sejmowych
                for print_num in prints:
                    bill_id = f"druk-{print_num}"

                    # Weryfikacja czy projekt o danym ID już istnieje w bazie PostgreSQL
                    existing_bill = session.get(Bill, bill_id)
                    if not existing_bill:
                        # Weryfikacja po numerze druku
                        statement = select(Bill).where(Bill.sejm_print_num == str(print_num))
                        existing_by_num = session.exec(statement).first()

                        if not existing_by_num:
                            new_bill = Bill(
                                id=bill_id,
                                sejm_print_num=str(print_num),
                                title=title[:255] if len(title) > 255 else title,
                                status=doc_type,
                                author="Sejm RP",
                                document_url=f"https://www.sejm.gov.pl/Sejm10.nsf/druk.xsp?nr={print_num}",
                            )
                            session.add(new_bill)
                            inserted_bills.append(bill_id)

            session.commit()

        logger.info(
            "Zapisano do bazy PostgreSQL: %d nowych projektów ustaw (Bill).", len(inserted_bills)
        )
        return {
            "total_processes_scanned": len(processes_data),
            "new_bills_inserted": len(inserted_bills),
            "inserted_bill_ids": inserted_bills,
        }

    # Definicja zależności przepływu danych
    fetched_data = fetch_latest_processes()
    persist_bills_to_database(fetched_data)


# Rejestracja instancji DAG
dag_instance = sejm_ingest_pipeline()
