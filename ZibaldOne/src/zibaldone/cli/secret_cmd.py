"""`zbone segreti …`: the secret blocks (0.2.3), the PIN and opening an entry with secrets."""

from datetime import datetime
from pathlib import Path
from typing import List

import typer

from zibaldone.cli.common import fail, open_store
from zibaldone.cli.entry_cmd import print_entry
from zibaldone.core import secrets
from zibaldone.storage import keys
from zibaldone.storage.paths import data_dir

secret_app = typer.Typer(help="Arcana: i blocchi segreti, cifrati con la tua chiave (PIN, aprire una voce).", no_args_is_help=False)


@secret_app.callback(invoke_without_command=True)
def status(ctx: typer.Context) -> None:
    """Com'è messa la cifratura dei segreti."""
    if ctx.invoked_subcommand is not None:
        return
    folder = data_dir()
    if not keys.is_configured(folder):
        typer.echo("I segreti si cifrano con la chiave dei backup, che non è ancora attiva: zbone backup setup")
        return
    with open_store() as store:
        templates = {template.slug: template for template in store.list_templates()}
        count = sum(1 for entry in store.list_entries() if entry.template in templates and any(spec.key in entry.values for spec in secrets.secret_specs(templates[entry.template])))
    ready = secrets.PROTECTED in keys.secret_public_keys(folder)
    typer.echo(f"Voci con segreti: {count}")
    typer.echo("Segreti protetti: " + ("si scrivono senza chiedere nulla" if ready else "aprili una volta con la passphrase (zbone segreti apri)"))
    typer.echo("PIN: " + ("scelto, apre i segreti protetti" if keys.has_pin(folder) else "non scelto (zbone segreti pin)"))
    typer.echo("I segreti di livello massimo si aprono solo con la passphrase o il codice di recupero.")


@secret_app.command("pin")
def pin(remove: bool = typer.Option(False, "--togli", help="togli il PIN: poi serve la passphrase")) -> None:
    """Scegli il PIN che apre i segreti protetti (mai quelli di livello massimo)."""
    folder = data_dir()
    try:
        if remove:
            typer.echo("PIN tolto." if keys.remove_pin(folder) else "Non c'era un PIN.")
            return
        main = keys.unlock_with_passphrase(folder, typer.prompt("Passphrase dei backup", hide_input=True))
        first = typer.prompt(f"Nuovo PIN ({keys.PIN_MIN}-{keys.PIN_MAX} cifre)", hide_input=True)
        keys.check_pin(first)
        if typer.prompt("Ripetilo", hide_input=True) != first:
            fail("i due PIN non sono uguali")
        keys.set_pin(folder, main, first)
    except keys.KeysError as error:
        fail(str(error))
    typer.echo(f"PIN scelto. Apre i segreti protetti; dopo {keys.PIN_ATTEMPTS} errori di fila si toglie da solo.")


def unlock(folder: Path, values: List[str]) -> secrets.Vault:
    """Ask the PIN when it is enough for these secrets, the passphrase otherwise."""
    vault = secrets.Vault()
    only_protected = bool(values) and all(secrets.value_level(value) == secrets.PROTECTED for value in values)
    try:
        if only_protected and keys.has_pin(folder):
            vault.unlock([keys.unlock_with_pin(folder, typer.prompt("PIN", hide_input=True))], datetime.now())
        else:
            vault.unlock(keys.unlock_secrets_with_passphrase(folder, typer.prompt("Passphrase dei backup", hide_input=True)), datetime.now())
    except (keys.KeysError, secrets.SecretsError) as error:
        fail(str(error))
    return vault


@secret_app.command("apri")
def open_entry(reference: str = typer.Argument("", metavar="[ID]")) -> None:
    """Mostra una voce con i suoi segreti in chiaro (solo sullo schermo); senza ID prepara i segreti protetti."""
    folder = data_dir()
    if not reference:
        if not keys.is_configured(folder):
            fail("i segreti si cifrano con la chiave dei backup: attivala con zbone backup setup")
        unlock(folder, [])
        typer.echo("Segreti pronti: quelli protetti ora si scrivono senza chiedere nulla.")
        return
    with open_store() as store:
        entry = store.get_entry(reference)
        template = store.get_template(entry.template)
    values = [entry.values[spec.key] for spec in secrets.secret_specs(template) if spec.key in entry.values]
    if not values:
        print_entry(entry, template)
        return
    if not keys.is_configured(folder):
        fail("manca keys.json: senza la chiave i segreti non si aprono")
    vault = unlock(folder, values)
    try:
        print_entry(entry, template, reveal=lambda value: vault.reveal(value, datetime.now()))
    except secrets.SecretsError as error:
        fail(str(error))
