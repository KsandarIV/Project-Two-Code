"""Helpers shared by every CLI command: consent, opening the store, answers, errors."""

from contextlib import contextmanager
from typing import Iterator

import typer

from zibaldone.core.privacy import NOTICE_VERSION, notice_text
from zibaldone.storage.database import Store, StoreError
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


@contextmanager
def open_store() -> Iterator[Store]:
    """Ask for consent if needed, open the database and turn known errors into messages."""
    ensure_consent()
    try:
        store = Store.open(data_dir())
    except StoreError as error:
        fail(str(error))
    try:
        yield store
    except (StoreError, ValueError) as error:
        fail(str(error))
    finally:
        store.close()
