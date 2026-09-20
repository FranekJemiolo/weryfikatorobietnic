"""Schematy walidacji danych i ustrukturyzowanych odpowiedzi modeli LLM.

Definiuje typy zwracane przez moduł ewaluacji zgodności projektów ustaw z obietnicami
zgodnie z kontraktem Structured Outputs (JSON Schema).
"""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AlignmentStatus(StrEnum):
    """Znormalizowany status zgodności procedowanego projektu z obietnicą wyborczą."""

    W_PELNI = "W_PELNI"
    CZESCIOWO = "CZESCIOWO"
    SPRZECZNA = "SPRZECZNA"
    BRAK_POWIAZANIA = "BRAK_POWIAZANIA"


class PromiseModel(BaseModel):
    """Model reprezentujący pojedynczą obietnicę wyborczą z tzw. Złotego Zbioru (Ground Truth)."""

    promise_id: str = Field(..., description="Unikalny identyfikator, np. KO-100K-042")
    party_id: str = Field(..., description="Kod partii, np. KO, TD, LEWICA")
    category: str = Field(..., description="Kategoria tematyczna, np. Podatki, Zdrowie")
    title: str = Field(..., description="Krótki tytuł obietnicy")
    raw_text: str = Field(..., description="Oryginalny tekst deklaracji wyborczej")
    source_document: str = Field(..., description="Nazwa dokumentu źródłowego")
    quantifiable_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Wskaźniki liczbowe, np. kwota, termin, %",
    )

    model_config = ConfigDict(frozen=True)


class PromiseEvaluation(BaseModel):
    """Ścisły kontrakt wyjściowy ewaluatora LLM (Structured Outputs)."""

    promise_id: str = Field(..., description="ID obietnicy z bazy referencyjnej.")
    project_id: str = Field(..., description="ID druku sejmowego lub procesu ustawy.")
    alignment_status: Literal["W_PELNI", "CZESCIOWO", "SPRZECZNA", "BRAK_POWIAZANIA"] = Field(
        ..., description="Kategoryczna ocena realizacji obietnicy."
    )
    justification: str = Field(
        ..., description="Krótkie, jedno- do dwuzdaniowe bezstronne uzasadnienie decyzji."
    )
    divergence_details: str | None = Field(
        default=None,
        description="Jeśli status to CZESCIOWO lub SPRZECZNA, precyzyjnie wskaż różnice i wyłączenia.",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Pewność modelu od 0.0 do 1.0. Wyniki poniżej 0.7 wymagają weryfikacji manualnej.",
    )
    evaluated_provisions: list[str] = Field(
        default_factory=list,
        description="Lista artykułów i ustępów ustawy, na podstawie których dokonano oceny.",
    )

    model_config = ConfigDict(extra="forbid")

    @property
    def alignment_score(self) -> int:
        """Konwertuje status kategoryczny na punktację w skali 0-100."""
        score_map = {
            "W_PELNI": 100,
            "CZESCIOWO": 50,
            "SPRZECZNA": 0,
            "BRAK_POWIAZANIA": 0,
        }
        return score_map.get(self.alignment_status, 0)

    @property
    def requires_manual_review(self) -> bool:
        """Wskazuje, czy rekord wymaga przeglądu przez analityka z powodu niskiej pewności."""
        return self.confidence_score < 0.70


# Alias kompatybilności wstecznej
EvaluationResult = PromiseEvaluation
