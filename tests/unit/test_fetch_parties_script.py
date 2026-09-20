"""Testy jednostkowe skryptu pobierania danych partii i RSS (fetch_parties_and_rss)."""

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from src.cli.main import app
from src.collectors.rss_collector import RSSCollector
from src.scrapers.party_watchdog import PartyWatchdog

runner = CliRunner()


def test_load_targets_from_yaml() -> None:
    """Weryfikuje poprawne wczytywanie celów monitoringu partii z config/parties.yaml."""
    targets = PartyWatchdog.load_targets_from_yaml("config/parties.yaml")
    assert len(targets) > 0

    # Sprawdzenie obecności głównych partii w celach
    parties = {t["party"] for t in targets}
    assert "KO" in parties
    assert "PIS" in parties
    assert "PL2050" in parties
    assert "PSL" in parties
    assert "LEWICA" in parties
    assert "RAZEM" in parties
    assert "KONF" in parties


def test_load_configured_feeds_from_yaml() -> None:
    """Weryfikuje poprawne wczytywanie kanałów RSS z config/parties.yaml."""
    collector = RSSCollector(config_path="config/parties.yaml")
    feeds = collector.load_configured_feeds()
    assert len(feeds) > 0

    urls = [f["url"] for f in feeds]
    # Przykładowe feedy rządowe i partyjne
    assert any("gov.pl" in u for u in urls)
    assert any("partiarazem.pl" in u or "wolnosc.pl" in u for u in urls)


def test_cli_fetch_data_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Weryfikuje uruchomienie komendy fetch-data w trybie dry-run."""
    # Mockujemy pobieranie, by test był w 100% offline
    mock_rss_fetch = MagicMock(return_value=[])
    mock_web_monitor = MagicMock(return_value=[])

    monkeypatch.setattr(RSSCollector, "fetch_all", mock_rss_fetch)
    monkeypatch.setattr(PartyWatchdog, "monitor_all", mock_web_monitor)

    result = runner.invoke(app, ["fetch-data", "--dry-run", "--delay", "0"])
    assert result.exit_code == 0
    assert "Ingestia zakończona pomyślnie" in result.output
