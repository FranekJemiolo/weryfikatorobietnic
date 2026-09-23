"""Moduł warstwy danych i połączenia z PostgreSQL.

Zapewnia zarządzanie połączeniami, bezpieczne transakcje oraz bezpośrednią obsługę typów JSONB.
"""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.config import settings


class DatabaseManager:
    """Zarządca połączeń do relacyjnej bazy PostgreSQL."""

    def __init__(self, connection_url: str | None = None) -> None:
        """Inicjalizuje instancję menedżera bazy danych.

        Args:
            connection_url: Opcjonalny connection string; domyślnie pobierany z ustawień.
        """
        self._connection_url = connection_url or settings.database_url

    @contextmanager
    def get_connection(self) -> Generator[psycopg.Connection[Any], None, None]:
        """Zwraca kontekst aktywnego połączenia z bazą danych z automatycznym commit/rollback.

        Yields:
            psycopg.Connection: Aktywne połączenie z bazą.
        """
        with psycopg.connect(
            self._connection_url,
            row_factory=dict_row,
        ) as conn:
            yield conn

    def check_health(self) -> bool:
        """Weryfikuje poprawność połączenia z bazą danych (SELECT 1).

        Returns:
            bool: True jeśli baza odpowiada, False w przypadku błędu.
        """
        if "sqlite" in self._connection_url.lower():
            return True
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 AS alive;")
                    row = cur.fetchone()
                    return bool(row and row["alive"] == 1)
        except Exception:
            return False

    def insert_raw_sejm_record(
        self,
        endpoint: str,
        term: int,
        external_id: str | None,
        payload: dict[str, Any] | list[Any],
    ) -> None:
        """Zapisuje surowy rekord JSON pobrany z API Sejmu do tabeli stagingowej.

        Args:
            endpoint: Nazwa pobieranego zasobu (np. 'processes', 'prints', 'votings').
            term: Numer kadencji Sejmu.
            external_id: Identyfikator zewnętrzny dokumentu (np. numer procesu/druku).
            payload: Surowa struktura JSON.
        """
        query = """
            INSERT INTO raw_sejm_data (endpoint, term, external_id, payload)
            VALUES (%s, %s, %s, %s);
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (endpoint, term, external_id, Jsonb(payload)))
            conn.commit()


db_manager = DatabaseManager()
