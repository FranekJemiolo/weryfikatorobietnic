"""DAG Apache Airflow: Watchdog stron partii politycznych i detekcja cichych modyfikacji.

Cyklicznie pobiera strony programowe zdefiniowane w config/parties.yaml, czyści DOM,
wylicza sumę kontrolną SHA-256 z tekstu merytorycznego i w przypadku wykrycia różnicy
tworzy nową rewizję w bazie PostgreSQL z flagą is_changed=True.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

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


from src.collectors.web_scraper import WebContentTracker
from src.core.database import db_manager


@dag(
    dag_id="party_watchdog_dag",
    schedule_interval=timedelta(hours=12),
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["watchdog", "parties", "silent-changes", "scraping"],
    doc_md=__doc__,
)
def party_watchdog_pipeline() -> None:
    """Potok orkiestracji wykrywający ciche modyfikacje w programach wyborczych partii."""

    @task(task_id="load_monitored_targets")
    def load_monitored_targets() -> list[dict[str, Any]]:
        """Wczytuje listę monitorowanych adresów URL z pliku konfiguracyjnego."""
        config_path = Path("config/parties.yaml").resolve()
        if not config_path.exists():
            return []

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        targets: list[dict[str, Any]] = []
        for party in data.get("parties", []):
            party_id = party.get("id")
            for url_entry in party.get("monitored_urls", []):
                targets.append(
                    {
                        "party_id": party_id,
                        "name": url_entry.get("name"),
                        "url": url_entry.get("url"),
                        "selector": url_entry.get("selector", "main"),
                    }
                )
        return targets

    @task(task_id="audit_party_pages_for_changes")
    def audit_party_pages_for_changes(targets: list[dict[str, Any]]) -> dict[str, int]:
        """Pobiera zawartość, kalkuluje SHA-256 i rejestruje nowe rewizje przy wykryciu zmian."""
        tracker = WebContentTracker()
        changed_count = 0
        unchanged_count = 0
        error_count = 0

        for target in targets:
            party_id = target["party_id"]
            url = target["url"]

            try:
                snapshot = tracker.fetch_and_snapshot(url)
            except Exception:
                error_count += 1
                continue

            # Pobranie ostatniego hasha z bazy danych
            last_hash: str | None = None
            last_rev: int = 0

            lookup_query = """
                SELECT content_hash, revision_number
                FROM party_web_snapshots
                WHERE party_id = %s AND source_url = %s
                ORDER BY detected_at DESC
                LIMIT 1;
            """
            try:
                with db_manager.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(lookup_query, (party_id, url))
                        row = cur.fetchone()
                        if row:
                            last_hash = str(row["content_hash"])
                            last_rev = int(row["revision_number"])
            except Exception:
                pass

            # Jeśli strona jest pobierana po raz pierwszy
            if last_hash is None:
                insert_query = """
                    INSERT INTO party_web_snapshots (
                        party_id, source_url, content_hash, cleaned_markdown, raw_html,
                        is_changed, revision_number, detected_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
                """
                try:
                    with db_manager.get_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                insert_query,
                                (
                                    party_id,
                                    url,
                                    snapshot.content_hash,
                                    snapshot.cleaned_text[:50000],  # Limit wielkości tekstu
                                    snapshot.raw_html[:100000],
                                    False,
                                    1,
                                ),
                            )
                        conn.commit()
                except Exception:
                    pass
                unchanged_count += 1

            elif last_hash != snapshot.content_hash:
                # Wykryto zmianę w treści obietnic!
                insert_query = """
                    INSERT INTO party_web_snapshots (
                        party_id, source_url, content_hash, cleaned_markdown, raw_html,
                        is_changed, revision_number, detected_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
                """
                try:
                    with db_manager.get_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                insert_query,
                                (
                                    party_id,
                                    url,
                                    snapshot.content_hash,
                                    snapshot.cleaned_text[:50000],
                                    snapshot.raw_html[:100000],
                                    True,
                                    last_rev + 1,
                                ),
                            )
                        conn.commit()
                except Exception:
                    pass
                changed_count += 1
            else:
                unchanged_count += 1

        return {
            "changed": changed_count,
            "unchanged": unchanged_count,
            "errors": error_count,
            "total_evaluated": len(targets),
        }

    targets_to_check = load_monitored_targets()
    audit_party_pages_for_changes(targets_to_check)


watchdog_dag = party_watchdog_pipeline()
