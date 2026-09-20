"""Testy jednostkowe skryptu inicjalizującego (Seed) Złotą Bazę Obietnic."""

import tempfile
from pathlib import Path

from sqlmodel import Session, create_engine, select

from src.database.engine import init_db
from src.database.models import Promise, PromiseStatus
from src.scripts.seed_promises import PromiseSeeder


def test_seed_promises_idempotency() -> None:
    """Weryfikuje, czy ponowne uruchomienie seeder'a nie dubluje wpisów (operacja UPSERT)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    init_db(engine)

    yaml_content = """
promises:
  - id: "TEST-001"
    party: "TEST_PARTY"
    title: "Obietnica testowa A"
    full_text: "Treść obietnicy testowej A"
    category: "Test"
    status: "NEW"
  - id: "TEST-002"
    party: "TEST_PARTY"
    title: "Obietnica testowa B"
    full_text: "Treść obietnicy testowej B"
    category: "Test"
    status: "IN_PROGRESS"
"""

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        temp_path = Path(f.name)

    try:
        seeder = PromiseSeeder(engine)

        # Pierwsze uruchomienie: dodanie 2 nowych obietnic
        stats1 = seeder.seed_from_yaml(temp_path)
        assert stats1["total"] == 2
        assert stats1["inserted"] == 2
        assert stats1["updated"] == 0

        with Session(engine) as session:
            all_promises = session.exec(select(Promise)).all()
            assert len(all_promises) == 2

        # Drugie uruchomienie z tym samym plikiem: 0 nowych wpisów, 2 aktualizacje
        stats2 = seeder.seed_from_yaml(temp_path)
        assert stats2["total"] == 2
        assert stats2["inserted"] == 0
        assert stats2["updated"] == 2

        with Session(engine) as session:
            all_promises_after = session.exec(select(Promise)).all()
            assert len(all_promises_after) == 2
            p1 = session.get(Promise, "TEST-001")
            assert p1 is not None
            assert p1.status == PromiseStatus.NEW
    finally:
        if temp_path.exists():
            temp_path.unlink()
