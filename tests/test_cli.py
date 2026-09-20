"""Testy jednostkowe narzędzia CLI administratora (Typer)."""

import re

from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


def _clean_output(text: str) -> str:
    """Usuwa sekwencje ucieczki ANSI (Rich) z wyjścia konsoli."""
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


def test_cli_help() -> None:
    """Weryfikuje poprawność wyświetlania pomocy konsolowej."""
    result = runner.invoke(app, ["--help"], env={"NO_COLOR": "1", "TERM": "dumb"})
    assert result.exit_code == 0
    clean = _clean_output(result.output)
    assert "add-promise" in clean
    assert "force-evaluate" in clean


def test_cli_add_promise_help() -> None:
    """Weryfikuje parametry komendy add-promise."""
    result = runner.invoke(app, ["add-promise", "--help"], env={"NO_COLOR": "1", "TERM": "dumb"})
    assert result.exit_code == 0
    clean = _clean_output(result.output)
    assert "--party" in clean
    assert "--title" in clean
    assert "--text" in clean


def test_cli_force_evaluate_help() -> None:
    """Weryfikuje parametry komendy force-evaluate."""
    result = runner.invoke(app, ["force-evaluate", "--help"], env={"NO_COLOR": "1", "TERM": "dumb"})
    assert result.exit_code == 0
    clean = _clean_output(result.output)
    assert "--bill-id" in clean
