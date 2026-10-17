"""`zbone export …`: every entry as Markdown (Obsidian) or CSV, in a zip file."""

from datetime import date
from pathlib import Path
from typing import Callable, Optional

import typer

from zibaldone.cli.common import ask_yes_no, fail, open_store
from zibaldone.storage.database import Store
from zibaldone.storage.export import ExportResult, export_csv, export_markdown

export_app = typer.Typer(help="Esporta tutte le voci in Markdown (per Obsidian) o in CSV, dentro un file zip.", no_args_is_help=True)

NOT_ENCRYPTED = "Attenzione: il file non è cifrato. Chi lo apre legge le tue voci: conservalo con cura e cancellalo quando non serve più."
OUTPUT_HELP = "il file .zip da creare (di base nella cartella attuale)"


def run_export(kind: str, output: Optional[Path], export: Callable[[Store, Path], ExportResult]) -> None:
    with open_store() as store:
        if store.count_entries() == 0:
            typer.echo("Nessuna voce da esportare.")
            return
        target = output or Path(f"zibaldone-{kind}-{date.today().isoformat()}.zip")
        if target.exists() and not ask_yes_no(f"Il file {target} esiste già. Sovrascriverlo?"):
            typer.echo("Va bene: non ho esportato nulla.")
            raise typer.Exit()
        try:
            result = export(store, target)
        except OSError as error:
            fail(f"non riesco a scrivere {target}: {error}")
    typer.echo(f"File creato: {result.path.resolve()} (voci: {result.entries}, modelli: {result.templates})")
    typer.echo(NOT_ENCRYPTED)


@export_app.command("markdown")
def export_markdown_command(output: Optional[Path] = typer.Option(None, "--output", "-o", help=OUTPUT_HELP)) -> None:
    """Esporta le voci in Markdown, una cartella per modello (va bene per Obsidian)."""
    run_export("markdown", output, export_markdown)


@export_app.command("csv")
def export_csv_command(output: Optional[Path] = typer.Option(None, "--output", "-o", help=OUTPUT_HELP)) -> None:
    """Esporta le voci in CSV: un file per modello, una colonna per blocco."""
    run_export("csv", output, export_csv)
