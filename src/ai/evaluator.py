"""Silnik ewaluacyjny RAG: wyszukiwanie semantyczne wycinków ustaw i ocena zgodności z obietnicami."""

import json
import logging
import math
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import Engine
from sqlmodel import Session, select

from src.ai.analyzer import AIAnalyzer
from src.ai.prompts import EVALUATION_SYSTEM_PROMPT
from src.database.engine import get_engine
from src.database.models import AlignmentStatus, BillArticle, LLMEvaluation, Promise

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]

logger = logging.getLogger("PromiseEvaluator")


class PromiseEvaluationSchema(BaseModel):
    """Ścisły schemat ustrukturyzowanej odpowiedzi audytora LLM (Structured Outputs)."""

    alignment_status: Literal["W_PELNI", "CZESCIOWO", "SPRZECZNA", "BRAK_POWIAZANIA"] = Field(
        ...,
        description="Kategoryczna ocena zgodności projektu ustawy z obietnicą wyborczą",
    )
    justification: str = Field(
        ...,
        description="Jedno- lub dwuzdaniowe, bezstronne uzasadnienie decyzji ze wskazaniem faktów",
    )
    divergence_details: str | None = Field(
        default=None,
        description="Precyzyjne wskazanie rozbieżności, wyjątków lub odroczeń czasowych",
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Wskaźnik pewności i stopnia realizacji (od 0.0 do 1.0)",
    )


