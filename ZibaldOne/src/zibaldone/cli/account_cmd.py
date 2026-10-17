"""`zbone account …` and `zbone cloud …`: who you are on this device and
where the encrypted copies of the backups go (Le Nuvole, ADR-0007).

The passphrase is asked with hidden input, never taken from flags. The
Google sign-in opens the browser and waits for Google to send it back to a
small local page on 127.0.0.1.
"""

import webbrowser
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

import typer

from zibaldone.cli.common import ask_yes_no, ensure_consent, fail, warn
from zibaldone.cloud import account, sync
from zibaldone.cloud.http import CloudError, OfflineError
from zibaldone.core.crypto import CryptoError
from zibaldone.storage import backups, keys
from zibaldone.storage.backups import BackupError
from zibaldone.storage.database import database_path
from zibaldone.storage.keys import KeysError
from zibaldone.storage.paths import data_dir, human_size
from zibaldone.storage.settings import SettingsError

account_app = typer.Typer(help="Account: chi sei su questo dispositivo (accesso con Google).")
cloud_app = typer.Typer(help="Le Nuvole · Copie cifrate dei backup su Google Drive o in una cartella.")

KNOWN_ERRORS = (CloudError, KeysError, BackupError, CryptoError, SettingsError)

GOOGLE_RECOVERY_TRADEOFF = """Recupero con l'account Google (facoltativo):
se lo attivi, su un dispositivo nuovo ti basterà entrare con Google per riavere i backup,
anche senza passphrase. Il prezzo: chi riesce a entrare nel tuo account Google può aprirli.
Se non lo attivi, servono la passphrase o il codice di recupero: più sicuro, ma non dimenticarli.
"""


@contextmanager
def cloud_errors() -> Iterator[None]:
    """Turn known errors into a short message, never a stack trace."""
    try:
        yield
    except KNOWN_ERRORS as error:
        fail(str(error))
    except OSError as error:
        fail(f"operazione sui file non riuscita: {error}")


def local_time(iso_or_moment) -> str:
    try:
        moment = datetime.fromisoformat(iso_or_moment) if isinstance(iso_or_moment, str) else iso_or_moment
    except ValueError:
        return str(iso_or_moment)
    return moment.astimezone().strftime("%d/%m/%Y %H:%M")


# * — account —


def row(label: str, value: str, color: Optional[str] = None) -> None:
    typer.secho(f"{label + ':':<20}{value}", fg=color)


def print_account(status: account.AccountStatus) -> None:
    if status.signed_in:
        who = f"{status.name} <{status.email}>" if status.name else status.email
        row("Account", f"{who} (Google)")
        row("Permesso Drive", "sì" if status.drive_allowed else "no (solo locale o cartella)")
    elif status.google_configured:
        row("Account", "non sei entrato. Entra con: zbone account login")
    else:
        row("Account", "nessuno (l'accesso con Google non è configurato in questa copia: funziona tutto in locale)")


def run_login(open_browser: bool = True) -> account.AccountStatus:
    """Sign in with Google from the terminal; at the first sign-in, also ask where the copies go."""
    folder = data_dir()

    def show(url: str) -> None:
        typer.echo("Si apre il browser sulla pagina di Google. Se non si apre, copia questo indirizzo nel browser:")
        typer.echo(f"  {url}\n")
        typer.echo("Aspetto che tu finisca l'accesso (puoi annullare con Ctrl+C)…")
        if open_browser:
            webbrowser.open(url)

    with cloud_errors():
        before = account.account_status(folder)
        status = account.sign_in_with_google(folder, open_browser=show)
    typer.echo(f"Sei entrato come {status.email}.")
    if before.signed_in and before.email != status.email and before.mode == "google":
        typer.echo("È un account diverso dal precedente: le copie su Drive sono tornate a solo locale.")
    if not status.drive_allowed:
        typer.echo("Non hai dato il permesso per Drive: le copie possono stare solo qui o in una cartella (`zbone cloud use folder PERCORSO`).")
    elif not _mode_chosen(folder):
        choose_destination_at_first_sign_in(folder)
    return status


def _mode_chosen(folder: Path) -> bool:
    from zibaldone.storage.settings import load_settings

    cloud = load_settings(folder).get("cloud")
    return isinstance(cloud, dict) and "mode" in cloud


def choose_destination_at_first_sign_in(folder: Path) -> None:
    typer.echo("\nDove vuoi tenere i backup?")
    typer.echo("  - solo su questo dispositivo (puoi cambiare idea quando vuoi);")
    typer.echo("  - anche sul tuo Google Drive, cifrati, nello spazio nascosto dell'app.")
    if ask_yes_no("Tenere una copia cifrata anche su Google Drive?"):
        use_google(folder)
    else:
        with cloud_errors():
            account.choose_mode(folder, "local")
        typer.echo("Va bene: solo locale. Per cambiare: zbone cloud use google")


@account_app.callback(invoke_without_command=True)
def account_status(ctx: typer.Context) -> None:
    """Mostra con quale account sei entrato."""
    if ctx.invoked_subcommand is not None:
        return
    ensure_consent()
    with cloud_errors():
        print_account(account.account_status(data_dir()))


