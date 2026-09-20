"""Schematy Pydantic v2 dla endpointów REST API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PromiseListItem(BaseModel):
    """Obietnica wyborcza na liście podsumowującej."""

    id: str
    party: str
    title: str
    category: str
    status: str
    latest_alignment_status: (
        Literal["W_PELNI", "CZESCIOWO", "SPRZECZNA", "BRAK_POWIAZANIA"] | None
    ) = None
    estimated_budget_impact_pln: float | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArticleExcerpt(BaseModel):
    """Wyciąg z artykułu powiązanego z ocenianą obietnicą."""

    article_number: str
    raw_text: str


class PromiseEvaluationDetail(BaseModel):
    """Szczegółowa ewaluacja obietnicy wraz z powiązanymi fragmentami ustaw."""

    promise_id: str
    title: str
    full_text: str
    party: str
    category: str
    status: str
    alignment_status: Literal["W_PELNI", "CZESCIOWO", "SPRZECZNA", "BRAK_POWIAZANIA"] | None = None
    justification: str | None = None
    confidence_score: float | None = None
    bill_id: str | None = None
    bill_title: str | None = None
    bill_print_num: str | None = None
    relevant_articles: list[ArticleExcerpt] = Field(default_factory=list)


class DailyActivityItem(BaseModel):
    """Wskaźnik aktywności poselskiej w pojedynczym dniu pod kątem heatmapy."""

    date: str
    total_votes: int
    attendance_rate: float
    dominant_status: Literal["LOYAL", "REBELLIOUS", "ABSENT", "MIXED", "NO_VOTES"]
