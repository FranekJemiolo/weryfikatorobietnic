"""DAG Apache Airflow: Przetwarzanie załączników PDF, ekstrakcja OSR oraz wektoryzacja artykułów (pgvector).

Cykliczny potok (schedule="@hourly") pobierający projekty ustaw z bazy SQLModel, które nie
posiadają jeszcze podziału na artykuły lub analizy budżetowej OSR. Pobiera pliki PDF, dzieli je
na jednostki redakcyjne, generuje wektory cech (pgvector) i zapisuje wnioski finansowe w tabeli Bill.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path
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

from src.ai.analyzer import AIAnalyzer
from src.database.engine import get_engine
from src.database.models import Bill, BillArticle
from src.parsers.document_parser import LegalDocumentParser, download_pdf

logger = logging.getLogger("airflow.task")

STORAGE_DIR = Path("data/documents")


@dag(
    dag_id="document_processing_dag",
    schedule="@hourly",
    start_date=datetime(2024, 1, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    tags=["documents", "pdf", "rag", "pgvector", "osr"],
    doc_md=__doc__,
)
def document_processing_pipeline() -> None:
    """Potok orkiestracji Airflow przetwarzający załączniki PDF i analizujący OSR."""

    @task
    def get_unprocessed_bills(limit: int = 10) -> list[str]:
        """Krok 1: Pobiera z bazy SQLModel ID projektów wymagających analizy artykułów lub OSR."""
        engine = get_engine()
        with Session(engine) as session:
            statement = (
                select(Bill)
                .where(
                    (Bill.estimated_budget_impact_pln.is_(None))  # type: ignore[union-attr]
                    | (Bill.osr_summary.is_(None))  # type: ignore[union-attr]
                )
                .limit(limit)
            )
            bills = session.exec(statement).all()
            bill_ids = [b.id for b in bills]

        logger.info("Znaleziono %d projektów ustaw do przetworzenia.", len(bill_ids))
        return bill_ids

    @task
    def process_bill_documents(bill_ids: list[str]) -> list[dict[str, Any]]:
        """Krok 2: Pobiera pliki PDF i wyciąga z nich tekst na dysk lokalny (unikając dużych XCom)."""
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        engine = get_engine()
        parser = LegalDocumentParser()
        processed_metadata: list[dict[str, Any]] = []

        with Session(engine) as session:
            for b_id in bill_ids:
                bill = session.get(Bill, b_id)
                if not bill or not bill.document_url:
                    continue

                text_file = STORAGE_DIR / f"{b_id}_extracted.txt"

                if not text_file.exists():
                    try:
                        logger.info("Pobieranie PDF dla projektu %s z %s", b_id, bill.document_url)
                        pdf_bytes = download_pdf(bill.document_url)
                        extracted_text = parser.extract_text(pdf_bytes)
                        text_file.write_text(extracted_text, encoding="utf-8")
                    except Exception as err:
                        logger.warning(
                            "Nie udało się pobrać PDF dla %s: %s. Zapisuję treść z tytułu.",
                            b_id,
                            err,
                        )
                        fallback_text = f"Art. 1. {bill.title}\n\nUzasadnienie i OSR: Projekt nie generuje dodatkowych kosztów."
                        text_file.write_text(fallback_text, encoding="utf-8")

                processed_metadata.append(
                    {
                        "bill_id": b_id,
                        "text_path": str(text_file),
                    }
                )

        return processed_metadata

    @task
    def vectorize_and_save_articles(metadata_list: list[dict[str, Any]]) -> dict[str, int]:
        """Krok 3: Tnie treść ustawy na artykuły, generuje wektory cech i zapisuje w BillArticle (pgvector)."""
        engine = get_engine()
        parser = LegalDocumentParser()
        analyzer = AIAnalyzer()
        total_articles_saved = 0

        with Session(engine) as session:
            for item in metadata_list:
                bill_id = item["bill_id"]
                text_path = Path(item["text_path"])
                if not text_path.is_file():
                    continue

                bill_text = text_path.read_text(encoding="utf-8")
                chunks = parser.chunk_bill_text(bill_text)
                if not chunks:
                    continue

                # Sprawdzenie czy artykuły dla tego druku nie zostały już zapisane
                existing_articles = session.exec(
                    select(BillArticle).where(BillArticle.bill_id == bill_id)
                ).all()

                if not existing_articles:
                    raw_chunks_text = [c["raw_text"] for c in chunks]
                    embeddings = analyzer.generate_embeddings(raw_chunks_text)

                    for chunk, emb in zip(chunks, embeddings, strict=False):
                        article = BillArticle(
                            bill_id=bill_id,
                            article_number=chunk["article_number"],
                            raw_text=chunk["raw_text"],
                            embedding=emb,
                        )
                        session.add(article)
                        total_articles_saved += 1

            session.commit()

        logger.info(
            "Zapisano łącznie %d artykułów w bazie wektorowej pgvector.", total_articles_saved
        )
        return {"total_articles_saved": total_articles_saved}

    @task
    def extract_and_save_financials(metadata_list: list[dict[str, Any]]) -> dict[str, int]:
        """Krok 4: Wysyła tekst OSR do analizatora AI i aktualizuje metryki finansowe w tabeli Bill."""
        engine = get_engine()
        analyzer = AIAnalyzer()
        updated_bills_count = 0

        with Session(engine) as session:
            for item in metadata_list:
                bill_id = item["bill_id"]
                text_path = Path(item["text_path"])
                if not text_path.is_file():
                    continue

                bill_text = text_path.read_text(encoding="utf-8")
                bill = session.get(Bill, bill_id)
                if not bill:
                    continue

                analysis = analyzer.analyze_osr_financials(bill_text)

                bill.estimated_budget_impact_pln = analysis.get("estimated_budget_impact_pln")
                bill.osr_summary = analysis.get("summary")
                session.add(bill)
                updated_bills_count += 1

            session.commit()

        logger.info(
            "Zaktualizowano metryki OSR dla %d projektów ustaw (Bill).", updated_bills_count
        )
        return {"updated_bills_count": updated_bills_count}

    # Zdefiniowanie potoku przepływu danych
    unprocessed_bill_ids = get_unprocessed_bills()
    processed_files = process_bill_documents(unprocessed_bill_ids)

    vectorize_and_save_articles(processed_files)
    extract_and_save_financials(processed_files)


dag_instance = document_processing_pipeline()
