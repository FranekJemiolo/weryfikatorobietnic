"""Skrypt inicjalizacyjny (Seed) ładujący Złotą Bazę Obietnic Wyborczych do bazy PostgreSQL."""

import argparse
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import Engine
from sqlmodel import Session, select

from src.database.engine import get_engine, init_db
from src.database.models import Promise, PromiseStatus

DEFAULT_YAML_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "initial_promises.yaml"


class PromiseSeeder:
    """Zarządza idempotentnym ładowaniem obietnic wyborczych z pliku YAML do bazy danych."""

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine or get_engine()

    def seed_from_yaml(self, yaml_path: Path | str = DEFAULT_YAML_PATH) -> dict[str, int]:
        """Wczytuje obietnice z pliku YAML i wykonuje operację UPSERT w bazie danych.

        Args:
            yaml_path: Ścieżka do pliku YAML ze Złotą Bazą Obietnic.

        Returns:
            Słownik ze statystykami: {'total': X, 'inserted': Y, 'updated': Z}.
        """
        path = Path(yaml_path)
        if not path.is_file():
            raise FileNotFoundError(f"Nie znaleziono pliku ze Złotą Bazą Obietnic: {path}")

        with open(path, encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}

        promises_data = data.get("promises", [])
        if not isinstance(promises_data, list):
            raise ValueError(
                "Nieprawidłowa struktura YAML - oczekiwano listy pod kluczem 'promises'."
            )

        inserted_count = 0
        updated_count = 0

        with Session(self.engine) as session:
            for item in promises_data:
                promise_id = str(item["id"])
                title = str(item["title"])
                party = str(item["party"])
                full_text = str(item["full_text"])
                category = str(item["category"])
                raw_status = str(item.get("status", "NEW"))

                try:
                    status = PromiseStatus(raw_status)
                except ValueError:
                    status = PromiseStatus.NEW

                # Sprawdzenie istnienia rekordu po unikalnym ID
                statement = select(Promise).where(Promise.id == promise_id)
                existing_promise = session.exec(statement).first()

                if existing_promise:
                    # Aktualizacja istniejącego rekordu (UPSERT)
                    existing_promise.title = title
                    existing_promise.party = party
                    existing_promise.full_text = full_text
                    existing_promise.category = category
                    existing_promise.status = status
                    session.add(existing_promise)
                    updated_count += 1
                else:
                    # Dodanie nowego rekordu
                    new_promise = Promise(
                        id=promise_id,
                        title=title,
                        party=party,
                        full_text=full_text,
                        category=category,
                        status=status,
                    )
                    session.add(new_promise)
                    inserted_count += 1

            session.commit()

        print(
            f"✅ Załadowano obietnice z {path.name}: "
            f"Łącznie {len(promises_data)}, Nowe: {inserted_count}, Zaktualizowane: {updated_count}"
        )
        return {
            "total": len(promises_data),
            "inserted": inserted_count,
            "updated": updated_count,
        }


def main() -> None:
    """Punkt wejścia skryptu CLI."""
    parser = argparse.ArgumentParser(description="Seed bazy danych obietnicami wyborczymi z YAML.")
    parser.add_argument(
        "--file",
        type=str,
        default=str(DEFAULT_YAML_PATH),
        help="Ścieżka do pliku YAML z obietnicami",
    )
    parser.add_argument(
        "--init-tables",
        action="store_true",
        help="Automatycznie utwórz tabele przed seedowaniem",
    )
    args = parser.parse_args()

    engine = get_engine()
    if args.init_tables:
        init_db(engine)

    seeder = PromiseSeeder(engine)
    seeder.seed_from_yaml(args.file)


if __name__ == "__main__":
    main()
