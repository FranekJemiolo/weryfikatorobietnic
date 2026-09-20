"""DAG Apache Airflow: Pobieranie zewnętrznych weryfikacji fact-checkingowych (Demagog, OKO.press, Konkret24).

Integruje niezależne źródła fact-checkingowe z naszą bazą obietnic wyborczych (Promise.external_factchecks).
Dzięki temu obywatele widzą hybrydową weryfikację:
1. Ocena semantyczna LLM na podstawie twardego prawa (RCL, Sejm, ISAP).
2. Niezależne analizy organizacji fact-checkingowych (np. Demagog, OKO.press).
"""

import logging
import re
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


from sqlmodel import Session, select

from src.collectors.rss_collector import RSSCollector, RSSFeedItemData
from src.database.engine import get_engine
from src.database.models import Promise

logger = logging.getLogger("airflow.task")

# Lista zaufanych źródeł fact-checkingowych i publicystyczno-analitycznych w Polsce
FACTCHECK_FEEDS: list[dict[str, str]] = [
    {
        "name": "Demagog",
        "url": "https://demagog.org.pl/feed/",
    },
    {
        "name": "OKO.press",
        "url": "https://oko.press/feed",
    },
    {
        "name": "Konkret24",
        "url": "https://konkret24.tvn24.pl/feed/rss",
    },
]

POLISH_STOPWORDS = {
    "i",
    "w",
    "na",
    "do",
    "z",
    "ze",
    "o",
    "dla",
    "się",
    "że",
    "to",
    "jak",
    "od",
    "po",
    "za",
    "przez",
    "lub",
    "albo",
    "czy",
    "oraz",
    "nie",
    "tak",
    "jest",
    "są",
    "będzie",
    "będą",
    "ustawa",
    "projekt",
    "rząd",
    "sejm",
    "sto",
    "100",
    "dni",
    "dniu",
    "lat",
    "zł",
    "złotych",
    "tys",
    "tysięcy",
}


def extract_verdict(text: str) -> str:
    """Rozpoznaje werdykt fact-checkingowy na podstawie słów kluczowych w tytule lub treści."""
    upper = text.upper()
    if "FAŁSZ" in upper or "FALSZ" in upper:
        return "FAŁSZ"
    if "PRAWDA" in upper:
        return "PRAWDA"
    if "MANIPULACJA" in upper:
        return "MANIPULACJA"
    if "CZĘŚCIOWO PRAWDA" in upper or "CZESCIOWO PRAWDA" in upper:
        return "CZĘŚCIOWO PRAWDA"
    if "NIEPRAWDA" in upper:
        return "FAŁSZ"
    if "OBETNICA ZŁAMANA" in upper or "ZŁAMANA" in upper:
        return "ZŁAMANA"
    if "ZREALIZOWANA" in upper or "DOWIEZIONA" in upper:
        return "ZREALIZOWANA"
    return "ANALIZA"


def get_keywords(text: str) -> set[str]:
    """Ekstrahuje unikalne słowa kluczowe z tekstu, filtrując słowa pospolite."""
    words = re.findall(r"\b[a-ząćęłńóśźż]{3,}\b", text.lower())
    return {w for w in words if w not in POLISH_STOPWORDS}


def is_factcheck_matching_promise(item: RSSFeedItemData, promise: Promise) -> bool:
    """Określa, czy dany artykuł fact-checkingowy odnosi się do wskazanej obietnicy wyborczej."""
    item_text = f"{item.title} {item.summary}".lower()
    promise_title_keywords = get_keywords(promise.title)

    # 1. Sprawdzenie dokładnego dopasowania kluczowych fraz z tytułu obietnicy
    matching_keywords = {kw for kw in promise_title_keywords if kw in item_text}

    # Wymagamy minimum 2 znaczących słów kluczowych z tytułu obietnicy
    if len(matching_keywords) >= 2:
        return True

    # 2. Dla obietnic o krótkich tytułach (np. "Babciowe") wystarczy 1 rzadkie słowo kluczowe
    rare_keywords = {"babciowe", "wakacje", "składka", "kredyt", "aktywny", "wiatraki", "pigułka"}
    for rk in rare_keywords:
        if rk in promise.title.lower() and rk in item_text:
            return True

    return False


@dag(
    dag_id="external_factcheck_dag",
    schedule="@daily",
    start_date=datetime(2024, 1, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    tags=["factcheck", "demagog", "oko_press", "konkret24", "verification"],
    doc_md=__doc__,
)
def external_factcheck_pipeline() -> None:
    @task(task_id="fetch_factchecks_task")
    def fetch_factchecks_task() -> list[dict[str, Any]]:
        """Pobiera wiadomości z kanałów RSS organizacji fact-checkingowych."""
        collector = RSSCollector(timeout=20.0, delay=1.0)
        all_items: list[dict[str, Any]] = []

        for feed_cfg in FACTCHECK_FEEDS:
            try:
                items = collector.fetch_feed(
                    source_name=feed_cfg["name"],
                    feed_url=feed_cfg["url"],
                    category="FACTCHECK",
                )
                logger.info("Pobrano %d wpisów z %s", len(items), feed_cfg["name"])
                for it in items:
                    all_items.append(it.model_dump())
            except Exception as exc:
                logger.warning("Błąd pobierania RSS z %s: %s", feed_cfg["name"], exc)

        return all_items

    @task(task_id="match_and_update_promises_task")
    def match_and_update_promises_task(raw_items: list[dict[str, Any]]) -> int:
        """Mapuje pobrane artykuły z obietnicami i aktualizuje pole external_factchecks w bazie."""
        if not raw_items:
            logger.info("Brak wpisów fact-checkingowych do przetworzenia.")
            return 0

        engine = get_engine()
        matched_count = 0

        with Session(engine) as session:
            promises = session.exec(select(Promise)).all()
            if not promises:
                logger.warning("Baza obietnic jest pusta - pomijam mapowanie.")
                return 0

            for raw in raw_items:
                item = RSSFeedItemData.model_validate(raw)
                verdict = extract_verdict(f"{item.title} {item.summary}")

                for promise in promises:
                    if is_factcheck_matching_promise(item, promise):
                        current_checks = list(promise.external_factchecks or [])
                        # Deduplikacja po URL
                        existing_urls = {fc.get("url") for fc in current_checks}
                        if item.link in existing_urls:
                            continue

                        new_entry = {
                            "source": item.source_name,
                            "title": item.title,
                            "url": item.link,
                            "verdict": verdict,
                            "summary": item.summary[:400],
                            "published_at": item.published_at.isoformat(),
                            "matched_at": datetime.now(UTC).isoformat(),
                        }
                        current_checks.append(new_entry)
                        promise.external_factchecks = current_checks
                        promise.updated_at = datetime.now(UTC)
                        session.add(promise)
                        matched_count += 1
                        logger.info(
                            "Dopasowano weryfikację '%s' [%s] do obietnicy %s",
                            item.title,
                            verdict,
                            promise.id,
                        )

            session.commit()

        logger.info(
            "Łącznie dodano %d nowych zewnętrznych weryfikacji fact-checkingowych.", matched_count
        )
        return matched_count

    items_data = fetch_factchecks_task()
    match_and_update_promises_task(items_data)


external_factcheck_pipeline_dag = external_factcheck_pipeline()