@account_app.command("login")
def login(no_browser: bool = typer.Option(False, "--no-browser", help="non aprire il browser: stampa solo l'indirizzo da aprire")) -> None:
    """Entra con il tuo account Google."""
    ensure_consent()
    run_login(open_browser=not no_browser)


@account_app.command("logout")
def logout(yes: bool = typer.Option(False, "--yes", "-y", help="non chiedere conferma")) -> None:
    """Esci dall'account su questo dispositivo: diario e backup restano."""
    ensure_consent()
    folder = data_dir()
    with cloud_errors():
        status = account.account_status(folder)
    if not status.signed_in:
        typer.echo("Non sei entrato con nessun account.")
        return
    question = f"Uscire da {status.email} su questo dispositivo? Diario e backup restano qui"
    if not yes and not ask_yes_no(question):
        typer.echo("Va bene: sei ancora dentro.")
        raise typer.Exit()
    with cloud_errors():
        revoked = account.sign_out(folder)
    typer.echo("Sei uscito. Le copie già su Drive restano lì; da ora i backup restano solo su questo dispositivo.")
    if not revoked:
        typer.echo("Google non ha confermato la revoca (sei offline?): puoi toglierla da myaccount.google.com/permissions.")


# * — cloud —


def print_cloud(folder: Path, status: account.AccountStatus) -> None:
    row("Copie", status.mode_label)
    if status.mode == "folder":
        row("Cartella", str(status.folder_path))
    if status.mode == "google":
        row("Google Drive", f"{status.email}, nello spazio nascosto dell'app")
        row("Recupero con Google", "attivo" if status.google_recovery else "non attivo")
    if status.mode != "local":
        row("Ultima copia", local_time(status.last_sync) if status.last_sync else "mai")
        if status.last_sync_error:
            row("Problema", status.last_sync_error, typer.colors.YELLOW)
        if not keys.is_configured(folder):
            typer.echo("Le copie partono quando attivi la cifratura: zbone backup setup")


def first_sync(folder: Path) -> None:
    """Right after choosing a destination: upload what is there, if encryption is on."""
    if not keys.is_configured(folder):
        typer.echo("Le copie partono quando attivi la cifratura dei backup: zbone backup setup (nessun dato esce in chiaro).")
        return
    try:
        result = sync.sync_now(folder)
    except OfflineError as error:
        warn(f"{error}. Riproverò al prossimo backup automatico.")
        return
    except KNOWN_ERRORS as error:
        warn(f"prima copia non riuscita: {error}")
        return
    typer.echo(result.message)


def offer_google_recovery(folder: Path, passphrase: Optional[str] = None) -> None:
    """Explain the trade-off and turn on recovery through Google if the user wants it."""
    status = account.account_status(folder)
    if status.mode != "google" or status.google_recovery or not keys.is_configured(folder):
        return
    typer.echo("\n" + GOOGLE_RECOVERY_TRADEOFF)
    if not ask_yes_no("Attivare il recupero con l'account Google?"):
        typer.echo("Va bene: per recuperare i backup serviranno la passphrase o il codice di recupero.")
        return
    secret = passphrase or typer.prompt("Passphrase dei backup", hide_input=True)
    try:
        sync.enable_google_recovery(folder, secret)
    except OfflineError as error:
        warn(f"{error}. Puoi attivarlo più tardi con `zbone cloud recovery on`.")
        return
    except KNOWN_ERRORS as error:
        warn(f"recupero con Google non attivato: {error}. Riprova con `zbone cloud recovery on`.")
        return
    typer.echo("Recupero con Google attivo. Per toglierlo: zbone cloud recovery off")


def use_google(folder: Path) -> None:
    with cloud_errors():
        status = account.choose_mode(folder, "google")
    typer.echo(f"Copie: {status.mode_label} ({status.email}). Su Drive vanno solo istantanee già cifrate.")
    offer_google_recovery(folder)
    first_sync(folder)


def after_encryption_setup(folder: Path, passphrase: str) -> None:
    """Called by `zbone backup setup`: offer recovery with Google and send the first copies."""
    try:
        status = account.account_status(folder)
    except CloudError:
        return
    if status.mode == "local":
        return
    offer_google_recovery(folder, passphrase)
    first_sync(folder)


@cloud_app.callback(invoke_without_command=True)
def cloud_status(ctx: typer.Context) -> None:
    """Mostra dove vanno le copie dei backup e com'è andata l'ultima."""
    if ctx.invoked_subcommand is not None:
        return
    ensure_consent()
    folder = data_dir()
    with cloud_errors():
        status = account.account_status(folder)
    print_account(status)
    print_cloud(folder, status)


