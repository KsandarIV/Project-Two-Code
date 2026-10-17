"""`zbone backup …`: snapshots like commits, restore, retention and encryption.

Secrets are asked with hidden input and never taken from flags or
environment variables, so they do not end up in the shell history or in
the process list. Tests answer the prompts through CliRunner `input=`.
"""

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional

import typer
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from zibaldone.cli.common import ask_yes_no, ensure_consent, fail, run_auto_backup  # noqa: F401 (re-exported)
from zibaldone.core.crypto import RECOVERY_LOOKALIKES, CryptoError, RecoveryCodeError, recovery_code_last_group
from zibaldone.storage import backups, keys
from zibaldone.storage.backups import BackupError, BackupSettings, SnapshotInfo
from zibaldone.storage.keys import KeysError
from zibaldone.storage.paths import data_dir, human_size
from zibaldone.storage.settings import SettingsError

backup_app = typer.Typer(help="Mnemosyne · Storia e backup: istantanee dei tuoi dati, ripristino, durata e cifratura.", no_args_is_help=True)

KNOWN_ERRORS = (BackupError, KeysError, CryptoError, SettingsError)
CONFIRM_ATTEMPTS = 3

SETUP_INTRO = """Da ora ogni istantanea sarà cifrata su questo dispositivo (AES-256-GCM).
I backup automatici non ti chiedono nulla: la passphrase serve solo per verificarli o ripristinarli.
Riceverai anche un codice di recupero da scrivere su carta: serve se dimentichi la passphrase.
Senza passphrase e senza codice di recupero i backup non si possono aprire, da nessuno:
nemmeno da chi ha creato l'app.
Il database su questo dispositivo resta in chiaro: la cifratura riguarda le istantanee.
"""


@contextmanager
def backup_errors() -> Iterator[None]:
    """Turn known errors into a short message, never a stack trace."""
    try:
        yield
    except KNOWN_ERRORS as error:
        fail(str(error))
    except OSError as error:
        fail(f"operazione sui file non riuscita: {error}")


# * — printing —


def local_time(moment: datetime) -> str:
    return moment.astimezone().strftime("%d/%m/%Y %H:%M")


def describe(snapshot: SnapshotInfo) -> str:
    parts = [local_time(snapshot.created_at), snapshot.reason_label, human_size(snapshot.size)]
    parts.append("cifrata" if snapshot.encrypted else "in chiaro")
    if snapshot.entries is not None:
        parts.append(f"{snapshot.entries} voci, {snapshot.templates} modelli")
    if snapshot.note:
        parts.append(f"«{snapshot.note}»")
    text = " · ".join(parts)
    return f"{text} · PROBLEMA: {snapshot.problem}" if snapshot.problem else text


def print_status(folder: Path, settings: BackupSettings) -> None:
    retention = settings.retention
    automatic = f"sì, ogni {settings.auto_interval_hours:g} ore" if settings.auto else "no"
    typer.echo(f"Cartella:     {backups.backups_dir(folder)}")
    typer.echo(f"Automatico:   {automatic}")
    typer.echo(f"Durata:       {retention.daily} giornaliere, {retention.weekly} settimanali, {retention.monthly} mensili")
    if keys.is_configured(folder):
        typer.echo(f"Cifratura:    attiva (chiave {keys.format_key_id(keys.key_id(folder))})")
    else:
        typer.echo("Cifratura:    non attiva. Attivala con: zbone backup setup")


# * — secrets —


def ask_new_passphrase(label: str = "Nuova passphrase") -> str:
    first = typer.prompt(label, hide_input=True)
    keys.check_passphrase(first)
    if typer.prompt("Ripetila", hide_input=True) != first:
        fail("le due passphrase non coincidono: non ho cambiato nulla")
    return first


def unlock_for(folder: Path, snapshots: List[SnapshotInfo]) -> Optional[X25519PrivateKey]:
    """Ask for the passphrase only if some of `snapshots` are encrypted.

    Without keys.json (for example on a new device) the recovery code opens
    the key stored in the snapshot itself.
    """
    encrypted = [snapshot for snapshot in snapshots if snapshot.encrypted]
    if not encrypted:
        return None
    if keys.is_configured(folder):
        return keys.unlock_with_passphrase(folder, typer.prompt("Passphrase dei backup", hide_input=True))
    code = typer.prompt("Manca keys.json: scrivi il codice di recupero", hide_input=True)
    return backups.unlock_snapshot_with_recovery_code(folder, encrypted[0].id, code)


def require_encryption(folder: Path) -> None:
    if not keys.is_configured(folder):
        fail("la cifratura dei backup non è attiva: attivala con `zbone backup setup`")


# * — commands —


