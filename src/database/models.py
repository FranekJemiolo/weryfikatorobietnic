"""Modele ORM SQLModel reprezentujące schemat bazy PostgreSQL dla Weryfikatora Obietnic."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import JSON, Field, Relationship, SQLModel


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
    club_affiliations: list["MPClubAffiliation"] = Relationship(back_populates="mp")
    interpellations: list["Interpellation"] = Relationship(back_populates="mp")
    amendments: list["BillAmendment"] = Relationship(back_populates="mp")


class MPClubAffiliation(SQLModel, table=True):
    """Historia przynależności posła do klubów i kół parlamentarnych (transfery polityczne)."""

    __tablename__ = "mp_club_affiliations"

    id: int | None = Field(default=None, primary_key=True)
    mp_id: int = Field(foreign_key="mps.id", index=True, description="ID posła")
    club_name: str = Field(index=True, description="Nazwa klubu lub koła parlamentarnego")
    start_date: datetime = Field(index=True, description="Data rozpoczęcia przynależności do klubu")
    end_date: datetime | None = Field(
        default=None,
        index=True,
        description="Data zakończenia przynależności (None oznacza bieżący klub)",
    )

    mp: MP | None = Relationship(back_populates="club_affiliations")


class Interpellation(SQLModel, table=True):
    """Interpelacja poselska złożona w Sejmie RP (aktywność i proaktywność poselska)."""

    __tablename__ = "interpellations"

    id: int = Field(primary_key=True, description="Numer/identyfikator interpelacji z Sejm API")
    mp_id: int = Field(foreign_key="mps.id", index=True, description="ID posła wnoszącego")
    title: str = Field(description="Tytuł lub przedmiot interpelacji")
    receipt_date: datetime = Field(index=True, description="Data złożenia/wpływu interpelacji")
    is_answered: bool = Field(
        default=False, index=True, description="Czy nadeszła odpowiedź na interpelację"
    )

    mp: MP | None = Relationship(back_populates="interpellations")


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
    updated_at: datetime | None = Field(
        default=None,
        description="Data aktualizacji statusu lub sfinalizowania obietnicy",
    )
    external_factchecks: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(
            JSON().with_variant(JSONB, "postgresql"),
            nullable=False,
            default=list,
        ),
        description="Zewnętrzne weryfikacje fact-checkingowe (Demagog, OKO.press, Konkret24)",
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
    senate_status: str | None = Field(
        default=None,
        index=True,
        description="Status prac w Senacie RP (np. PRZYJĘTA_BEZ_POPRAWEK, WNIESIONO_POPRAWKI, ODRZUCONA)",
    )
    president_signature_date: datetime | None = Field(
        default=None,
        index=True,
        description="Data podpisania ustawy przez Prezydenta RP",
    )
    isap_publication_id: str | None = Field(
        default=None,
        index=True,
        description="Identyfikator aktu w ISAP / Dzienniku Ustaw (np. WDU/2024/123)",
    )

    evaluations: list["LLMEvaluation"] = Relationship(back_populates="bill")
    articles: list["BillArticle"] = Relationship(back_populates="bill")
    amendments: list["BillAmendment"] = Relationship(back_populates="bill")
    pre_legislative_processes: list["PreLegislativeProcess"] = Relationship(back_populates="bill")


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


class Committee(SQLModel, table=True):
    """Komisja sejmowa (np. Komisja Finansów Publicznych)."""

    __tablename__ = "committees"

    id: str = Field(primary_key=True, description="Kod komisji, np. FPB, ASW")
    name: str = Field(description="Oficjalna nazwa komisji")

    sittings: list["CommitteeSitting"] = Relationship(back_populates="committee")


class CommitteeSitting(SQLModel, table=True):
    """Posiedzenie komisji sejmowej."""

    __tablename__ = "committee_sittings"

    id: int | None = Field(default=None, primary_key=True)
    committee_id: str = Field(foreign_key="committees.id", index=True, description="Kod komisji")
    date: datetime = Field(index=True, description="Data i godzina posiedzenia komisji")

    committee: Committee | None = Relationship(back_populates="sittings")


class BillAmendment(SQLModel, table=True):
    """Poprawka do projektu ustawy zgłoszona podczas prac w komisji lub czytań."""

    __tablename__ = "bill_amendments"

    id: int | None = Field(default=None, primary_key=True)
    bill_id: str = Field(foreign_key="bills.id", index=True, description="ID projektu ustawy")
    mp_id: int | None = Field(
        default=None, foreign_key="mps.id", index=True, description="ID posła wnioskodawcy"
    )
    text_content: str = Field(description="Treść poprawki (proponowana zmiana w artykule)")
    is_accepted: bool = Field(
        default=False, index=True, description="Czy poprawka została przyjęta"
    )
    article_reference: str | None = Field(
        default=None, index=True, description="Oznaczenie zmienianego artykułu (np. Art. 5)"
    )

    bill: Bill | None = Relationship(back_populates="amendments")
    mp: MP | None = Relationship(back_populates="amendments")


class PreLegislativeProcess(SQLModel, table=True):
    """Proces pre-legislacyjny w Rządowym Centrum Legislacji (legislacja.gov.pl)."""

    __tablename__ = "pre_legislative_processes"

    id: str = Field(primary_key=True, description="Identyfikator projektu w RCL (np. UD124, UC45)")
    rcl_id: str = Field(index=True, description="Numer z wykazu prac rządu / RCL")
    title: str = Field(description="Tytuł projektu ustawy lub założeń")
    stage: str = Field(
        index=True,
        description="Etap prac: Uzgodnienia, Konsultacje publiczne, Opiniowanie",
    )
    institution: str | None = Field(
        default=None,
        description="Organ odpowiedzialny lub wnioskodawca (np. Ministerstwo Finansów)",
    )
    created_date: datetime | None = Field(
        default=None, index=True, description="Data rejestracji projektu w wykazie RCL"
    )
    updated_date: datetime | None = Field(
        default=None, description="Data ostatniej aktualizacji na portalu legislacja.gov.pl"
    )
    consultation_end_date: datetime | None = Field(
        default=None, description="Data zakończenia konsultacji publicznych"
    )
    bill_id: str | None = Field(
        default=None,
        foreign_key="bills.id",
        index=True,
        description="Identyfikator powiązanego druku sejmowego po wpłynięciu do Sejmu",
    )
    url: str | None = Field(
        default=None, description="Link do strony projektu na legislacja.gov.pl"
    )

    bill: Bill | None = Relationship(back_populates="pre_legislative_processes")


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
    divergence_details: str | None = Field(
        default=None, description="Wypunktowane lub opisane luki i rozbieżności z obietnicą"
    )
    confidence_score: float = Field(default=1.0, description="Pewność oceny modelu od 0.0 do 1.0")
    is_approved_by_human: bool = Field(
        default=False,
        index=True,
        description="Flaga zatwierdzenia oceny LLM przez człowieka (Human-in-the-Loop)",
    )
    requires_re_evaluation: bool = Field(
        default=False,
        index=True,
        description="Flaga konieczności ponownej ewaluacji po zgłoszeniu poprawek w komisji",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Czas wygenerowania oceny",
    )

    promise: Promise | None = Relationship(back_populates="evaluations")
    bill: Bill | None = Relationship(back_populates="evaluations")


class RSSFeedItem(SQLModel, table=True):
    """Wpis pobrany z oficjalnego kanału informacyjnego RSS/Atom (rządowego lub partyjnego)."""

    __tablename__ = "rss_feed_items"

    id: int | None = Field(default=None, primary_key=True)
    source_name: str = Field(index=True, description="Nazwa źródła (np. KPRM, RCL, Sejm RP, Razem)")
    feed_url: str = Field(index=True, description="Adres URL kanału informacyjnego RSS/Atom")
    title: str = Field(index=True, description="Tytuł komunikatu lub artykułu")
    link: str = Field(
        unique=True, index=True, description="Bezpośredni link URL do treści źródłowej"
    )
    summary: str = Field(description="Oczyszczona treść skrótowa lub zarys komunikatu")
    published_at: datetime = Field(
        index=True, description="Data i godzina publikacji artykułu (UTC)"
    )
    guid: str | None = Field(
        default=None, index=True, description="Unikalny identyfikator wpisu w kanale"
    )
    category: str | None = Field(
        default=None, index=True, description="Kategoria wpisu (np. GOVERNMENT, LEGISLATION, PARTY)"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Data pobrania i zapisu w bazie danych",
    )
