"""Schematy walidacji danych i ustrukturyzowanych odpowiedzi modeli LLM.

Definiuje typy zwracane przez moduł ewaluacji zgodności projektów ustaw z obietnicami.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AlignmentStatus(StrEnum):
    """Znormalizowany status zgodności procedowanego projektu z obietnicą wyborczą."""

    W_PELNI_ZREALIZOWANA = "W_PELNI_ZREALIZOWANA"
    CZESCIOWO_ZREALIZOWANA = "CZESCIOWO_ZREALIZOWANA"
    ZMIENIONA_KONCEPCJA = "ZMIENIONA_KONCEPCJA"
    SPRZECZNA = "SPRZECZNA"
    BRAK_ZWIAZKU = "BRAK_ZWIAZKU"


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


class EvaluationResult(BaseModel):
    """Ustrukturyzowany wynik ewaluacji wygenerowany przez model LLM (Structured Output)."""

    summary_pl: str = Field(
        ...,
        description="Zwięzłe (maksymalnie 3 zdania), bezstronne podsumowanie wpływu projektu.",
        max_length=600,
    )
    alignment_status: AlignmentStatus = Field(
        ...,
        description="Klasyfikacja stopnia realizacji obietnicy.",
    )
    alignment_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Punktowa ocena zgodności w skali od 0 do 100.",
    )
    divergence_analysis: str | None = Field(
        default=None,
        description="Precyzyjne wykazanie różnic w stosunku do pierwotnych założeń.",
    )
    budget_impact_summary: str | None = Field(
        default=None,
        description="Podsumowanie wpływu na budżet państwa na podstawie Oceny Skutków Regulacji (OSR).",
    )
    evaluated_provisions: list[str] = Field(
        default_factory=list,
        description="Lista kluczowych artykułów/ustępów projektu, które poddano analizie.",
    )

    model_config = ConfigDict(extra="forbid")
