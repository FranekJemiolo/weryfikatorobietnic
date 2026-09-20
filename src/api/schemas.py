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
    estimated_budget_impact_pln: float | None = None
    divergence_details: str | None = None
    relevant_articles: list[ArticleExcerpt] = Field(default_factory=list)


class DailyActivityItem(BaseModel):
    """Wskaźnik aktywności poselskiej w pojedynczym dniu pod kątem heatmapy."""

    date: str
    total_votes: int
    attendance_rate: float
    rebellion_rate: float | None = 0.0
    dominant_status: Literal["LOYAL", "REBELLIOUS", "ABSENT", "MIXED", "NO_VOTES"]


class MPProfileResponse(BaseModel):
    """Szczegółowe dane posła na Sejm RP."""

    id: int
    first_name: str
    last_name: str
    club: str
    active: bool

    model_config = ConfigDict(from_attributes=True)


class TimelineEvent(BaseModel):
    """Wydarzenie na osi czasu procesu legislacyjnego (Time-to-Delivery)."""

    date: str
    stage_name: str
    description: str
    is_completed: bool


class AnalyticsSummary(BaseModel):
    """Globalne wskaźniki podsumowujące realizację obietnic rządu (Government Score)."""

    total_promises: int
    fulfilled_count: int
    in_progress_count: int
    broken_count: int
    average_delivery_days: float | None = None


class PromiseSearchResponse(BaseModel):
    """Wynik zapytania wyszukiwarki obietnic z obsługą paginacji."""

    items: list[PromiseListItem]
    total: int
    limit: int
    offset: int
