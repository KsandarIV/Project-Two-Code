"""Le Nuvole and Mnemosyne in the interface: wording, choices and the flows,
run headless against a folder destination (no network, no Google)."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pytest

from zibaldone.core.crypto import ScryptParams
from zibaldone.core.privacy import NOTICE_VERSION
from zibaldone.storage import backups, keys
from zibaldone.storage.database import Store
from zibaldone.storage.settings import load_settings, record_consent, save_settings
from zibaldone.ui import cloud_model as cm
from zibaldone.ui import services

PASSPHRASE = "quattro parole a caso"


@pytest.fixture(autouse=True)
def fast_scrypt(monkeypatch):
    monkeypatch.setattr(keys, "DEFAULT_SCRYPT_PARAMS", ScryptParams(n=2**10))


@pytest.fixture
def folder(isolated_data_dir: Path) -> Path:
    isolated_data_dir.mkdir(parents=True, exist_ok=True)
    record_consent(isolated_data_dir, True, NOTICE_VERSION)
    with Store.open(isolated_data_dir) as store:
        store.save_template(_diary())
        store.add_entry("pensiero", {"testo": "Bisogna immaginare Sisifo felice."})
    return isolated_data_dir


def _diary():
    from zibaldone.core.templates import BlockSpec, Template

    return Template(slug="pensiero", name="Pensiero", blocks=[BlockSpec(key="testo", type="longtext", label="Testo")]).validate()


@dataclass
class Status:
    signed_in: bool = False
    email: Optional[str] = None
    name: Optional[str] = None
    mode: str = "local"
    folder_path: Optional[str] = None
    google_configured: bool = False
    last_sync: Optional[str] = None
    last_sync_error: Optional[str] = None
    drive_allowed: bool = False
    google_recovery: bool = False

    @property
    def mode_label(self) -> str:
        return {"local": "solo locale", "google": "locale + Google Drive", "folder": "locale + una cartella"}[self.mode]


def sign_in_by_hand(folder: Path, drive: bool = True) -> None:
    settings = load_settings(folder)
    settings["account"] = {"provider": "google", "email": "alex@example.com", "name": "Alex", "signed_in_at": "2026-10-17T10:00:00+00:00", "drive": drive}
    save_settings(folder, settings)


# * — wording and choices —


def test_terminal_commands_become_places_in_the_app() -> None:
    text = "prima attiva la cifratura con `zbone backup setup`: nessun dato esce dal dispositivo in chiaro"
    assert cm.app_hint(text) == "prima attiva la cifratura con «Attiva la cifratura» in Impostazioni · Mnemosyne: nessun dato esce dal dispositivo in chiaro"
    assert cm.app_hint("Puoi rileggerla quando vuoi con `zbone privacy`.") == "Puoi rileggerla quando vuoi in Impostazioni · Parresia."
    assert "`" not in cm.app_hint("scegli una destinazione con `zbone cloud use google` o `zbone cloud use folder PERCORSO`")
    assert cm.error_text(ValueError("la cartella non esiste")) == "La cartella non esiste"
    assert cm.error_text(ValueError("")).startswith("qualcosa non ha funzionato")


def test_privacy_notice_has_no_terminal_command_for_parresia(folder: Path) -> None:
    from zibaldone.core.privacy import notice_text

    assert "`zbone privacy`" not in cm.app_hint(notice_text(folder))


def test_google_mode_needs_sign_in_and_drive() -> None:
    def google(status):
        return next(choice for choice in cm.mode_choices(status) if choice.mode == "google")

    assert not google(Status()).enabled and "entra con Google" in google(Status()).hint
    assert not google(Status(signed_in=True, email="a@b.it")).enabled
    allowed = google(Status(signed_in=True, email="a@b.it", drive_allowed=True))
    assert allowed.enabled and "a@b.it" in allowed.hint
    assert [choice.mode for choice in cm.mode_choices(Status())] == ["local", "google", "folder"]


def test_cloud_lines_describe_account_copies_and_problems() -> None:
    lines = dict(cm.cloud_lines(Status(), False))
    assert lines["Account"].startswith("nessuno")
    assert "Ultima copia" not in lines
    status = Status(signed_in=True, email="a@b.it", name="Alex", mode="folder", folder_path="E:/backup", last_sync_error="prima attiva la cifratura con `zbone backup setup`")
    lines = dict(cm.cloud_lines(status, False))
    assert lines["Account"] == "Alex <a@b.it> (Google)"
    assert lines["Cartella"] == "E:/backup"
    assert lines["Ultima copia"] == "mai"
    assert "Mnemosyne" in lines["Problema"]
    assert lines["Cifratura dei backup"] == "non attiva"
    assert cm.needs_encryption_note(status, False)
    assert not cm.needs_encryption_note(status, True)
    assert cm.destination_label(status) == "E:/backup"
    assert cm.destination_label(Status(mode="google", email="a@b.it")) == "Google Drive (a@b.it)"
    assert dict(cm.cloud_lines(Status(mode="google", signed_in=True, google_recovery=True), True))["Recupero con Google"] == "attivo"


def test_notes_after_signing_in() -> None:
    before = Status(signed_in=True, email="vecchio@b.it", mode="google")
    notes = cm.sign_in_notes(before, Status(signed_in=True, email="nuovo@b.it"))
    assert notes[0] == "Sei entrato come nuovo@b.it."
    assert any("account diverso" in note for note in notes)
    assert any("permesso per Drive" in note for note in notes)
    assert cm.sign_in_notes(None, Status(signed_in=True, email="a@b.it", drive_allowed=True)) == ["Sei entrato come a@b.it."]


def test_new_passphrase_and_recovery_code_checks() -> None:
    assert "almeno 10" in cm.check_new_passphrase("corta", "corta")
    assert cm.check_new_passphrase(PASSPHRASE, PASSPHRASE + "!") == "Le due passphrase non coincidono."
    assert cm.check_new_passphrase(PASSPHRASE, PASSPHRASE) == ""
    code = "9678-2FKR-NANA-4PM3-DBFZ-CFGM-05CX"
    assert cm.recovery_answer_ok(code, "05cx")
    assert cm.recovery_answer_ok(code, " o5cx ")  # O and 0 are the same
    assert not cm.recovery_answer_ok(code, "CFGM")
    assert not cm.recovery_answer_ok(code, "")


def test_remote_choices_and_recovery_methods() -> None:
    @dataclass
    class Snap:
        id: str
        created_at: datetime
        size: int

    choices = cm.remote_choices([Snap("s1", datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc), 1536)])
    assert choices[0].id == "s1" and choices[0].label.endswith("· 1.5 KB") and "ott 2026" in choices[0].label
    assert [key for key, _ in cm.recovery_methods(False)] == ["passphrase", "code"]
    assert cm.recovery_methods(True)[0][0] == "google"


# * — services —


def test_destination_choice_only_after_signing_in_with_drive(folder: Path) -> None:
    assert not services.destination_choice_pending(folder)
    sign_in_by_hand(folder, drive=False)
    assert not services.destination_choice_pending(folder)
    sign_in_by_hand(folder, drive=True)
    assert services.destination_choice_pending(folder)
    from zibaldone.cloud import account

    account.choose_mode(folder, "local")
    assert not services.destination_choice_pending(folder)


def test_daily_backup_after_a_save_then_quiet(folder: Path) -> None:
    assert services.auto_backup(folder) == ""
    assert len(backups.list_snapshots(folder)) == 1
    assert services.auto_backup(folder) == ""
    assert len(backups.list_snapshots(folder)) == 1
    assert services.pre_migration_backup(folder) == ""
    assert services.sync_quietly(folder) == ""  # local mode: nothing to copy


def test_encryption_flag(folder: Path) -> None:
    assert not services.encryption_on(folder)
    keys.setup_keys(folder, PASSPHRASE)
    assert services.encryption_on(folder)


# * — the flows, headless —


@pytest.fixture
def needs_flet():
    pytest.importorskip("flet")


def test_folder_destination_sync_recover_and_forget(needs_flet, folder: Path, tmp_path: Path) -> None:
    from zibaldone.cloud import account
    from zibaldone.ui.context import AppContext
    from zibaldone.ui.views import cloud as C

    outside = tmp_path / "chiavetta"
    outside.mkdir()
    ctx = AppContext(folder)

    screen = C.CloudScreen(ctx)
    screen.build()
    screen.mode, screen.path_input.value = "folder", str(outside)
    screen.apply_mode()
    assert account.account_status(folder).mode == "folder"
    assert any("cifratura" in toast for toast in ctx.toasts)  # nothing leaves in clear

    keys.setup_keys(folder, PASSPHRASE)
    backups.create_snapshot(folder, "manual")
    ctx.toasts.clear()
    screen = C.CloudScreen(ctx)
    screen.build()
    screen.sync()
    assert ctx.toasts[-1].startswith("Sincronizzato con")
    assert any(path.suffix == ".zbsnap" for path in outside.rglob("*"))

    from zibaldone.cloud import sync

    dialog = C.RecoverDialog(ctx, cm.remote_choices(sync.list_remote(folder)), google=False)
    dialog.confirm()
    assert dialog.error.value.startswith("Scrivi")
    dialog.secret.value = "non è questa la passphrase"
    dialog.confirm()
    assert dialog.error.visible and dialog.error.value
    dialog.secret.value = PASSPHRASE
    dialog.confirm()
    assert ctx.toasts[-1].startswith("Dati riportati")

    screen = C.CloudScreen(ctx)
    screen.build()
    screen.forget()
    assert account.account_status(folder).mode == "local"
    assert not any(path.suffix == ".zbsnap" for path in outside.rglob("*"))


def test_a_folder_inside_the_data_folder_is_refused(needs_flet, folder: Path) -> None:
    from zibaldone.ui.context import AppContext
    from zibaldone.ui.views import cloud as C

    inside = folder / "dentro"
    inside.mkdir()
    screen = C.CloudScreen(AppContext(folder))
    screen.build()
    screen.mode, screen.path_input.value = "folder", str(inside)
    screen.apply_mode()
    assert screen.error.visible and "fuori dalla cartella dati" in screen.error.value


def test_encryption_save_seals_old_snapshots(needs_flet, folder: Path) -> None:
    from zibaldone.ui.context import AppContext
    from zibaldone.ui.views import encryption

    backups.create_snapshot(folder, "manual")
    ctx = AppContext(folder)
    new_keys = keys.create_keys(PASSPHRASE)
    done = []
    encryption.save(ctx, keys, new_keys, PASSPHRASE, lambda: done.append(True))
    assert services.encryption_on(folder)
    assert all(snapshot.encrypted for snapshot in backups.list_snapshots(folder))
    assert ctx.toasts[0].startswith("Cifratura attiva") and "ora cifrate: 1" in ctx.toasts[0]
    assert done == [True]
