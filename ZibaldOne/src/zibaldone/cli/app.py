from typing import List, Tuple

import typer

from zibaldone import __version__
from zibaldone.core.privacy import NOTICE_VERSION, notice_text
from zibaldone.storage.paths import data_dir, folder_usage, human_size
from zibaldone.storage.settings import consent_status, has_consent, record_consent

APP_NAME = "ZibaldOne"
APP_TAGLINE = "a composable, local-first journal"

YES = {"s", "si", "sì", "y", "yes"}
NO = {"n", "no"}

app = typer.Typer(
    name="zibaldone",
    help=f"{APP_NAME} — {APP_TAGLINE}. Also available as `zbone`.",
    add_completion=False,
    no_args_is_help=True,
)
privacy_app = typer.Typer(help="Show where your data lives and what the risks are.")
data_app = typer.Typer(help="Information about your data folder.")
app.add_typer(privacy_app, name="privacy", invoke_without_command=True)
app.add_typer(data_app, name="data")


def command_summaries() -> List[Tuple[str, str]]:
    """Return (name, first help line) for every command and subcommand, sorted by name."""

    def first_line(callback) -> str:
        doc = (callback.__doc__ or "").strip().splitlines() if callback else []
        return doc[0] if doc else ""

    summaries = [
        (command.name or command.callback.__name__.replace("_", "-"), first_line(command.callback))
        for command in app.registered_commands
    ]
    for group in app.registered_groups:
        if group.typer_instance.registered_callback:
            summaries.append((group.name, first_line(group.typer_instance.registered_callback.callback)))
        for command in group.typer_instance.registered_commands:
            summaries.append((f"{group.name} {command.name}", first_line(command.callback)))
    return sorted(summaries)


def ask_yes_no(question: str) -> bool:
    """Ask until the answer is yes or no, in Italian or English."""
    while True:
        answer = typer.prompt(f"{question} (sì/no)").strip().lower()
        if answer in YES:
            return True
        if answer in NO:
            return False
        typer.echo("Rispondi sì oppure no.")


def ensure_consent() -> None:
    """At first start, show the privacy notice and stop unless the user accepts.

    Every command that reads or writes user data calls this first.
    `help`, `version` and `privacy` work without it.
    """
    folder = data_dir()
    if has_consent(folder, NOTICE_VERSION):
        return
    typer.echo(notice_text(folder) + "\n")
    if not ask_yes_no("Continuare?"):
        typer.echo("Va bene: ZibaldOne non ha salvato nulla. Te lo richiederà al prossimo avvio.")
        raise typer.Exit(code=1)
    record_consent(folder, accepted=True, notice_version=NOTICE_VERSION)
    typer.echo(f"Consenso salvato. La tua cartella dati è {folder}\n")


@app.command("help")
def show_help() -> None:
    """List every available command."""
    typer.echo(f"{APP_NAME} {__version__} — {APP_TAGLINE}\n")
    typer.echo("Usage: zibaldone <command> [options]   (short alias: zbone)\n")
    typer.echo("Commands:")
    summaries = command_summaries()
    width = max(len(name) for name, _ in summaries)
    for name, summary in summaries:
        typer.echo(f"  {name.ljust(width)}  {summary}")
    typer.echo("\nRun `zibaldone <command> --help` for details on a command.")


@app.command("version")
def show_version() -> None:
    """Print the installed version."""
    typer.echo(f"{APP_NAME} {__version__}")


@privacy_app.callback()
def privacy_report(ctx: typer.Context) -> None:
    """Show the privacy notice, the data folder, its size and your consent."""
    if ctx.invoked_subcommand is not None:
        return
    folder = data_dir()
    files, size = folder_usage(folder)
    status = consent_status(folder) if folder.exists() else {}
    if status.get("accepted") is True and status.get("notice_version") == NOTICE_VERSION:
        consent = f"accettato il {status['decided_at']}"
    elif status.get("accepted") is True:
        consent = "accettato per un avviso precedente: te lo richiederà"
    elif status:
        consent = f"revocato il {status['decided_at']}"
    else:
        consent = "non ancora dato"
    typer.echo(notice_text(folder) + "\n")
    typer.echo(f"Cartella esiste: {'sì' if folder.exists() else 'no'}")
    typer.echo(f"Contenuto:       {files} file, {human_size(size)}")
    typer.echo(f"Consenso:        {consent}")


@privacy_app.command("accept")
def privacy_accept() -> None:
    """Accept the privacy notice without the interactive question."""
    folder = data_dir()
    typer.echo(notice_text(folder) + "\n")
    record_consent(folder, accepted=True, notice_version=NOTICE_VERSION)
    typer.echo(f"Consenso salvato. La tua cartella dati è {folder}")


@privacy_app.command("revoke")
def privacy_revoke() -> None:
    """Revoke consent; your files stay where they are until you delete them."""
    folder = data_dir()
    if not folder.exists():
        typer.echo("Non c'è nessun consenso da revocare: la cartella dati non esiste.")
        return
    record_consent(folder, accepted=False, notice_version=NOTICE_VERSION)
    typer.echo("Consenso revocato. ZibaldOne te lo richiederà al prossimo comando.")
    typer.echo(f"I tuoi file restano in {folder}: puoi cancellarli quando vuoi.")


@data_app.command("path")
def show_data_path() -> None:
    """Print the data folder path."""
    ensure_consent()
    typer.echo(str(data_dir()))


def main() -> None:
    app()
