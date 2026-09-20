"""Zarządzanie połączeniem i silnikiem bazy danych SQLModel/PostgreSQL."""

import os
from collections.abc import Generator

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

DEFAULT_DATABASE_URL = "postgresql://user:pass@localhost:5432/weryfikator"


def get_database_url() -> str:
    """Pobiera URL połączenia z bazą danych ze środowiska lub zwraca domyślny."""
    url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    # Zapewnienie kompatybilności ze sterownikiem psycopg2 w SQLAlchemy
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def get_engine(url: str | None = None, echo: bool = False) -> Engine:
    """Tworzy i konfiguruje silnik SQLAlchemy/SQLModel.

    Args:
        url: Opcjonalny niestandardowy URL połączenia (np. do testów z SQLite in-memory).
        echo: Flaga włączająca logowanie zapytań SQL do konsoli.
    """
    db_url = url or get_database_url()
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(
        db_url,
        echo=echo,
        connect_args=connect_args,
        pool_pre_ping=True,
    )


def get_session(engine: Engine | None = None) -> Generator[Session, None, None]:
    """Generator sesji bazy danych (przydatny m.in. jako Depends w FastAPI)."""
    db_engine = engine or get_engine()
    with Session(db_engine) as session:
        yield session


def init_db(engine: Engine | None = None) -> None:
    """Tworzy wszystkie zdefiniowane tabele SQLModel w bazie danych."""
    db_engine = engine or get_engine()
    SQLModel.metadata.create_all(db_engine)