@cloud_app.command("use")
def use_destination(
    mode: str = typer.Argument(..., metavar="MODALITÀ", help="local (solo locale), google (anche su Google Drive) o folder (anche in una cartella)"),
    path: Optional[Path] = typer.Argument(None, metavar="[PERCORSO]", help="la cartella, per la modalità folder: una chiavetta o una cartella di OneDrive, Dropbox…"),
) -> None:
    """Sceglie dove tenere le copie cifrate dei backup."""
    ensure_consent()
    folder = data_dir()
    if mode == "google":
        use_google(folder)
        return
    with cloud_errors():
        status = account.choose_mode(folder, mode, str(path) if path else None)
    typer.echo(f"Copie: {status.mode_label}.")
    if mode == "local":
        typer.echo("Le copie che c'erano già fuori restano dove sono. Per cancellarle: zbone cloud forget (prima di cambiare modalità).")
        return
    typer.echo(f"Cartella: {status.folder_path}")
    first_sync(folder)


@cloud_app.command("sync")
def sync_command() -> None:
    """Copia adesso le istantanee cifrate nuove sulla destinazione scelta."""
    ensure_consent()
    with cloud_errors():
        result = sync.sync_now(data_dir())
    typer.echo(result.message)


@cloud_app.command("list")
def list_remote() -> None:
    """Elenca le istantanee che ci sono sulla destinazione."""
    ensure_consent()
    folder = data_dir()
    with cloud_errors():
        snapshots = sync.list_remote(folder)
    if not snapshots:
        typer.echo("Sulla destinazione non c'è ancora nessuna istantanea.")
        return
    for snapshot in snapshots:
        typer.echo(f"  {snapshot.id}  {local_time(snapshot.created_at)} · {human_size(snapshot.size)} · cifrata")
    typer.echo(f"\n{len(snapshots)} istantanee. Per riportarne una su questo dispositivo: zbone cloud recover [ID]")


@cloud_app.command("recover")
def recover(
    reference: Optional[str] = typer.Argument(None, metavar="[ID]", help="di base la più recente"),
    code: bool = typer.Option(False, "--code", help="usa il codice di recupero invece della passphrase"),
    yes: bool = typer.Option(False, "--yes", "-y", help="non chiedere conferma"),
) -> None:
    """Riporta i dati da Drive o dalla cartella, per esempio su un dispositivo nuovo."""
    ensure_consent()
    folder = data_dir()
    with cloud_errors():
        destination = sync._destination(folder, None, None)
        snapshot = sync._pick(sync.remote_snapshots(destination.list_files()), reference)
        typer.echo(f"Istantanea {snapshot.id} del {local_time(snapshot.created_at)} ({human_size(snapshot.size)}), da {destination.label}.")
        if database_path(folder).exists() and not yes:
            question = "Sostituire modelli e voci di questo dispositivo? Lo stato attuale sarà salvato prima"
            if not ask_yes_no(question):
                typer.echo("Va bene: non ho cambiato nulla.")
                raise typer.Exit()
        passphrase = recovery_code = None
        if code:
            recovery_code = typer.prompt("Codice di recupero", hide_input=True)
        elif sync.google_recovery_available(folder, destination) and ask_yes_no("Il recupero con Google è attivo. Usarlo, senza passphrase?"):
            pass
        else:
            passphrase = typer.prompt("Passphrase dei backup", hide_input=True)
        result = sync.recover_from_cloud(folder, passphrase, recovery_code, snapshot.id, destination)
    typer.echo(f"Dati riportati all'istantanea del {local_time(result.restored.created_at)} ({result.restored.id}).")
    if result.undo:
        typer.echo(f"Per annullare: zbone backup restore {result.undo.id}")
    typer.echo("Le chiavi dei backup ora sono anche su questo dispositivo: i prossimi backup useranno la stessa passphrase.")


@cloud_app.command("recovery")
def recovery_switch(state: str = typer.Argument(..., metavar="on|off", help="on attiva, off toglie il recupero con l'account Google")) -> None:
    """Attiva o toglie il recupero dei backup con l'account Google."""
    ensure_consent()
    folder = data_dir()
    if state not in ("on", "off"):
        fail("scrivi `on` oppure `off`")
    if state == "off":
        with cloud_errors():
            sync.disable_google_recovery(folder)
        typer.echo("Recupero con Google tolto: ora servono la passphrase o il codice di recupero.")
        return
    with cloud_errors():
        status = account.account_status(folder)
        if status.mode != "google":
            fail("il recupero con Google funziona solo con le copie su Google Drive: zbone cloud use google")
        if not keys.is_configured(folder):
            fail("prima attiva la cifratura dei backup: zbone backup setup")
    if status.google_recovery:
        typer.echo("Il recupero con Google è già attivo.")
        return
    offer_google_recovery(folder)


@cloud_app.command("forget")
def forget(yes: bool = typer.Option(False, "--yes", "-y", help="non chiedere conferma")) -> None:
    """Cancella tutte le copie dalla destinazione e torna a solo locale."""
    ensure_consent()
    folder = data_dir()
    with cloud_errors():
        destination = sync._destination(folder, None, None)
        question = f"Cancellare tutte le copie di ZibaldOne da {destination.label}? Diario e backup su questo dispositivo restano"
        if not yes and not ask_yes_no(question):
            typer.echo("Va bene: non ho cancellato nulla.")
            raise typer.Exit()
        removed = sync.forget_remote(folder, destination)
        account.choose_mode(folder, "local")
    typer.echo(f"File cancellati dalla destinazione: {removed}. Ora le copie restano solo su questo dispositivo.")