@backup_app.command("create")
def create_backup(note: str = typer.Option("", "--note", "-n", help="una nota breve, per esempio 'prima del trasloco'")) -> None:
    """Salva adesso un'istantanea completa dei tuoi dati."""
    ensure_consent()
    with backup_errors():
        snapshot = backups.create_snapshot(data_dir(), "manual", note)
    typer.echo(f"Istantanea creata: {snapshot.id}")
    typer.echo(f"  {describe(snapshot)}")
    if not snapshot.encrypted:
        typer.echo("  Non è cifrata: attiva la cifratura con `zbone backup setup`.")


@backup_app.command("list")
def list_backups(
    details: bool = typer.Option(False, "--details", help="chiede la passphrase e mostra note e contenuto delle istantanee cifrate"),
) -> None:
    """Elenca le istantanee, dalla più recente."""
    ensure_consent()
    folder = data_dir()
    with backup_errors():
        snapshots = backups.list_snapshots(folder)
        private_key = unlock_for(folder, snapshots) if details else None
        if private_key is not None:
            snapshots = backups.list_snapshots(folder, private_key)
        settings = backups.load_backup_settings(folder)
        if not snapshots:
            typer.echo("Nessuna istantanea. Creane una con: zbone backup create")
        for snapshot in snapshots:
            typer.echo(f"  {snapshot.id}  {describe(snapshot)}")
        typer.echo("")
        print_status(folder, settings)


