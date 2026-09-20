"""Modele walidacyjne Pydantic v2 dla struktur zwracanych przez Sejm OpenAPI.

Zapewnia ścisłą walidację typów na wejściu warstwy ingestii, odrzucając
nieprawidłowe lub uszkodzone payloady zanim trafią do bazy PostgreSQL.
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VoteType(StrEnum):
    """Znormalizowany typ oddanego głosu przez posła."""

    YES = "YES"
    NO = "NO"
    ABSTAIN = "ABSTAIN"
    ABSENT = "ABSENT"
    VOTE_VALID = "VOTE_VALID"


class SejmProcessStage(BaseModel):
    """Pojedynczy etap procesu legislacyjnego (np. czytanie, skierowanie do komisji)."""

    stage_name: str = Field(..., alias="stageName")
    date: date | datetime | str | None = None
    sitting_num: int | None = Field(default=None, alias="sittingNum")
    comment: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class SejmProcessRaw(BaseModel):
    """Model procesu legislacyjnego pobieranego z endpointu /term{term}/processes."""

    number: str | int
    term: int = 10
    title: str
    document_type: str | None = Field(default=None, alias="documentType")
    description: str | None = None
    author: str | None = None
    author_type: str | None = Field(default=None, alias="authorType")
    change_date: datetime | str | None = Field(default=None, alias="changeDate")
    urgency: str | None = None
    prints: list[str | int] = Field(default_factory=list)
    stages: list[SejmProcessStage | dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    @property
    def process_id(self) -> str:
        """Zwraca zunifikowany identyfikator procesu, np. '10-123'."""
        return f"{self.term}-{self.number}"


class SejmAttachmentRaw(BaseModel):
    """Załącznik binarny do druku sejmowego (np. tekst ustawy, OSR, opinia)."""

    name: str
    url: str | None = None
    last_modified: datetime | str | None = Field(default=None, alias="lastModified")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class SejmPrintRaw(BaseModel):
    """Druk sejmowy pobierany z endpointu /term{term}/prints."""

    number: str | int
    term: int = 10
    title: str
    document_date: date | str | None = Field(default=None, alias="documentDate")
    delivery_date: date | str | None = Field(default=None, alias="deliveryDate")
    change_date: datetime | str | None = Field(default=None, alias="changeDate")
    attachments: list[SejmAttachmentRaw] = Field(default_factory=list)
    process_print: list[str | int] = Field(default_factory=list, alias="processPrint")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    @property
    def print_id(self) -> str:
        """Zwraca zunifikowany identyfikator druku."""
        return f"{self.term}-{self.number}"


class SejmSingleMPVoteRaw(BaseModel):
    """Pojedynczy głos posła w głosowaniu imiennym."""

    mp_id: int = Field(..., alias="MP")
    first_last_name: str | None = Field(default=None, alias="firstLastName")
    club: str | None = None
    vote: str

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    def normalized_vote(self) -> VoteType:
        """Normalizuje ciąg znaków głosu do enuma VoteType."""
        raw = self.vote.strip().upper()
        if raw in ("ZA", "YES"):
            return VoteType.YES
        if raw in ("PRZECIW", "NO"):
            return VoteType.NO
        if raw in ("WSTRZYMAŁ SIĘ", "WSTRZYMAL SIE", "ABSTAIN"):
            return VoteType.ABSTAIN
        return VoteType.ABSENT


class SejmVotingRaw(BaseModel):
    """Głosowanie sejmowe z endpointu /term{term}/votings/{sitting}/{votingNum}."""

    term: int = 10
    sitting: int
    sitting_day: int | None = Field(default=None, alias="sittingDay")
    voting_number: int = Field(..., alias="votingNumber")
    date: datetime | str
    title: str
    topic: str | None = None
    total_voted: int = Field(default=0, alias="totalVoted")
    yes: int = 0
    no: int = 0
    abstain: int = 0
    not_participating: int = Field(default=0, alias="notParticipating")
    votes: list[SejmSingleMPVoteRaw] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    @property
    def voting_id(self) -> str:
        """Zwraca unikalny klucz głosowania: {term}-{sitting}-{votingNumber}."""
        return f"{self.term}-{self.sitting}-{self.voting_number}"


class SejmMPRaw(BaseModel):
    """Poseł na Sejm RP pobierany z endpointu /term{term}/MP."""

    id: int
    first_last_name: str = Field(..., alias="firstLastName")
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    club: str
    district_name: str | None = Field(default=None, alias="districtName")
    active: bool = True

    model_config = ConfigDict(populate_by_name=True, extra="ignore")
