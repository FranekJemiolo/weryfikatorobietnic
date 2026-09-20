"""Moduł ewaluacji LLM dla Apache Airflow (Task 4 potoku ETL).

Wykorzystuje oficjalne SDK Google GenAI (google-genai) do wymuszenia schematu
Structured Outputs (Pydantic v2) na modelach Gemini, dokonuje bezstronnej analizy
zgodności projektów ustaw z obietnicami i wykonuje operację UPSERT do tabeli core_evaluations
za pośrednictwem Airflow PostgresHook.
"""

import json
import logging
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import timedelta
from typing import Any, Literal, TypeVar

from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel, ConfigDict, Field

F = TypeVar("F", bound=Callable[..., Any])

# Obsługa importów Airflow z bezpiecznym fallbackiem dla środowisk deweloperskich/testowych
try:
    from airflow.decorators import task  # type: ignore[import-not-found]
    from airflow.models import Variable  # type: ignore[import-not-found]
    from airflow.providers.postgres.hooks.postgres import (  # type: ignore[import-not-found]
        PostgresHook,
    )

    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False

    class MockTask:
        """Atrapa węzła zadania Airflow w środowisku bez aktywnego schedulera."""

        def __init__(self, name: str) -> None:
            self.name = name

        def __rshift__(self, other: Any) -> Any:
            return other

        def __lshift__(self, other: Any) -> Any:
            return other

    def task(*args: Any, **kwargs: Any) -> Callable[[F], F]:
        """Atrapa dekoratora @task do celów testowych."""

        def decorator(f: F) -> F:
            return f

        return decorator

    class Variable:  # type: ignore[no-redef]
        """Atrapa Airflow Variable dla testów."""

        @staticmethod
        def get(key: str, default_var: Any = None) -> Any:
            return default_var

    class PostgresHook:  # type: ignore[no-redef]
        """Atrapa PostgresHook delegująca do lokalnego db_manager w testach."""

        def __init__(self, postgres_conn_id: str = "postgres_default") -> None:
            self.postgres_conn_id = postgres_conn_id

        def get_conn(self) -> Any:
            from src.core.database import db_manager

            return db_manager.get_connection()


logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# 1. Schemat Danych Wyjściowych (Pydantic v2 Contract)
# ------------------------------------------------------------------------------
class PromiseEvaluation(BaseModel):
    """Ścisły schemat wyjściowy oceny projektu ustawy względem obietnicy wyborczej."""

    promise_id: str = Field(
        ...,
        description="Unikalny identyfikator obietnicy z bazy referencyjnej (np. 'KO-100K-042').",
    )
    project_id: str = Field(
        ...,
        description="Identyfikator procesu lub druku sejmowego (np. '10-120').",
    )
    alignment_status: Literal["W_PELNI", "CZESCIOWO", "SPRZECZNA", "BRAK_POWIAZANIA"] = Field(
        ...,
        description="Kategoryczna klasyfikacja merytorycznej zgodności projektu z obietnicą.",
    )
    justification: str = Field(
        ...,
        max_length=600,
        description="Zwięzłe (1-2 zdania), bezstronne uzasadnienie orzeczenia oparte na faktach.",
    )
    divergence_details: str | None = Field(
        default=None,
        description="Precyzyjne wykazanie wyłączeń podmiotowych, ograniczeń kwotowych lub opóźnień.",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Wskaźnik pewności modelu w skali 0.0 - 1.0. Wartości < 0.70 oznaczają konieczność weryfikacji.",
    )

    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------------------
