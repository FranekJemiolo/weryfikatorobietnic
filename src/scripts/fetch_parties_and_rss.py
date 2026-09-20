"""Skrypt wsadowy do pobierania danych ze stron wszystkich partii politycznych oraz kanałów RSS.

Pobiera deklaracje programowe ze stron partii politycznych (KO, PiS, TD, Lewica, Konfederacja, Razem)
oraz najnowsze komunikaty z kanałów RSS (KPRM, RCL, Sejm, Senat, partie), zapisując dane w bazie PostgreSQL
z zachowaniem limitów czasowych i polityki uprzejmości (opóźnienia między zapytaniami).
"""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlmodel import Session

from src.collectors.rss_collector import RSSCollector
from src.database.engine import get_engine, init_db
from src.scrapers.party_watchdog import PartyWatchdog

app = typer.Typer(
    name="fetch-parties-and-rss",
    help="Pobiera dane ze stron partii politycznych oraz oficjalnych kanałów RSS/Atom.",
    add_completion=False,
)
console = Console()


@app.command()
def main(
    fetch_rss: Annotated[
        bool, typer.Option("--rss/--no-rss", help="Włącz/wyłącz pobieranie kanałów RSS")
    ] = True,
    fetch_web: Annotated[
        bool, typer.Option("--web/--no-web", help="Włącz/wyłącz crawling stron partii")
    ] = True,
    delay: Annotated[
        float, typer.Option("--delay", "-d", help="Opóźnienie w sekundach między zapytaniami")
    ] = 0.5,
    config: Annotated[
        str, typer.Option("--config", "-c", help="Ścieżka do pliku konfiguracyjnego parties.yaml")
    ] = "config/parties.yaml",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Tryb testowy: pobiera dane bez zapisu do bazy")
    ] = False,
) -> None:
    """Główna funkcja orkiestrująca pobieranie danych ze stron partii oraz kanałów RSS."""
    config_path = Path(config)
    console.print(
        Panel.fit(
            f"[bold cyan]Weryfikator Obietnic[/bold cyan] - Ingestia Danych RSS i Stron Partyjnych\n"
            f"Plik konfiguracji: [yellow]{config_path}[/yellow] | Opóźnienie: [green]{delay}s[/green] | Dry-run: [magenta]{dry_run}[/magenta]",
            border_style="cyan",
        )
    )

    engine = get_engine()
    if not dry_run:
        init_db(engine)

    # -------------------------------------------------------------
    # 1. POBIERANIE KANAŁÓW RSS / ATOM
    # -------------------------------------------------------------
    total_rss_items = 0
    saved_rss_count = 0

    if fetch_rss:
        console.print(
            "\n[bold blue]=== Krok 1/2: Pobieranie kanałów informacyjnych RSS / Atom ===[/bold blue]"
        )
        rss_collector = RSSCollector(config_path=config_path, delay=delay)
        configured_feeds = rss_collector.load_configured_feeds()
        console.print(
            f"Znaleziono [bold]{len(configured_feeds)}[/bold] skonfigurowanych kanałów RSS/Atom."
        )

        rss_items = rss_collector.fetch_all(feeds=configured_feeds, delay=delay)
        total_rss_items = len(rss_items)

        if not dry_run and rss_items:
            with Session(engine) as session:
                saved_rss_count = rss_collector.save_items_to_db(session, rss_items)
        else:
            saved_rss_count = total_rss_items

        rss_table = Table(title="Podsumowanie Pobierania RSS", border_style="blue")
        rss_table.add_column("Kanał", style="cyan")
        rss_table.add_column("Pobrane Wpisy", justify="right", style="green")
        rss_table.add_column("Kategoria", style="magenta")

        # Agregacja per źródło
        feed_counts: dict[str, int] = {}
        for it in rss_items:
            feed_counts[it.source_name] = feed_counts.get(it.source_name, 0) + 1

        for feed in configured_feeds:
            name = feed.get("name", "Nieznany")
            cnt = feed_counts.get(name, 0)
            cat = feed.get("category", "-")
            rss_table.add_row(name, str(cnt), cat)

        console.print(rss_table)
        console.print(
            f"Łącznie pobrano: [bold green]{total_rss_items}[/bold green] wpisów RSS "
            f"([bold]{saved_rss_count}[/bold] nowych w bazie)."
        )

    # -------------------------------------------------------------
    # 2. AUDYT STRON PROGRAMOWYCH PARTII POLITYCZNYCH
    # -------------------------------------------------------------
    total_web_targets = 0
    changed_targets_count = 0

    if fetch_web:
        console.print(
            "\n[bold green]=== Krok 2/2: Audyt stron wszystkich partii politycznych ===[/bold green]"
        )
        targets = PartyWatchdog.load_targets_from_yaml(config_path=config_path)
        total_web_targets = len(targets)
        console.print(
            f"Znaleziono [bold]{total_web_targets}[/bold] monitorowanych stron partii politycznych."
        )

        watchdog = PartyWatchdog(engine=engine, delay=delay)
        web_results = watchdog.monitor_all(targets)

        web_table = Table(title="Wyniki Audytu Stron Partii Politycznych", border_style="green")
        web_table.add_column("ID Obietnicy", style="cyan")
        web_table.add_column("Partia", style="yellow")
        web_table.add_column("Status Zmiany", style="bold")
        web_table.add_column("URL", style="dim", max_width=45, overflow="ellipsis")

        for res in web_results:
            p_id = res.get("promise_id", "")
            party = p_id.split("-")[0] if "-" in p_id else "INNE"
            url = res.get("url", "")
            err_val = str(res.get("error", ""))
            if err_val:
                status_str = f"[red]Błąd: {err_val[:25]}...[/red]"
            elif res.get("is_changed"):
                status_str = "[yellow]⚠️ CICHA ZMIANA[/yellow]"
                changed_targets_count += 1

            elif res.get("is_initial"):
                status_str = "[blue]Pierwsza rejestracja[/blue]"
            else:
                status_str = "[green]Brak zmian (spójny)[/green]"

            web_table.add_row(p_id, party, status_str, url)

        console.print(web_table)

    console.print(
        Panel.fit(
            f"[bold green]Ingestia zakończona pomyślnie![/bold green]\n"
            f"• Wpisy RSS: [bold]{total_rss_items}[/bold] (zapisano: {saved_rss_count})\n"
            f"• Strony partii: [bold]{total_web_targets}[/bold] (wykryto zmian: {changed_targets_count})",
            border_style="green",
        )
    )


if __name__ == "__main__":
    app()
