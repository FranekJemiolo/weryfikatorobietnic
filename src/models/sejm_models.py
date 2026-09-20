"""Podstawowe modele walidacji Pydantic v2 dla danych pobieranych z Sejm OpenAPI."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MPModel(BaseModel):
    """Model reprezentujący posła na Sejm RP."""

    id: int = Field(..., description="Unikalny identyfikator posła")
    first_last_name: str = Field(..., alias="firstLastName", description="Imię i nazwisko posła")
    club: str = Field(..., description="Klub parlamentarny lub koło poselskie")
    active: bool = Field(default=True, description="Czy mandat poselski jest aktywny")
    district_name: str | None = Field(
        default=None, alias="districtName", description="Okręg wyborczy"
    )

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class ProcessModel(BaseModel):
    """Model procesu legislacyjnego w Sejmie."""

    number: str | int = Field(..., description="Numer procesu")
    term: int = Field(default=10, description="Kadencja Sejmu")
    title: str = Field(..., description="Tytuł procedowanego projektu")
    document_type: str | None = Field(
        default=None, alias="documentType", description="Rodzaj dokumentu"
    )
    change_date: datetime | str | None = Field(default=None, alias="changeDate")
    prints: list[str | int] = Field(default_factory=list, description="Powiązane druki sejmowe")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class PrintDetailModel(BaseModel):
    """Szczegółowe dane pojedynczego druku sejmowego."""

    number: str = Field(..., description="Numer druku")
    term: int = Field(default=10, description="Kadencja Sejmu")
    title: str = Field(..., description="Tytuł projektu ustawy lub druku")
    document_date: str | None = Field(default=None, alias="documentDate")
    attachments: list[dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class MPVoteDetail(BaseModel):
    """Pojedynczy oddany głos posła."""

    mp_id: int = Field(..., alias="MP", description="ID posła")
    first_last_name: str | None = Field(default=None, alias="firstLastName")
    club: str | None = None
    vote: str = Field(..., description="Oddany głos: YES, NO, ABSTAIN, ABSENT, VOTE_VALID")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class VotingResultModel(BaseModel):
    """Wyniki pojedynczego imiennego głosowania w Sejmie."""

    term: int = Field(default=10, description="Kadencja Sejmu")
    sitting: int = Field(..., description="Numer posiedzenia Sejmu")
    voting_number: int = Field(..., alias="votingNumber", description="Numer głosowania")
    date: str = Field(..., description="Data i czas głosowania")
    title: str = Field(..., description="Tytuł lub przedmiot głosowania")
    topic: str | None = Field(default=None, description="Szczegółowy temat")
    total_yes: int = Field(default=0, alias="yes")
    total_no: int = Field(default=0, alias="no")
    total_abstain: int = Field(default=0, alias="abstain")
    votes: list[MPVoteDetail] = Field(default_factory=list, description="Lista imiennych głosów")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class InterpellationModel(BaseModel):
    """Model interpelacji poselskiej pobranej z Sejm OpenAPI."""

    term: int = Field(default=10, description="Kadencja Sejmu")
    num: int = Field(..., description="Numer interpelacji")
    title: str = Field(..., description="Tytuł interpelacji")
    receipt_date: str | None = Field(default=None, alias="receiptDate", description="Data wpływu")
    last_modified: str | None = Field(default=None, alias="lastModified")
    from_mp: list[int] = Field(
        default_factory=list, alias="from", description="Identyfikatory posłów wnoszących"
    )
    to: list[str] = Field(default_factory=list, description="Adresaci interpelacji")
    sent_date: str | None = Field(default=None, alias="sentDate")
    replies: list[dict[str, Any]] = Field(
        default_factory=list, description="Odpowiedzi na interpelację"
    )

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    @property
    def is_answered(self) -> bool:
        """Określa, czy interpelacja doczekała się oficjalnej odpowiedzi."""
        return len(self.replies) > 0
