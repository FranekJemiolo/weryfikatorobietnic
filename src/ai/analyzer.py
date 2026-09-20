"""Moduł analityczny AI: generowanie osadzeń wektorowych oraz ustrukturyzowana analiza OSR."""

import hashlib
import json
import logging
import math
import os
import re
from typing import Any

from pydantic import BaseModel, Field

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]

logger = logging.getLogger("AIAnalyzer")


class OSRFinancialAnalysis(BaseModel):
    """Ustrukturyzowany kontrakt wyjściowy dla analizy Oceny Skutków Regulacji (OSR)."""

    estimated_budget_impact_pln: float | None = Field(
        default=None,
        description="Wyciągnięty szacowany całkowity wpływ na sektor finansów publicznych w PLN",
    )
    summary: str = Field(
        ...,
        description="Zwięzłe, rzeczowe podsumowanie skutków finansowych dla obywateli i budżetu państwa",
    )


class AIAnalyzer:
    """Komponent AI odpowiedzialny za tworzenie wektorów (RAG) oraz analizę finansową OSR."""

    DEFAULT_LLM_MODEL = "gemini-2.5-flash"
    DEFAULT_EMBEDDING_MODEL = "text-embedding-004"
    EMBEDDING_DIM = 1536

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = DEFAULT_LLM_MODEL,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        """Inicjalizuje klienta AI.

        Args:
            api_key: Opcjonalny klucz API (jeśli None, pobierany z GEMINI_API_KEY lub GOOGLE_API_KEY).
            model_name: Nazwa modelu językowego do analizy OSR.
            embedding_model: Nazwa modelu wektoryzującego.
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name
        self.embedding_model = embedding_model
        self._client: Any = None

        if genai and self.api_key:
            try:
                self._client = genai.Client(api_key=self.api_key)
            except Exception as err:
                logger.warning("Nie udało się zainicjalizować oficjalnego klienta GenAI: %s", err)

    def _fallback_embedding(self, text: str) -> list[float]:
        """Generuje deterministyczny, znormalizowany wektor 1536-d w trybie offline/testowym."""
        vec = [0.0] * self.EMBEDDING_DIM
        for word in text.lower().split():
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx = h % self.EMBEDDING_DIM
            vec[idx] += 1.0

        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            return [x / norm for x in vec]
        return vec

    def generate_embeddings(self, text_chunks: list[str]) -> list[list[float]]:
        """Generuje osadzenia wektorowe dla przekazanej listy fragmentów tekstu.

        Args:
            text_chunks: Lista ciągów znaków (np. pojedynczych artykułów ustawy).

        Returns:
            Lista wektorów zmiennoprzecinkowych (float) o stałej wymiarowości.
        """
        if not text_chunks:
            return []

        if self._client:
            try:
                embeddings_list: list[list[float]] = []
                for chunk in text_chunks:
                    resp = self._client.models.embed_content(
                        model=self.embedding_model,
                        contents=chunk,
                    )
                    # Jeśli model zwraca wektory 768-d, dopełniamy do 1536 pod schemat Vector(1536)
                    values = list(resp.embedding.values)
                    if len(values) < self.EMBEDDING_DIM:
                        values = values + [0.0] * (self.EMBEDDING_DIM - len(values))
                    elif len(values) > self.EMBEDDING_DIM:
                        values = values[: self.EMBEDDING_DIM]
                    embeddings_list.append(values)
                return embeddings_list
            except Exception as exc:
                logger.warning(
                    "Błąd zapytania do API embeddingów (%s). Przełączanie na tryb awaryjny.", exc
                )

        # Fallback offline
        return [self._fallback_embedding(chunk) for chunk in text_chunks]

    def analyze_osr_financials(self, osr_text: str) -> dict[str, Any]:
        """Wykonuje analitykę Oceny Skutków Regulacji (OSR) z wymuszeniem struktury JSON (Structured Outputs).

        Args:
            osr_text: Tekst dokumentu Oceny Skutków Regulacji (OSR) lub uzasadnienia.

        Returns:
            Słownik: {'estimated_budget_impact_pln': float | None, 'summary': str}.
        """
        if not osr_text or not osr_text.strip():
            return {
                "estimated_budget_impact_pln": None,
                "summary": "Brak tekstu OSR do analizy finansowej.",
            }

        prompt = (
            "Jesteś bezstronnym analitykiem budżetowym w projekcie 'Weryfikator Obietnic'. "
            "Przeanalizuj poniższy fragment Oceny Skutków Regulacji (OSR) lub uzasadnienia ustawy. "
            "Wyodrębnij łączny szacowany roczny lub całkowity wpływ na finanse publiczne (w PLN jako liczbę zmiennoprzecinkową) "
            "oraz sporządź zwięzłe, jednotekstowe podsumowanie konsekwencji budżetowych.\n\n"
            f"TEKST OSR:\n{osr_text[:12000]}"
        )

        if self._client and types:
            try:
                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=OSRFinancialAnalysis,
                    temperature=0.1,
                )
                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                )
                parsed_json = json.loads(response.text)
                return OSRFinancialAnalysis.model_validate(parsed_json).model_dump()
            except Exception as err:
                logger.warning(
                    "Błąd wywołania LLM przy analizie OSR: %s. Użycie reguł heurystycznych.", err
                )

        # Heurystyczny parser awaryjny (regex na kwoty w PLN / mln / mld)
        impact_pln: float | None = None
        match = re.search(
            r"(\d+(?:[\s,.]\d+)?)\s*(mld|mln|tys\.)?\s*(?:zł|PLN)", osr_text, re.IGNORECASE
        )
        if match:
            raw_val = match.group(1).replace(" ", "").replace(",", ".")
            try:
                base_num = float(raw_val)
                unit = (match.group(2) or "").lower()
                if "mld" in unit:
                    impact_pln = base_num * 1_000_000_000
                elif "mln" in unit:
                    impact_pln = base_num * 1_000_000
                elif "tys" in unit:
                    impact_pln = base_num * 1_000
                else:
                    impact_pln = base_num
            except ValueError:
                impact_pln = None

        first_sentence = osr_text.split(".")[0].strip()
        summary = (
            f"Zidentyfikowano szacunkowy wpływ regulacji: {first_sentence}."
            if first_sentence
            else "Projekt zawiera ocenę skutków regulacji dla sektora finansów."
        )

        return OSRFinancialAnalysis(
            estimated_budget_impact_pln=impact_pln,
            summary=summary[:500],
        ).model_dump()
