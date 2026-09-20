"""Modele ORM SQLModel reprezentujące schemat bazy PostgreSQL dla Weryfikatora Obietnic."""

from datetime import UTC, datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column
from sqlmodel import Field, Relationship, SQLModel


class VoteType(StrEnum):
    """Znormalizowany rodzaj oddanego głosu."""

    YES = "YES"
    NO = "NO"
    ABSTAIN = "ABSTAIN"
    ABSENT = "ABSENT"


class PromiseStatus(StrEnum):
    """Status realizacji obietnicy wyborczej."""

    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    FULFILLED = "FULFILLED"
    BROKEN = "BROKEN"


class AlignmentStatus(StrEnum):
    """Kategoryczna ocena zgodności projektu prawnego z obietnicą (LLM)."""

    W_PELNI = "W_PELNI"
    CZESCIOWO = "CZESCIOWO"
    SPRZECZNA = "SPRZECZNA"
    BRAK_POWIAZANIA = "BRAK_POWIAZANIA"


class MP(SQLModel, table=True):
    """Poseł na Sejm RP."""

    __tablename__ = "mps"

    id: int | None = Field(
        default=None, primary_key=True, description="Identyfikator posła z Sejm API"
    )
    first_name: str = Field(description="Imię posła")
    last_name: str = Field(description="Nazwisko posła")
    club: str = Field(index=True, description="Przynależność do klubu parlamentarnego lub koła")
    active: bool = Field(default=True, index=True, description="Czy mandat poselski jest aktywny")

    votes: list["MPVote"] = Relationship(back_populates="mp")


class Voting(SQLModel, table=True):
    """Głosowanie plenarne w Sejmie."""

    __tablename__ = "votings"

    id: int | None = Field(default=None, primary_key=True, description="Klucz główny głosowania")
    sitting_num: int = Field(index=True, description="Numer posiedzenia Sejmu")
    voting_num: int = Field(index=True, description="Numer głosowania na danym posiedzeniu")
    date: datetime = Field(index=True, description="Data i godzina przeprowadzenia głosowania")
    title: str = Field(description="Tytuł lub przedmiot głosowania")
    description: str | None = Field(
        default=None, description="Dodatkowy opis lub kontekst głosowania"
    )

    votes: list["MPVote"] = Relationship(back_populates="voting")


class MPVote(SQLModel, table=True):
    """Tabela asocjacyjna łącząca posła z konkretnym głosowaniem i oddanym głosem."""

    __tablename__ = "mp_votes"

    id: int | None = Field(default=None, primary_key=True)
    voting_id: int = Field(
        foreign_key="votings.id", index=True, description="ID powiązanego głosowania"
    )
    mp_id: int = Field(foreign_key="mps.id", index=True, description="ID posła")
    vote_type: VoteType = Field(index=True, description="Oddany głos (YES, NO, ABSTAIN, ABSENT)")

    voting: Voting | None = Relationship(back_populates="votes")
    mp: MP | None = Relationship(back_populates="votes")


class Promise(SQLModel, table=True):
    """Deklaracja lub obietnica wyborcza zarejestrowana w bazie referencyjnej."""

    __tablename__ = "promises"

    id: str = Field(
        primary_key=True, description="Unikalny identyfikator deklaracji, np. KO-100K-042"
    )
    party: str = Field(index=True, description="Kod partii lub koalicji, np. KO, PiS, TD, LEWICA")
    title: str = Field(index=True, description="Krótki tytuł deklaracji")
    full_text: str = Field(description="Pełne brzmienie obietnicy ze źródła")
    category: str = Field(index=True, description="Kategoria tematyczna (np. Podatki, Zdrowie)")
    status: PromiseStatus = Field(
        default=PromiseStatus.NEW, index=True, description="Bieżący status realizacji"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Znacznik czasu rejestracji obietnicy",
    )

    evaluations: list["LLMEvaluation"] = Relationship(back_populates="promise")
    revisions: list["PromiseRevision"] = Relationship(back_populates="promise")


class PromiseRevision(SQLModel, table=True):
    """Historia zmian treści deklaracji wyborczej lub stron programowych partii."""

    __tablename__ = "promise_revisions"

    id: int | None = Field(default=None, primary_key=True)
    promise_id: str = Field(
        foreign_key="promises.id", index=True, description="ID powiązanej obietnicy"
    )
    content_hash: str = Field(index=True, description="Suma kontrolna SHA-256 oczyszczonego tekstu")
    full_html_content: str = Field(description="Zarchiwizowana surowa zawartość HTML")
    scraped_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        index=True,
        description="Data i czas pobrania zrzutu strony",
    )

    promise: Promise | None = Relationship(back_populates="revisions")


class Bill(SQLModel, table=True):
    """Projekt ustawy lub druk procedowany w Sejmie."""

    __tablename__ = "bills"

    id: str = Field(primary_key=True, description="Identyfikator projektu, np. druk-124")
    sejm_print_num: str = Field(index=True, description="Oficjalny numer druku sejmowego")
    title: str = Field(description="Oficjalny tytuł projektu ustawy")
    status: str = Field(index=True, description="Aktualny status legislacyjny")
    author: str | None = Field(default=None, description="Projektodawca (np. Rząd, Poselski)")
    document_url: str | None = Field(
        default=None, description="Link do pliku PDF lub treści na sejm.gov.pl"
    )
    estimated_budget_impact_pln: float | None = Field(
        default=None,
        description="Szacowany wpływ na finanse publiczne w PLN (wyciągnięty z OSR)",
    )
    osr_summary: str | None = Field(
        default=None,
        description="Syntetyczne podsumowanie Oceny Skutków Regulacji (OSR)",
    )

    evaluations: list["LLMEvaluation"] = Relationship(back_populates="bill")
    articles: list["BillArticle"] = Relationship(back_populates="bill")


class BillArticle(SQLModel, table=True):
    """Wyodrębniony artykuł lub jednostka redakcyjna ustawy pod kątem wyszukiwania semantycznego RAG."""

    __tablename__ = "bill_articles"

    id: int | None = Field(default=None, primary_key=True)
    bill_id: str = Field(
        foreign_key="bills.id", index=True, description="Identyfikator powiązanego projektu ustawy"
    )
    article_number: str = Field(index=True, description="Oznaczenie artykułu, np. Art. 4a")
    raw_text: str = Field(description="Oryginalna treść artykułu")
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(Vector(1536)),
        description="Wektor cech semantycznych (1536 wymiarów) obsługiwany przez pgvector",
    )

    bill: Bill | None = Relationship(back_populates="articles")


class LLMEvaluation(SQLModel, table=True):
    """Ocena semantyczna zgodności procedowanego projektu z obietnicą wyborczą."""

    __tablename__ = "llm_evaluations"

    id: int | None = Field(default=None, primary_key=True)
    promise_id: str = Field(
        foreign_key="promises.id", index=True, description="ID powiązanej obietnicy"
    )
    bill_id: str = Field(
        foreign_key="bills.id", index=True, description="ID ocenianego projektu ustawy"
    )
    alignment_status: AlignmentStatus = Field(index=True, description="Kategoryczna ocena modelu")
    justification: str = Field(description="Uzasadnienie decyzji analitycznej")
    confidence_score: float = Field(default=1.0, description="Pewność oceny modelu od 0.0 do 1.0")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Czas wygenerowania oceny",
    )

    promise: Promise | None = Relationship(back_populates="evaluations")
    bill: Bill | None = Relationship(back_populates="evaluations")
