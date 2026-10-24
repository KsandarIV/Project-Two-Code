"""Root of the `zibaldone` / `zbone` command line."""

from typing import Callable, List, Optional, Tuple

import typer

from zibaldone import __version__
from zibaldone.core.brand import APP_MOTTO, APP_NAME, APP_TAGLINE, MASCOTS, NOMENCLATURE, quote_of_the_day
from zibaldone.cli.account_cmd import account_app, cloud_app
from zibaldone.cli.anon_cmd import anon_app
from zibaldone.cli.area_cmd import area_app
from zibaldone.cli.backup_cmd import backup_app
from zibaldone.cli.common import fail
from zibaldone.cli.entry_cmd import entry_app
from zibaldone.cli.export_cmd import export_app
from zibaldone.cli.graph_cmd import graph_command
from zibaldone.cli.finance_cmd import finance_app
from zibaldone.cli.habit_cmd import habit_app
from zibaldone.cli.import_cmd import import_command
from zibaldone.cli.media_cmd import media_app
from zibaldone.cli.pack_cmd import pack_app
from zibaldone.cli.person_cmd import occasions_command, person_app
from zibaldone.cli.secret_cmd import secret_app
from zibaldone.cli.privacy_cmd import data_app, privacy_app
from zibaldone.cli.remind_cmd import remind_app
from zibaldone.cli.search_cmd import SEARCH_CONTEXT, links_command, search_command
from zibaldone.cli.stats_cmd import review_command, stats_command
from zibaldone.cli.template_cmd import template_app
from zibaldone.cli.update_cmd import check_updates
from zibaldone.cli.view_cmd import view_app


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
app.add_typer(pack_app, name="pack")
app.add_typer(backup_app, name="backup")
app.add_typer(export_app, name="export")
app.add_typer(account_app, name="account")
app.add_typer(cloud_app, name="cloud")
app.add_typer(remind_app, name="remind")
app.add_typer(anon_app, name="anon")
app.add_typer(area_app, name="area")
app.add_typer(person_app, name="persona")
app.add_typer(secret_app, name="segreti")
app.add_typer(media_app, name="allegati")
app.add_typer(finance_app, name="finanze")
app.add_typer(habit_app, name="abitudini")
app.add_typer(view_app, name="viste")
app.command("update")(check_updates)
app.command("ricorrenze")(occasions_command)
app.command("importa")(import_command)
app.command("search", context_settings=SEARCH_CONTEXT)(search_command)
app.command("links")(links_command)
app.command("graph")(graph_command)
app.command("stats")(stats_command)
app.command("review")(review_command)


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


@app.command("app")
def open_app(
    web: bool = typer.Option(False, "--web", help="apri nel browser invece che in una finestra"),
    port: int = typer.Option(0, "--port", help="porta del server web (0 = una libera)"),
    route: Optional[str] = typer.Option(None, "--route", help="la pagina da aprire, per esempio /voci o /scrivi/sera"),
) -> None:
    """Apre l'interfaccia grafica (in una finestra o nel browser)."""
    try:
        from zibaldone.ui.app import run
    except ImportError:
        fail('l\'interfaccia grafica non è installata: `pip install -e ".[ui]"` e riprova')
    run(web=web, port=port, route=route)  # consent and sign-in are asked by the app itself


@app.command("version")
def show_version() -> None:
    """Stampa la versione installata."""
    typer.echo(f"{APP_NAME} {__version__}")


@app.command("pensiero")
def show_quote() -> None:
    """Il pensiero del giorno, da un filosofo."""
    quote = quote_of_the_day()
    typer.echo(f"«{quote.text}»\n  — {quote.author}, {quote.source}")


@app.command("about")
def show_about() -> None:
    """Il nome, le mascotte e i nomi filosofici dell'app."""
    typer.echo(f"{APP_NAME} {__version__} — {APP_TAGLINE}. {APP_MOTTO}")
    typer.echo("Il nome viene dallo Zibaldone di pensieri di Giacomo Leopardi; One sta per tutto in uno.\n")
    typer.echo("Mascotte:")
    for mascot in MASCOTS:
        typer.echo(f"  {mascot.name:<7} {mascot.animal:<9} {mascot.sphere:<10} {mascot.story}")
    typer.echo("\nNomi:")
    for item in NOMENCLATURE.values():
        typer.echo(f"  {item.name:<17} {item.meaning} — {item.source}")


def main() -> None:
    app()
