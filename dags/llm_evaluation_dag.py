"""DAG Apache Airflow: Warstwa transformacji (Legal AST) i ewaluacji semantycznej LLM (RAG).

1. extract_and_parse: Przetwarza teksty projektów ustaw i rozbija je na artykuły (LegalTextParser).
2. generate_embeddings: Generuje wektory semantyczne dla artykułów i obietnic (EmbeddingService).
3. rag_matching: Wyszukuje Top-5 relewantnych przepisów dla każdej obietnicy (RAGMatcher).
4. llm_evaluation: Wysyła wyselekcjonowany kontekst do modelu LLM (Structured Outputs)
   i zapisuje ustrukturyzowaną ocenę do tabeli legislative_evaluations, flagując niepewne rekordy.
"""

from datetime import datetime, timedelta
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
                return MockTask(f.__name__)

            wrapper.__name__ = f.__name__
            wrapper.__doc__ = f.__doc__
            return wrapper

        return decorator


from psycopg.types.json import Jsonb

from src.core.database import db_manager
from src.evaluation.embeddings import EmbeddingService, RAGMatcher
from src.evaluation.llm_client import LLMEvaluator
from src.parsers.legal_parser import LegalTextParser, ParsedProvision


@dag(
    dag_id="llm_evaluation_dag",
    schedule_interval=timedelta(hours=6),
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["llm", "rag", "ast", "evaluation", "structured-outputs"],
    doc_md=__doc__,
)
def llm_evaluation_pipeline() -> None:
    """Potok orkiestracji realizujący pełną ścieżkę Legal AST -> RAG -> LLM Evaluation."""

    @task(task_id="extract_and_parse")
    def extract_and_parse() -> list[str]:
        """Wykrywa nieprzetworzone procesy ustawowe i rozbija je na artykuły."""
        query_unparsed = """
            SELECT p.process_id, p.title, p.description
            FROM legislative_processes p
            LEFT JOIN legislative_provisions lp ON p.process_id = lp.process_id
            WHERE lp.id IS NULL
            LIMIT 10;
        """
        parser = LegalTextParser()
        processed_ids: list[str] = []

        try:
            with db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query_unparsed)
                    candidates = cur.fetchall()

                    for cand in candidates:
                        pid = str(cand["process_id"])
                        # W środowisku produkcyjnym pobierany jest załącznik PDF,
                        # tutaj jako źródło łączymy treść i uzasadnienie
                        source_text = (
                            f"{cand['title']}\n\nArt. 1. {cand.get('description') or cand['title']}"
                        )
                        provisions = parser.parse_provisions(source_text)

                        # Jeśli tekst był płaski i nie zawierał nagłówków Art.
                        if not provisions:
                            provisions = [
                                ParsedProvision(
                                    article="Art. 1",
                                    paragraph=None,
                                    text=cand.get("description") or cand["title"],
                                    context_path="Przepisy Ogólne > Art. 1",
                                )
                            ]

                        insert_prov_query = """
                            INSERT INTO legislative_provisions (
                                process_id, print_number, section, chapter, article,
                                paragraph, point, provision_text, context_path
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """
                        for prov in provisions:
                            cur.execute(
                                insert_prov_query,
                                (
                                    pid,
                                    "1",
                                    prov.section,
                                    prov.chapter,
                                    prov.article,
                                    prov.paragraph,
                                    prov.point,
                                    prov.text,
                                    prov.context_path,
                                ),
                            )
                        processed_ids.append(pid)
                conn.commit()
        except Exception:
            pass

        return processed_ids

    @task(task_id="generate_embeddings")
    def generate_embeddings(process_ids: list[str]) -> list[str]:
        """Generuje wektory embeddingów dla wyodrębnionych artykułów ustaw."""
        if not process_ids:
            return []

        embedder = EmbeddingService()
        query_fetch = """
            SELECT id, context_path, provision_text
            FROM legislative_provisions
            WHERE process_id = ANY(%s) AND embedding_vector IS NULL;
        """
        update_query = """
            UPDATE legislative_provisions
            SET embedding_vector = %s
            WHERE id = %s;
        """
        try:
            with db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query_fetch, (process_ids,))
                    rows = cur.fetchall()

                    for r in rows:
                        combined_text = f"{r['context_path']}: {r['provision_text']}"
                        vector = embedder.get_embedding(combined_text)
                        cur.execute(update_query, (Jsonb(vector), r["id"]))
                conn.commit()
        except Exception:
            pass

        return process_ids

    @task(task_id="rag_matching")
    def rag_matching(process_ids: list[str]) -> list[dict[str, Any]]:
        """Dopasowuje obietnice wyborcze do artykułów ustaw i wyłania Top-5 artykułów."""
        if not process_ids:
            return []

        payloads: list[dict[str, Any]] = []
        embedder = EmbeddingService()
        matcher = RAGMatcher(embedding_service=embedder)

        try:
            with db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    # Pobranie Złotej Bazy Obietnic
                    cur.execute("SELECT promise_id, title, raw_text FROM electoral_promises;")
                    promises = cur.fetchall()

                    for pid in process_ids:
                        # Pobranie artykułów dla danego procesu
                        cur.execute(
                            """
                            SELECT article, paragraph, point, section, chapter,
                                   provision_text, context_path
                            FROM legislative_provisions
                            WHERE process_id = %s;
                            """,
                            (pid,),
                        )
                        prov_rows = cur.fetchall()
                        parsed_provs = [
                            ParsedProvision(
                                article=p["article"],
                                paragraph=p["paragraph"],
                                point=p["point"],
                                section=p["section"],
                                chapter=p["chapter"],
                                text=p["provision_text"],
                                context_path=p["context_path"],
                            )
                            for p in prov_rows
                        ]

                        for prom in promises:
                            top_matches = matcher.select_top_relevant_provisions(
                                promise_text=prom["raw_text"],
                                provisions=parsed_provs,
                                top_k=5,
                            )
                            if top_matches:
                                payloads.append(
                                    {
                                        "promise_id": prom["promise_id"],
                                        "promise_text": prom["raw_text"],
                                        "project_id": pid,
                                        "provisions": [
                                            {
                                                "article": p.article,
                                                "paragraph": p.paragraph,
                                                "text": p.text,
                                                "context_path": p.context_path,
                                            }
                                            for p, _ in top_matches
                                        ],
                                    }
                                )
        except Exception:
            pass

        return payloads

    @task(task_id="llm_evaluation")
    def llm_evaluation(payloads: list[dict[str, Any]]) -> dict[str, int]:
        """Odpytuje model LLM z Structured Outputs i zapisuje wynik do tabeli ewaluacji."""
        evaluator = LLMEvaluator()
        success_count = 0
        review_count = 0

        upsert_eval_query = """
            INSERT INTO legislative_evaluations (
                promise_id, process_id, alignment_status, alignment_score,
                justification, divergence_details, confidence_score,
                requires_manual_review, evaluated_provisions, model_name,
                evaluated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO NOTHING;
        """

        for item in payloads:
            prov_objs = [
                ParsedProvision(
                    article=p["article"],
                    paragraph=p.get("paragraph"),
                    text=p["text"],
                    context_path=p["context_path"],
                )
                for p in item["provisions"]
            ]
            result = evaluator.evaluate(
                promise_id=item["promise_id"],
                promise_text=item["promise_text"],
                project_id=item["project_id"],
                provisions=prov_objs,
            )

            try:
                with db_manager.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            upsert_eval_query,
                            (
                                result.promise_id,
                                result.project_id,
                                result.alignment_status,
                                result.alignment_score,
                                result.justification,
                                result.divergence_details,
                                result.confidence_score,
                                result.requires_manual_review,
                                Jsonb(result.evaluated_provisions),
                                "gemini-1.5-flash",
                            ),
                        )
                    conn.commit()
                success_count += 1
                if result.requires_manual_review:
                    review_count += 1
            except Exception:
                continue

        return {
            "evaluated_count": success_count,
            "flagged_for_review": review_count,
            "total_payloads": len(payloads),
        }

    parsed_ids = extract_and_parse()
    embedded_ids = generate_embeddings(parsed_ids)
    eval_payloads = rag_matching(embedded_ids)
    llm_evaluation(eval_payloads)


evaluation_dag = llm_evaluation_pipeline()
