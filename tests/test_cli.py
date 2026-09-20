"""Testy jednostkowe narzędzia CLI administratora (Typer)."""

from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


def test_cli_help() -> None:
    """Weryfikuje poprawność wyświetlania pomocy konsolowej."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "add-promise" in result.output
    assert "force-evaluate" in result.output


def test_cli_add_promise_help() -> None:
    """Weryfikuje parametry komendy add-promise."""
    result = runner.invoke(app, ["add-promise", "--help"])
    assert result.exit_code == 0
    assert "--party" in result.output
    assert "--title" in result.output
    assert "--text" in result.output


def test_cli_force_evaluate_help() -> None:
    """Weryfikuje parametry komendy force-evaluate."""
    result = runner.invoke(app, ["force-evaluate", "--help"])
    assert result.exit_code == 0
    assert "--bill-id" in result.output
