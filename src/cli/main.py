"""Narzędzie CLI Administratora projektu 'Weryfikator Obietnic'."""

import hashlib
from datetime import UTC, datetime
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlmodel import Session, col, select

from src.ai.evaluator import PromiseEvaluator
from src.database.engine import get_engine
from src.database.models import Bill, BillArticle, Promise, PromiseStatus

app = typer.Typer(
    name="weryfikator-cli",
    help="Narzędzie administratorskie do zarządzania bazą obietnic i silnikiem AI w projekcie Weryfikator Obietnic.",
    add_completion=False,
)
console = Console()


@app.command(name="add-promise")
def add_promise(
    party: Annotated[
        str,
        typer.Option(
            "--party",
            "-p",
            help="Skrót partii lub komitetu (np. KO, PiS, Lewica, TD, Konfederacja)",
        ),
    ],
    title: Annotated[str, typer.Option("--title", "-t", help="Tytuł deklaracji wyborczej")],
    text: Annotated[str, typer.Option("--text", "-d", help="Pełna treść złożonej obietnicy")],
    category: Annotated[
        str, typer.Option("--category", "-c", help="Kategoria merytoryczna")
    ] = "Gospodarka",
) -> None:
    """Dodaje nową obietnicę wyborczą bezpośrednio do bazy danych PostgreSQL."""
    clean_party = party.strip().upper()
    slug_part = "".join(c for c in title.lower() if c.isalnum())[:10]
    hash_part = hashlib.md5(f"{clean_party}-{title}".encode()).hexdigest()[:6]
    promise_id = f"{clean_party}-{slug_part}-{hash_part}"

    engine = get_engine()
    with Session(engine) as session:
        existing = session.get(Promise, promise_id)
        if existing:
            console.print(
                f"[yellow]Obietnica o identyfikatorze [bold]{promise_id}[/bold] już istnieje w bazie. Aktualizuję treść...[/yellow]"
            )
            existing.party = clean_party
            existing.title = title
            existing.full_text = text
            existing.category = category
            session.add(existing)
            session.commit()
            session.refresh(existing)
            target = existing
        else:
            new_promise = Promise(
                id=promise_id,
                party=clean_party,
                title=title,
                full_text=text,
                category=category,
                status=PromiseStatus.IN_PROGRESS,
                created_at=datetime.now(UTC),
            )
            session.add(new_promise)
            session.commit()
            session.refresh(new_promise)
            target = new_promise

    panel_content = (
        f"[bold white]ID:[/bold white] [cyan]{target.id}[/cyan]\n"
        f"[bold white]Partia:[/bold white] [yellow]{target.party}[/yellow]\n"
        f"[bold white]Kategoria:[/bold white] [magenta]{target.category}[/magenta]\n"
        f"[bold white]Tytuł:[/bold white] {target.title}\n"
        f"[bold white]Status:[/bold white] [green]{target.status.value}[/green]"
    )
    console.print(
        Panel(
            panel_content,
            title="[bold green]✓ Pomyślnie zarejestrowano obietnicę w bazie danych[/bold green]",
            border_style="green",
        )
    )


