"""Środowisko wykonawcze migracji bazy danych Alembic skonfigurowane dla SQLModel."""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from alembic import context

# Dodanie katalogu głównego projektu do sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import wszystkich modeli SQLModel, aby zarejestrować metadane tabel
from src.database import models  # noqa: F401
from src.database.engine import get_database_url

# Obiekt konfiguracyjny Alembic
config = context.config

# Konfiguracja loggerów z pliku konfiguracyjnego
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Dynamiczne wstrzyknięcie aktualnego adresu URL bazy danych ze zmiennych środowiskowych
config.set_main_option("sqlalchemy.url", get_database_url())

# Obiekt MetaData z modelami SQLModel do automatycznego wykrywania zmian (autogenerate)
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Uruchamia migracje w trybie 'offline'.

    Generuje skrypty SQL bez aktywnego połączenia z serwerem bazy danych.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Uruchamia migracje w trybie 'online' z aktywnym połączeniem do PostgreSQL."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