# 2. Klasa Klienta LLM (Niezależna od Airflow dla łatwego testowania)
# ------------------------------------------------------------------------------
class GeminiStructuredEvaluator:
    """Klient API Gemini wykorzystujący oficjalne SDK google-genai i Structured Outputs."""

    SYSTEM_INSTRUCTION = """Jesteś bezstronnym biegłym analitykiem prawno-legislacyjnym.
Twoim celem jest porównanie treści obietnicy wyborczej z przepisami procedowanego projektu ustawy.

ZASADY EWALUACJI:
1. Skup się wyłącznie na faktach: beneficjentach, kwotach, wyłączeniach i terminach wejścia w życie.
2. Odcinaj się od ocen politycznych lub moralnych ("dobre/złe prawo").
3. Klasyfikuj status:
   - "W_PELNI" - ustawa wdraża obietnicę bez zawężania beneficjentów i obniżania kwot.
   - "CZESCIOWO" - ustawa realizuje cel z ograniczeniami, progami dochodowymi lub wyłączeniami.
   - "SPRZECZNA" - ustawa działa przeciwnie do zapowiedzi (np. podwyżka zamiast obniżki).
   - "BRAK_POWIAZANIA" - przepisy nie regulują materii obietnicy.
4. Zwróć wynik wyłącznie w formacie JSON zgodnym ze schematem.
"""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-1.5-flash",
    ) -> None:
        """Inicjalizuje klienta Google GenAI.

        Args:
            api_key: Klucz API Google Gemini. Jeśli brak, evaluator działa w trybie heurystycznym.
            model_name: Nazwa modelu z rodziny Gemini (np. 'gemini-1.5-flash' lub 'gemini-2.0-flash').
        """
        self._api_key = api_key
        self._model_name = model_name
        self._client: genai.Client | None = None

        if self._api_key:
            self._client = genai.Client(api_key=self._api_key)

    def evaluate_pair(
        self,
        promise_id: str,
        promise_text: str,
        project_id: str,
        provisions_text: list[str],
    ) -> PromiseEvaluation:
        """Przeprowadza ewaluację obietnicy względem wyselekcjonowanych artykułów ustawy.

        Args:
            promise_id: Identyfikator obietnicy.
            promise_text: Treść obietnicy wyborczej.
            project_id: Identyfikator procedowanego projektu ustawy.
            provisions_text: Lista wyselekcjonowanych przez RAG artykułów.

        Returns:
            PromiseEvaluation: Zwalidowany obiekt oceny zgodności.

        Raises:
            APIError: W przypadku nienaprawialnego błędu komunikacji z Google GenAI API.
        """
        if not provisions_text:
            return PromiseEvaluation(
                promise_id=promise_id,
                project_id=project_id,
                alignment_status="BRAK_POWIAZANIA",
                justification="Brak artykułów ustawy powiązanych z tą obietnicą.",
                divergence_details=None,
                confidence_score=1.0,
            )

        context_body = "\n\n".join(provisions_text)
        prompt = (
            f"OBIETNICA WYBORCZA (ID: {promise_id}):\n{promise_text}\n\n"
            f"ARTYKUŁY Z PROJEKTU USTAWY (PROJEKT: {project_id}):\n{context_body}\n\n"
            f"Zwróć ocenę dla promise_id='{promise_id}' oraz project_id='{project_id}'."
        )

        if self._client:
            return self._call_gemini_api(prompt, promise_id, project_id)

        # Tryb awaryjny / offline dla testów jednostkowych
        return self._heuristic_fallback(promise_id, promise_text, project_id, provisions_text)

    def _call_gemini_api(self, prompt: str, promise_id: str, project_id: str) -> PromiseEvaluation:
        """Wywołuje oficjalne SDK google-genai z wymuszonym schematem JSON."""
        assert self._client is not None

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=PromiseEvaluation,
            system_instruction=self.SYSTEM_INSTRUCTION,
            temperature=0.1,
        )

        try:
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=config,
            )
            raw_text = response.text or "{}"
            parsed_dict = json.loads(raw_text)
            return PromiseEvaluation.model_validate(parsed_dict)
        except APIError as api_err:
            logger.error("Błąd Google GenAI API dla projektu %s: %s", project_id, api_err)
            raise
        except Exception as err:
            logger.warning("Błąd parsowania odpowiedzi Gemini: %s. Używam fallbacku.", err)
            return PromiseEvaluation(
                promise_id=promise_id,
                project_id=project_id,
                alignment_status="CZESCIOWO",
                justification="Błąd podczas przetwarzania odpowiedzi LLM; skierowano do weryfikacji ręcznej.",
                divergence_details=f"Błąd deserializacji: {err}",
                confidence_score=0.20,
            )

    def _heuristic_fallback(
        self,
        promise_id: str,
        promise_text: str,
        project_id: str,
        provisions_text: list[str],
    ) -> PromiseEvaluation:
        """Deterministyczny silnik regułowy dla pracy lokalnej bez kluczy API."""
        combined_articles = " ".join(provisions_text).lower()
        p_lower = promise_text.lower()

        keywords = [w for w in p_lower.split() if len(w) > 4]
        match_count = sum(1 for kw in keywords if kw in combined_articles)

        if match_count >= 3:
            if any(
                term in combined_articles for term in ["z wyjątkiem", "wyłącza się", "nie dotyczy"]
            ):
                return PromiseEvaluation(
                    promise_id=promise_id,
                    project_id=project_id,
                    alignment_status="CZESCIOWO",
                    justification="Zidentyfikowano wyłączenia podmiotowe w przepisach projektu.",
                    divergence_details="Występują klauzule wyłączające część beneficjentów.",
                    confidence_score=0.85,
                )
            return PromiseEvaluation(
                promise_id=promise_id,
                project_id=project_id,
                alignment_status="W_PELNI",
                justification="Artykuły projektu bezpośrednio realizują treść obietnicy.",
                divergence_details=None,
                confidence_score=0.92,
            )

        if match_count >= 1:
            return PromiseEvaluation(
                promise_id=promise_id,
                project_id=project_id,
                alignment_status="CZESCIOWO",
                justification="Częściowa zbieżność terminologiczna wymagająca weryfikacji.",
                divergence_details="Ograniczone pokrycie leksykalne.",
                confidence_score=0.60,  # Wymaga weryfikacji manualnej (< 0.70)
            )

        return PromiseEvaluation(
            promise_id=promise_id,
            project_id=project_id,
            alignment_status="BRAK_POWIAZANIA",
            justification="Brak zbieżności merytorycznej między przepisami a deklaracją.",
            divergence_details=None,
            confidence_score=0.85,
        )