@app.command(name="force-evaluate")
def force_evaluate(
    bill_id: Annotated[
        str, typer.Option("--bill-id", "-b", help="Identyfikator projektu ustawy w bazie danych")
    ],
    top_k: Annotated[
        int,
        typer.Option("--top-k", "-k", help="Liczba najbardziej pasujących artykułów z pgvector"),
    ] = 5,
) -> None:
    """Ręcznie wyzwala proces generowania wektorów i wnioskowania LLM dla konkretnego druku sejmowego."""
    engine = get_engine()
    with Session(engine) as session:
        bill = session.get(Bill, bill_id)
        if not bill:
            # Sprawdzenie czy podano sejm_print_num zamiast id
            bill_by_print = session.exec(
                select(Bill).where(col(Bill.sejm_print_num) == bill_id)
            ).first()
            if bill_by_print:
                bill = bill_by_print
            else:
                console.print(
                    f"[bold red]BŁĄD:[/bold red] Nie znaleziono projektu ustawy o ID lub druku '{bill_id}'."
                )
                raise typer.Exit(code=1)

        # Sprawdzenie obecności artykułów ustawy
        articles_count = session.exec(
            select(BillArticle).where(col(BillArticle.bill_id) == bill.id)
        ).all()

        active_promises = session.exec(
            select(Promise).where(
                col(Promise.status).in_([PromiseStatus.IN_PROGRESS, PromiseStatus.NEW])
            )
        ).all()

    console.print(
        f"[cyan]Rozpoczynam audyt RAG dla projektu:[/cyan] [bold]{bill.title}[/bold] (Druk nr {bill.sejm_print_num or 'Brak'})"
    )
    console.print(
        f"Liczba stypizowanych artykułów w pgvector: [yellow]{len(articles_count)}[/yellow] | Aktywnych obietnic do zderzenia: [yellow]{len(active_promises)}[/yellow]"
    )

    if not active_promises:
        console.print("[yellow]Brak aktywnych obietnic w bazie danych do porównania.[/yellow]")
        return

    evaluator = PromiseEvaluator(engine=engine)
    results_table = Table(
        title=f"Wyniki Ewaluacji LLM (Druk: {bill.sejm_print_num or bill.id})",
        show_header=True,
        header_style="bold magenta",
    )
    results_table.add_column("ID Obietnicy", style="cyan", width=22)
    results_table.add_column("Partia", style="yellow", width=8)
    results_table.add_column("Status LLM", style="bold", width=16)
    results_table.add_column("Pewność", justify="right", width=10)
    results_table.add_column("Uzasadnienie z Artykułów", style="white")

    with console.status("[bold green]Generowanie osadzeń wektorowych i wnioskowanie LLM..."):
        for promise in active_promises:
            articles = evaluator.get_relevant_articles(
                promise_id=promise.id,
                bill_id=bill.id,
                top_k=top_k,
            )
            evaluation = evaluator.evaluate_bill_against_promise(promise, articles)
            evaluator.save_evaluation(
                promise_id=promise.id,
                bill_id=bill.id,
                evaluation=evaluation,
            )

            status_style = {
                "W_PELNI": "[green]W PEŁNI[/green]",
                "CZESCIOWO": "[yellow]CZĘŚCIOWO[/yellow]",
                "SPRZECZNA": "[red]SPRZECZNA[/red]",
                "BRAK_POWIAZANIA": "[dim]BRAK[/dim]",
            }.get(evaluation.alignment_status, evaluation.alignment_status)

            results_table.add_row(
                promise.id,
                promise.party,
                status_style,
                f"{evaluation.score * 100:.0f}%",
                evaluation.justification[:100]
                + ("..." if len(evaluation.justification) > 100 else ""),
            )

    console.print(results_table)
    console.print(
        "[bold green]✓ Zakończono audyt legislacyjny. Wyniki zaktualizowane w tabeli LLMEvaluation.[/bold green]"
    )


@app.command(name="fetch-data")
def fetch_data(
    rss: Annotated[
        bool, typer.Option("--rss/--no-rss", help="Pobieraj kanały informacyjne RSS/Atom")
    ] = True,
    web: Annotated[
        bool,
        typer.Option("--web/--no-web", help="Audytuj strony internetowe partii politycznych"),
    ] = True,
    delay: Annotated[
        float, typer.Option("--delay", "-d", help="Opóźnienie w sekundach między zapytaniami")
    ] = 0.5,
    config: Annotated[
        str, typer.Option("--config", "-c", help="Ścieżka do pliku parties.yaml")
    ] = "config/parties.yaml",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Tryb testowy bez zapisu do bazy")
    ] = False,
) -> None:
    """Pobiera deklaracje ze stron partii politycznych oraz oficjalnych kanałów RSS/Atom."""
    from src.scripts.fetch_parties_and_rss import main as run_fetch

    run_fetch(fetch_rss=rss, fetch_web=web, delay=delay, config=config, dry_run=dry_run)


if __name__ == "__main__":
    app()
