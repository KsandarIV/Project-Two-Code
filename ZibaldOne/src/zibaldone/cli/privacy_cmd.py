"""`zbone privacy …` and `zbone data …`: transparency about the user's data."""

import typer

from zibaldone.cli.common import ensure_consent
from zibaldone.core.privacy import NOTICE_VERSION, notice_text
from zibaldone.storage.paths import data_dir, folder_usage, human_size
from zibaldone.storage.settings import consent_status, record_consent

privacy_app = typer.Typer(help="Dove sono i tuoi dati e quali sono i rischi.")
data_app = typer.Typer(help="Informazioni sulla cartella dati.", no_args_is_help=True)


@privacy_app.callback(invoke_without_command=True)
def privacy_report(ctx: typer.Context) -> None:
    """Mostra avviso privacy, cartella dati, spazio usato e stato del consenso."""
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
    """Accetta l'avviso privacy senza la domanda interattiva."""
    folder = data_dir()
    typer.echo(notice_text(folder) + "\n")
    record_consent(folder, accepted=True, notice_version=NOTICE_VERSION)
    typer.echo(f"Consenso salvato. La tua cartella dati è {folder}")


@privacy_app.command("revoke")
def privacy_revoke() -> None:
    """Revoca il consenso; i file restano dove sono finché non li cancelli."""
    folder = data_dir()
    if not folder.exists():
        typer.echo("Non c'è nessun consenso da revocare: la cartella dati non esiste.")
        return
    record_consent(folder, accepted=False, notice_version=NOTICE_VERSION)
    typer.echo("Consenso revocato. ZibaldOne te lo richiederà al prossimo comando.")
    typer.echo(f"I tuoi file restano in {folder}: puoi cancellarli quando vuoi.")


@data_app.command("path")
def show_data_path() -> None:
    """Stampa il percorso della cartella dati."""
    ensure_consent()
    typer.echo(str(data_dir()))