# ------------------------------------------------------------------------------
# 3. Pomocnik Kontekstu Połączenia PostgreSQL
# ------------------------------------------------------------------------------
@contextmanager
def get_db_cursor(hook: PostgresHook) -> Generator[Any, None, None]:
    """Zarządza kontekstem kursora bazy danych dla PostgresHook."""
    conn = hook.get_conn()
    if hasattr(conn, "__enter__"):
        with conn as active_conn:
            cur = active_conn.cursor()
            try:
                yield cur
                if hasattr(active_conn, "commit"):
                    active_conn.commit()
            finally:
                if hasattr(cur, "close"):
                    cur.close()
    else:
        cur = conn.cursor()
        try:
            yield cur
            if hasattr(conn, "commit"):
                conn.commit()
        finally:
            if hasattr(cur, "close"):
                cur.close()


# ------------------------------------------------------------------------------
# 4. Zadanie Airflow: TaskFlow API
# ------------------------------------------------------------------------------
@task(  # type: ignore[untyped-decorator]
    task_id="llm_promise_evaluation_task",
    retries=3,
    retry_delay=timedelta(seconds=30),
)
def evaluate_promises_with_llm(
    evaluation_payloads: list[dict[str, Any]] | None = None,
    postgres_conn_id: str = "postgres_default",
) -> dict[str, int]:
    """Wykonuje ewaluację LLM na parach (obietnica, artykuły) i zapisuje UPSERT do core_evaluations.

    Pobiera klucz API z mechanizmu Airflow Variable (zmienna 'GEMINI_API_KEY').
    Jeśli 'confidence_score' < 0.70, ustawia flagę 'needs_human_review = True'.

    Args:
        evaluation_payloads: Opcjonalna lista paczek ewaluacyjnych z zadania RAG.
            W przypadku braku, pobiera nieocenione pary bezpośrednio z bazy.
        postgres_conn_id: Identyfikator połączenia Airflow Connection do PostgreSQL.

    Returns:
        dict[str, int]: Podsumowanie przetworzonych rekordów i skierowanych do przeglądu.
    """
    hook = PostgresHook(postgres_conn_id=postgres_conn_id)

    # Pobranie klucza i konfiguracji bez bezpośredniego sięgania po os.environ w ciele zadania
    api_key = Variable.get("GEMINI_API_KEY", default_var=None)
    model_name = Variable.get("LLM_MODEL_NAME", default_var="gemini-1.5-flash")

    evaluator = GeminiStructuredEvaluator(api_key=api_key, model_name=model_name)

    # Jeśli nie przekazano ładunków w argumencie, pobieramy nieocenione pary z bazy
    payloads_to_process = evaluation_payloads
    if payloads_to_process is None:
        payloads_to_process = _fetch_pending_evaluations(hook)

    logger.info("Rozpoczynam ewaluację %d paczek legislacyjnych.", len(payloads_to_process))

    upsert_sql = """
        INSERT INTO core_evaluations (
            promise_id, project_id, alignment_status, justification,
            divergence_details, confidence_score, needs_human_review,
            evaluated_provisions, model_name, evaluated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (promise_id, project_id) DO UPDATE SET
            alignment_status = EXCLUDED.alignment_status,
            justification = EXCLUDED.justification,
            divergence_details = EXCLUDED.divergence_details,
            confidence_score = EXCLUDED.confidence_score,
            needs_human_review = EXCLUDED.needs_human_review,
            evaluated_provisions = EXCLUDED.evaluated_provisions,
            model_name = EXCLUDED.model_name,
            evaluated_at = CURRENT_TIMESTAMP;
    """

    processed_count = 0
    flagged_for_review = 0

    for payload in payloads_to_process:
        p_id = payload["promise_id"]
        proj_id = payload["project_id"]
        p_text = payload["promise_text"]
        provisions = payload.get("provisions", [])

        # Wywołanie ewaluatora LLM
        eval_result = evaluator.evaluate_pair(
            promise_id=p_id,
            promise_text=p_text,
            project_id=proj_id,
            provisions_text=provisions,
        )

        # Reguła biznesowa: flaga weryfikacji manualnej dla confidence < 0.70
        needs_human_review = eval_result.confidence_score < 0.70
        if needs_human_review:
            flagged_for_review += 1

        try:
            with get_db_cursor(hook) as cur:
                cur.execute(
                    upsert_sql,
                    (
                        eval_result.promise_id,
                        eval_result.project_id,
                        eval_result.alignment_status,
                        eval_result.justification,
                        eval_result.divergence_details,
                        eval_result.confidence_score,
                        needs_human_review,
                        json.dumps(provisions),
                        model_name,
                    ),
                )
            processed_count += 1
        except Exception as db_err:
            logger.error(
                "Błąd zapisu UPSERT do core_evaluations dla (%s, %s): %s",
                p_id,
                proj_id,
                db_err,
            )
            continue

    logger.info(
        "Zakończono ewaluację. Zapisano: %d, Do weryfikacji ręcznej: %d",
        processed_count,
        flagged_for_review,
    )

    return {
        "processed_evaluations": processed_count,
        "needs_human_review_count": flagged_for_review,
        "total_attempted": len(payloads_to_process),
    }