class PromiseEvaluator:
    """Łączy wyszukiwanie wektorowe artykułów prawnych z wnioskowaniem LLM."""

    SYSTEM_PROMPT = EVALUATION_SYSTEM_PROMPT

    def __init__(
        self,
        engine: Engine | None = None,
        analyzer: AIAnalyzer | None = None,
    ) -> None:
        self.engine = engine or get_engine()
        self.analyzer = analyzer or AIAnalyzer()

    @staticmethod
    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        """Oblicza podobieństwo kosinusowe w czystym Pythonie (fallback dla baz bez pgvector)."""
        dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def get_relevant_articles(
        self,
        promise_id: str,
        bill_id: str,
        top_k: int = 5,
    ) -> list[BillArticle]:
        """Wyszukuje top_k najbardziej relewantnych artykułów ustawy dla wskazanej obietnicy.

        Wykorzystuje wektor obietnicy oraz dystans kosinusowy w pgvector
        (z fallbackiem pythonowym dla środowisk testowych SQLite).
        """
        with Session(self.engine) as session:
            promise = session.get(Promise, promise_id)
            if not promise:
                raise ValueError(f"Nie znaleziono obietnicy o ID: {promise_id}")

            promise_text = f"{promise.title} - {promise.full_text}"
            promise_vectors = self.analyzer.generate_embeddings([promise_text])
            if not promise_vectors:
                return []
            query_vector = promise_vectors[0]

            is_postgres = session.bind is not None and session.bind.dialect.name == "postgresql"

            if is_postgres:
                try:
                    # Wykorzystanie natywnego operatora dystansu kosinusowego pgvector
                    statement = (
                        select(BillArticle)
                        .where(BillArticle.bill_id == bill_id)
                        .order_by(BillArticle.embedding.cosine_distance(query_vector))  # type: ignore[union-attr]
                        .limit(top_k)
                    )
                    return list(session.exec(statement).all())
                except Exception as err:
                    logger.warning("Błąd zapytania pgvector: %s. Użycie algorytmu fallback.", err)

            # Fallback w pamięci dla SQLite / testów
            all_articles = list(
                session.exec(select(BillArticle).where(BillArticle.bill_id == bill_id)).all()
            )
            if not all_articles:
                return []

            scored: list[tuple[float, BillArticle]] = []
            for art in all_articles:
                if art.embedding:
                    sim = self._cosine_similarity(query_vector, art.embedding)
                    scored.append((sim, art))
                else:
                    scored.append((0.0, art))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [art for _, art in scored[:top_k]]

    def evaluate_bill_against_promise(
        self,
        promise_obj: Promise,
        relevant_articles: list[BillArticle],
    ) -> PromiseEvaluationSchema:
        """Wysyła zderzenie obietnicy z artykułami do LLM i zwraca sformalizowaną ocenę."""
        articles_formatted = "\n\n".join(
            f"[{a.article_number}]: {a.raw_text}" for a in relevant_articles
        )

        # Bezpieczne pobranie atrybutów obiektu obietnicy nawet w przypadku sesji detached
        party: str = "NIEZNANA"
        title: str = "Obietnica"
        full_text: str = ""
        try:
            from sqlalchemy import inspect as sa_inspect

            insp = sa_inspect(promise_obj, raiseerr=False)
            p_id = insp.identity[0] if (insp and insp.identity) else None
            if p_id is not None:
                with Session(self.engine) as s:
                    fresh = s.get(Promise, p_id)
                    if fresh:
                        party = fresh.party
                        title = fresh.title
                        full_text = fresh.full_text
            else:
                party = promise_obj.party
                title = promise_obj.title
                full_text = promise_obj.full_text
        except Exception:
            pass

        user_content = (
            f"DEKLARACJA WYBORCZA ({party}):\n"
            f"Tytuł: {title}\n"
            f"Treść: {full_text}\n\n"
            f"WYCIĄG Z PROJEKTU USTAWY:\n"
            f"{articles_formatted if articles_formatted else 'Brak relewantnych fragmentów w projekcie.'}"
        )

        # Wywołanie z oficjalnym klientem google-genai
        if self.analyzer._client and types:
            try:
                config = types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=PromiseEvaluationSchema,
                    temperature=0.1,
                )
                response = self.analyzer._client.models.generate_content(
                    model=self.analyzer.model_name,
                    contents=user_content,
                    config=config,
                )
                data = json.loads(response.text)
                return PromiseEvaluationSchema.model_validate(data)
            except Exception as exc:
                logger.warning("Błąd wnioskowania LLM (%s). Generowanie oceny heurystycznej.", exc)

        # Fallback heurystyczny
        has_articles = bool(relevant_articles)
        if has_articles:
            status: Literal["W_PELNI", "CZESCIOWO", "SPRZECZNA", "BRAK_POWIAZANIA"] = "CZESCIOWO"
            justification = (
                f"Projekt proceduje rozwiązania tematycznie powiązane z obietnicą '{title}'."
            )
            score = 0.75
        else:
            status = "BRAK_POWIAZANIA"
            justification = "Procedowane przepisy nie wykazują związku z treścią deklaracji."
            score = 0.1

        return PromiseEvaluationSchema(
            alignment_status=status,
            justification=justification,
            divergence_details=None,
            score=score,
        )

    def save_evaluation(
        self,
        promise_id: str,
        bill_id: str,
        evaluation: PromiseEvaluationSchema,
    ) -> LLMEvaluation:
        """Zapisuje lub aktualizuje ocenę LLM w tabeli LLMEvaluation."""
        with Session(self.engine) as session:
            statement = select(LLMEvaluation).where(
                LLMEvaluation.promise_id == promise_id,
                LLMEvaluation.bill_id == bill_id,
            )
            record = session.exec(statement).first()

            status_enum = AlignmentStatus(evaluation.alignment_status)

            if record:
                record.alignment_status = status_enum
                record.justification = evaluation.justification
                record.confidence_score = evaluation.score
                record.created_at = datetime.now(UTC)
                session.add(record)
            else:
                record = LLMEvaluation(
                    promise_id=promise_id,
                    bill_id=bill_id,
                    alignment_status=status_enum,
                    justification=evaluation.justification,
                    confidence_score=evaluation.score,
                    created_at=datetime.now(UTC),
                )
                session.add(record)

            session.commit()
            session.refresh(record)
            return record

    def evaluate_and_persist(
        self,
        promise_id: str,
        bill_id: str,
        top_k: int = 5,
    ) -> LLMEvaluation:
        """Kompleksowa ścieżka: wyszukanie artykułów -> ocena LLM -> zapis do bazy."""
        with Session(self.engine) as session:
            promise = session.get(Promise, promise_id)
            if not promise:
                raise ValueError(f"Nie znaleziono obietnicy {promise_id}")

        relevant_articles = self.get_relevant_articles(promise_id, bill_id, top_k=top_k)
        evaluation_result = self.evaluate_bill_against_promise(promise, relevant_articles)
        return self.save_evaluation(promise_id, bill_id, evaluation_result)
