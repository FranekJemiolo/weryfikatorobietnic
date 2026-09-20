"""Modele domenowe reprezentujące obiekty prawne, procesy oraz głosowania."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class LegislativeProcessModel(BaseModel):
    """Model danych opisujący proces legislacyjny w Sejmie."""

    process_id: str
    term: int = 10
    title: str
    description: str | None = None
    author: str | None = None
    author_type: str | None = None
    status: str
    print_numbers: list[str] = Field(default_factory=list)
    timeline: dict[str, Any] = Field(default_factory=dict)
    time_to_delivery_days: int | None = None
    first_reading_date: date | None = None
    passed_date: date | None = None
    signed_date: date | None = None


class VotingRecordModel(BaseModel):
    """Model danych opisujący głosowanie sejmowe."""

    voting_id: str
    process_id: str | None = None
    term: int = 10
    sitting: int
    voting_number: int
    date: datetime
    title: str
    topic: str | None = None
    total_voted: int
    votes_yes: int
    votes_no: int
    votes_abstain: int
    votes_absent: int
    mp_votes: list[dict[str, Any]] = Field(default_factory=list)