def _fetch_pending_evaluations(hook: PostgresHook) -> list[dict[str, Any]]:
    """Pobiera z PostgreSQL zestaw obietnic i odpowiadających im artykułów do ewaluacji."""
    query = """
        SELECT p.promise_id, p.raw_text as promise_text,
               lp.process_id as project_id,
               COALESCE(
                   json_agg(lp.context_path || ': ' || lp.provision_text)
                   FILTER (WHERE lp.id IS NOT NULL),
                   '[]'::json
               ) as provisions
        FROM electoral_promises p
        CROSS JOIN legislative_processes proc
        LEFT JOIN legislative_provisions lp ON proc.process_id = lp.process_id
        LEFT JOIN core_evaluations ce ON p.promise_id = ce.promise_id AND proc.process_id = ce.project_id
        WHERE ce.promise_id IS NULL
        GROUP BY p.promise_id, p.raw_text, lp.process_id
        LIMIT 25;
    """
    payloads: list[dict[str, Any]] = []
    try:
        with get_db_cursor(hook) as cur:
            cur.execute(query)
            rows = cur.fetchall()
            for r in rows:
                if isinstance(r, dict):
                    provs = r["provisions"]
                    if isinstance(provs, str):
                        provs = json.loads(provs)
                    payloads.append(
                        {
                            "promise_id": r["promise_id"],
                            "promise_text": r["promise_text"],
                            "project_id": r["project_id"] or "unknown",
                            "provisions": provs if isinstance(provs, list) else [],
                        }
                    )
                else:
                    provs = r[3]
                    if isinstance(provs, str):
                        provs = json.loads(provs)
                    payloads.append(
                        {
                            "promise_id": r[0],
                            "promise_text": r[1],
                            "project_id": r[2] or "unknown",
                            "provisions": provs if isinstance(provs, list) else [],
                        }
                    )
    except Exception as err:
        logger.warning("Brak możliwości pobrania nieocenionych par z bazy: %s", err)

    return payloads