@backup_app.command("restore")
def restore_backup(
    reference: str = typer.Argument(..., metavar="ID", help="identificativo dell'istantanea (bastano le prime cifre o il codice finale)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="non chiedere conferma"),
) -> None:
    """Riporta modelli e voci a un'istantanea, in modo annullabile.

    Prima salva lo stato attuale in un'istantanea "prima di un ripristino".
    """
    ensure_consent()
    folder = data_dir()
    with backup_errors():
        snapshot = backups.find_snapshot(folder, reference)
        typer.echo(f"Istantanea {snapshot.id}: {describe(snapshot)}")
        question = "Riportare modelli e voci a questa istantanea? Lo stato attuale sarà salvato prima"
        if not yes and not ask_yes_no(question):
            typer.echo("Va bene: non ho cambiato nulla.")
            raise typer.Exit()
        result = backups.restore_snapshot(folder, snapshot.id, unlock_for(folder, [snapshot]))
    typer.echo(f"Dati riportati all'istantanea del {local_time(result.restored.created_at)} ({result.restored.id}).")
    if result.undo:
        typer.echo(f"Per annullare: zbone backup restore {result.undo.id}")
    typer.echo("Impostazioni, consenso privacy e chiavi di questo dispositivo non sono cambiati.")


@backup_app.command("verify")
def verify_backups(
    reference: Optional[str] = typer.Argument(None, metavar="[ID]", help="di base la più recente"),
    all_snapshots: bool = typer.Option(False, "--all", "-a", help="controlla tutte le istantanee"),
) -> None:
    """Controlla che le istantanee siano integre e ripristinabili."""
    ensure_consent()
    folder = data_dir()
    with backup_errors():
        snapshots = backups.list_snapshots(folder)
        if not snapshots:
            fail("non ci sono istantanee da controllare")
        if all_snapshots:
            targets = snapshots
        elif reference:
            targets = [backups.find_snapshot(folder, reference)]
        else:
            targets = snapshots[:1]
        private_key = unlock_for(folder, targets)
        results = [backups.verify_snapshot(folder, snapshot.id, private_key) for snapshot in targets]
    broken = [result for result in results if not result.ok]
    for result in results:
        if result.ok:
            typer.echo(f"  integra  {result.snapshot.id}")
        else:
            typer.secho(f"  ROTTA    {result.snapshot.id}: {'; '.join(result.problems)}", fg=typer.colors.RED)
    if broken:
        fail(f"{len(broken)} istantanee su {len(results)} non sono integre")
    typer.echo("Tutto a posto." if len(results) == 1 else f"Tutte le {len(results)} istantanee sono integre.")


@backup_app.command("prune")
def prune_backups(dry_run: bool = typer.Option(False, "--dry-run", help="mostra cosa cancellerebbe, senza cancellare nulla")) -> None:
    """Cancella le istantanee scadute secondo la durata scelta."""
    ensure_consent()
    with backup_errors():
        result = backups.prune(data_dir(), dry_run=dry_run)
    failed = {snapshot_id for snapshot_id, _ in result.failed}
    removed = [snapshot for snapshot in result.remove if snapshot.id not in failed]
    if not result.remove:
        typer.echo(f"Niente da cancellare: le {len(result.keep)} istantanee sono tutte da tenere.")
        return
    typer.echo("Prova: cancellerei queste istantanee (nessuna è stata cancellata):" if dry_run else "Istantanee cancellate:")
    for snapshot in removed:
        typer.echo(f"  {snapshot.id}  {describe(snapshot)}")
    typer.echo(f"Restano {len(result.keep) + len(failed)} istantanee.")
    for snapshot_id, error in result.failed:
        typer.secho(f"  non cancellata {snapshot_id}: {error}", fg=typer.colors.RED, err=True)
    if failed:
        fail(f"{len(failed)} istantanee non si sono potute cancellare")


@backup_app.command("config")
def configure_backups(
    auto: Optional[bool] = typer.Option(None, "--auto/--no-auto", help="istantanea automatica dopo i comandi che salvano dati"),
    days: Optional[int] = typer.Option(None, "--days", min=0, max=backups.MAX_KEEP, help="quante istantanee giornaliere tenere"),
    weeks: Optional[int] = typer.Option(None, "--weeks", min=0, max=backups.MAX_KEEP, help="quante settimanali"),
    months: Optional[int] = typer.Option(None, "--months", min=0, max=backups.MAX_KEEP, help="quante mensili"),
    interval: Optional[float] = typer.Option(None, "--interval", min=1, max=backups.MAX_INTERVAL_HOURS, help="ore tra due istantanee automatiche"),
) -> None:
    """Mostra o cambia backup automatico e durata delle istantanee."""
    ensure_consent()
    folder = data_dir()
    with backup_errors():
        settings = backups.load_backup_settings(folder)
        if auto is not None:
            settings.auto = auto
        if interval is not None:
            settings.auto_interval_hours = interval
        for name, value in (("daily", days), ("weekly", weeks), ("monthly", months)):
            if value is not None:
                setattr(settings.retention, name, value)
        changed = any(value is not None for value in (auto, interval, days, weeks, months))
        if changed:
            backups.save_backup_settings(folder, settings)
        typer.echo("Impostazioni salvate." if changed else "Impostazioni dei backup:")
        print_status(folder, settings)
    if changed:
        typer.echo("La nuova durata vale dalla prossima pulizia: zbone backup prune --dry-run per vedere cosa cambierebbe.")


@backup_app.command("setup")
def setup_encryption() -> None:
    """Attiva la cifratura dei backup: passphrase e codice di recupero."""
    ensure_consent()
    folder = data_dir()
    if keys.is_configured(folder):
        fail("la cifratura è già attiva. Per cambiare passphrase: zbone backup passphrase")
    typer.echo(SETUP_INTRO)
    with backup_errors():
        new_keys = keys.create_keys(ask_new_passphrase("Scegli la passphrase dei backup"))
    typer.echo("\nCODICE DI RECUPERO (te lo mostro solo adesso):\n")
    typer.echo(f"    {new_keys.recovery_code}\n")
    typer.echo("Scrivilo su carta e conservalo lontano da questo dispositivo. Non salvarlo qui e non fotografarlo.")
    last_group = recovery_code_last_group(new_keys.recovery_code)
    for _ in range(CONFIRM_ATTEMPTS):
        answer = typer.prompt("Per conferma, scrivi l'ultimo gruppo del codice").strip().upper().translate(RECOVERY_LOOKALIKES)
        if answer == last_group:
            break
        typer.echo("Non corrisponde: ricontrolla quello che hai scritto.")
    else:
        fail("configurazione annullata: non ho salvato nulla. Riprova con `zbone backup setup`")
    with backup_errors():
        keys.save_new_keys(folder, new_keys)
        result = backups.encrypt_existing_snapshots(folder, new_keys.private_key)
    typer.echo(f"Cifratura attiva (chiave {keys.format_key_id(new_keys.key_id)}).")
    if result.encrypted:
        typer.echo(f"Istantanee che c'erano già, ora cifrate: {len(result.encrypted)}. Le copie in chiaro non ci sono più.")
    for snapshot_id, problem in result.failed:
        typer.secho(f"  restata in chiaro {snapshot_id}: {problem}", fg=typer.colors.YELLOW, err=True)
    if result.failed:
        typer.echo("Le istantanee rimaste in chiaro sono rovinate: controllale con `zbone backup verify --all`.")


@backup_app.command("passphrase")
def change_passphrase() -> None:
    """Cambia la passphrase dei backup (serve quella attuale)."""
    ensure_consent()
    folder = data_dir()
    require_encryption(folder)
    with backup_errors():
        current = typer.prompt("Passphrase attuale", hide_input=True)
        keys.unlock_with_passphrase(folder, current)
        keys.change_passphrase(folder, current, ask_new_passphrase())
    typer.echo("Passphrase cambiata. Il codice di recupero resta lo stesso.")


@backup_app.command("recover")
def recover_passphrase() -> None:
    """Imposta una nuova passphrase con il codice di recupero."""
    ensure_consent()
    folder = data_dir()
    require_encryption(folder)
    with backup_errors():
        for _ in range(CONFIRM_ATTEMPTS):
            code = typer.prompt("Codice di recupero", hide_input=True)
            try:
                keys.unlock_with_recovery_code(folder, code)
                break
            except RecoveryCodeError as error:
                typer.echo(f"  {error}")
        else:
            fail("codice di recupero non valido: non ho cambiato nulla")
        keys.reset_passphrase(folder, code, ask_new_passphrase())
    typer.echo("Nuova passphrase salvata. Il codice di recupero resta lo stesso: tienilo al sicuro.")
