"""Root of the `zibaldone` / `zbone` command line."""

from typing import Callable, List, Optional, Tuple

import typer

from zibaldone import __version__
from zibaldone.cli.entry_cmd import entry_app
from zibaldone.cli.privacy_cmd import data_app, privacy_app
from zibaldone.cli.template_cmd import template_app

APP_NAME = "ZibaldOne"
APP_TAGLINE = "il tuo zibaldone personale, fatto a blocchi"

app = typer.Typer(
    name="zibaldone",
    help=f"{APP_NAME} — {APP_TAGLINE}. Disponibile anche come `zbone`.",
    add_completion=False,
    no_args_is_help=True,
)
app.add_typer(privacy_app, name="privacy")
app.add_typer(data_app, name="data")
app.add_typer(template_app, name="template")
app.add_typer(entry_app, name="entry")


def _first_line(callback: Optional[Callable]) -> str:
    doc = (callback.__doc__ or "").strip().splitlines() if callback else []
    return doc[0] if doc else ""


def command_summaries() -> List[Tuple[str, str]]:
    """Return (name, first help line) for every command and subcommand, sorted by name."""
    summaries = [
        (command.name or command.callback.__name__.replace("_", "-"), _first_line(command.callback))
        for command in app.registered_commands
    ]
    for group in app.registered_groups:
        callback = group.typer_instance.registered_callback
        if callback and callback.invoke_without_command:
            summaries.append((group.name, _first_line(callback.callback)))
        for command in group.typer_instance.registered_commands:
            summaries.append((f"{group.name} {command.name}", _first_line(command.callback)))
    return sorted(summaries)


@app.command("help")
def show_help() -> None:
    """Elenca tutti i comandi disponibili."""
    typer.echo(f"{APP_NAME} {__version__} — {APP_TAGLINE}\n")
    typer.echo("Uso: zibaldone <comando> [opzioni]   (alias corto: zbone)\n")
    typer.echo("Comandi:")
    summaries = command_summaries()
    width = max(len(name) for name, _ in summaries)
    for name, summary in summaries:
        typer.echo(f"  {name.ljust(width)}  {summary}")
    typer.echo("\nScrivi `zbone <comando> --help` per i dettagli di un comando.")


@app.command("version")
def show_version() -> None:
    """Stampa la versione installata."""
    typer.echo(f"{APP_NAME} {__version__}")


def main() -> None:
    app()
