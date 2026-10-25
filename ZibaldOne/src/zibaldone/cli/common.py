"""Helpers shared by every CLI command: consent, account, opening the store, answers, errors."""

import sqlite3
from contextlib import contextmanager
from typing import Iterator

import typer

from zibaldone.cloud import account, sync
from zibaldone.cloud.http import CloudError
from zibaldone.core.privacy import NOTICE_VERSION, notice_text
from zibaldone.storage import backups
from zibaldone.storage.backups import BackupError
from zibaldone.storage.database import Store, StoreError
from zibaldone.storage.keys import KeysError
from zibaldone.storage.paths import data_dir
from zibaldone.storage.settings import SettingsError, has_consent, record_consent

YES = {"s", "si", "sì", "y", "yes"}
NO = {"n", "no"}


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
    try:
        if has_consent(folder, NOTICE_VERSION):
            return
    except SettingsError as error:
        fail(str(error))
    typer.echo(notice_text(folder) + "\n")
    if not ask_yes_no("Continuare?"):
        typer.echo("Va bene: ZibaldOne non ha salvato nulla. Te lo richiederà al prossimo avvio.")
        raise typer.Exit(code=1)
    record_consent(folder, accepted=True, notice_version=NOTICE_VERSION)
    typer.echo(f"Consenso salvato. La tua cartella dati è {folder}")
    typer.echo("Per iniziare con dei modelli pronti: zbone pack install diario\n")


def fail(message: str, code: int = 1) -> None:
    typer.secho(f"Errore: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=code)


def warn(message: str) -> None:
    typer.secho(f"Attenzione: {message}", fg=typer.colors.YELLOW, err=True)


LOGIN_INTRO = """Puoi entrare con il tuo account Google, ma non è obbligatorio.
Serve a sapere chi sei su questo dispositivo e, se vuoi, a tenere copie cifrate su Google Drive:
ZibaldOne riceve la tua email e il tuo nome, e li tiene qui. Senza account usi tutto in locale.
"""


def ensure_account() -> None:
    """At first start, offer to sign in with Google; «no» means solo locale and the question is not asked again.

    Only when this copy of the app has a Google client configured: during
    development it works locally without an account. Backups, export and
    privacy commands never ask for it, so getting your data back never
    depends on Google (ADR-0007).
    """
    folder = data_dir()
    try:
        required = account.login_required(folder)
    except CloudError as error:
        fail(str(error))
    if not required:
        return
    typer.echo(LOGIN_INTRO)
    if not ask_yes_no("Aprire adesso il browser per entrare con Google?"):
        account.skip_login(folder)
        typer.echo("Va bene: continui solo in locale. Quando vuoi, entra con `zbone account login`.\n")
        return
    from zibaldone.cli.account_cmd import run_login  # account_cmd imports this module

    run_login(open_browser=True)
    typer.echo("")


def sync_quietly() -> None:
    """Copy new encrypted snapshots to the chosen destination, if there is one.

    A failure is a warning only: the snapshot is safe on this device and the
    next automatic backup (or `zbone cloud sync`) tries again.
    """
    folder = data_dir()
    try:
        status = account.account_status(folder)
    except CloudError:
        return
    if status.mode == "local":
        return
    if sync.maybe_sync(folder) is None:
        error = account.account_status(folder).last_sync_error
        if error:
            warn(f"copia su {status.mode_label} non riuscita: {error}. Riproverò al prossimo backup (o `zbone cloud sync`)")


def run_auto_backup() -> None:
    """The daily automatic snapshot, after a command saved data.

    Silent when there is nothing to do; a failure becomes a warning and never
    fails the command, because the user's data is already saved. A new
    snapshot is then copied to the cloud destination, if one is chosen.
    """
    try:
        snapshot = backups.maybe_auto_snapshot(data_dir())
    except (BackupError, SettingsError, OSError, sqlite3.Error) as error:
        warn(f"backup automatico non riuscito: {error}")
        return
    if snapshot is not None:
        try:
            sync_quietly()
        except (CloudError, KeysError, SettingsError, OSError) as error:
            warn(f"copia del backup non riuscita: {error}")


@contextmanager
def open_store(require_account: bool = True) -> Iterator[Store]:
    """Ask for consent (and the account) if needed, open the database and turn known errors into messages.

    Before an update migrates the database a copy is saved; after a command
    that changed something the daily snapshot runs (Mnemosyne, ADR-0006).
    `require_account=False` is for commands that give the user their data
    back, like export.
    """
    ensure_consent()
    if require_account:
        ensure_account()
    folder = data_dir()
    try:
        backups.maybe_pre_migration_snapshot(folder)
    except BackupError as error:
        warn(f"copia prima dell'aggiornamento non riuscita: {error}")
    try:
        store = Store.open(folder)
    except StoreError as error:
        fail(str(error))
    changes_at_start = store.connection.total_changes
    try:
        yield store
        changed = store.connection.total_changes > changes_at_start
    except (StoreError, ValueError) as error:
        fail(str(error))
    finally:
        store.close()
    if changed:
        run_auto_backup()
