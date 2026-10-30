"""The bridge between the interface and the rest of ZibaldOne, without Flet.

- where the data folder is (also inside an Android app);
- a fresh `Store` per operation (SQLite connections never cross threads);
- guarded access to parts that may be missing or still in progress
  (backups, account and cloud): `None` means "in arrivo";
- the in-app notifier for the Daimon while the app is open;
- a few interface preferences under the `ui` key of settings.json.
"""

import importlib
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Iterator, List, Optional, Tuple

from zibaldone.storage import backup_folder as bf
from zibaldone.storage.database import Store
from zibaldone.storage.paths import ENV_DATA_DIR, data_dir
from zibaldone.storage.settings import SettingsError, load_settings, save_settings
from zibaldone.ui import theme as T

UI_SETTINGS_KEY = "ui"
COMING_SOON = "in arrivo"
FLET_DATA_ENV = "FLET_APP_STORAGE_DATA"


def running_on_android() -> bool:
    try:
        from zibaldone.notify import running_on_android as check
    except Exception:  # pragma: no cover - notify is part of the app
        return False
    return check()


def resolve_data_folder() -> Path:
    """`ZIBALDONE_HOME` first; inside an Android app the private folder Flet gives; else the usual one."""
    if os.environ.get(ENV_DATA_DIR):
        return data_dir()
    flet_data = os.environ.get(FLET_DATA_ENV)
    if flet_data and running_on_android():
        return Path(flet_data) / "ZibaldOne"
    return data_dir()


@contextmanager
def open_store(folder: Path) -> Iterator[Store]:
    """Open, use and close: call it inside the thread that uses the store."""
    store = Store.open(folder)
    try:
        yield store
    finally:
        store.close()


# * — optional parts —


def optional_module(name: str) -> Optional[ModuleType]:
    """Import a module that may not exist yet; None on any import problem."""
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def backups_api() -> Optional[ModuleType]:
    module = optional_module("zibaldone.storage.backups")
    if module is None or not all(hasattr(module, name) for name in ("list_snapshots", "create_snapshot")):
        return None
    return module


def account_api() -> Optional[ModuleType]:
    module = optional_module("zibaldone.cloud.account")
    needed = ("account_status", "login_required", "skip_login", "sign_in_with_google", "sign_out", "choose_mode")
    if module is None or not all(hasattr(module, name) for name in needed):
        return None
    return module


def sync_api() -> Optional[ModuleType]:
    module = optional_module("zibaldone.cloud.sync")
    if module is None or not hasattr(module, "sync_now"):
        return None
    return module


def keys_api() -> Optional[ModuleType]:
    module = optional_module("zibaldone.storage.keys")
    needed = ("is_configured", "create_keys", "save_new_keys", "key_id", "format_key_id")
    if module is None or not all(hasattr(module, name) for name in needed):
        return None
    return module


def encryption_on(folder: Path) -> bool:
    """True once the snapshots are encrypted (keys.json exists)."""
    keys = keys_api()
    if keys is None:
        return False
    try:
        return bool(keys.is_configured(folder))
    except Exception:
        return False


def login_required(folder: Path) -> bool:
    """True only when the account part exists and asks for a sign-in."""
    account = account_api()
    if account is None:
        return False
    try:
        return bool(account.login_required(folder))
    except Exception:
        return False


def account_status(folder: Path) -> Tuple[Any, str]:
    """(status or None, error message). (None, '') when the account part is not there."""
    account = account_api()
    if account is None:
        return None, ""
    try:
        return account.account_status(folder), ""
    except Exception as error:
        return None, str(error)


def skip_login(folder: Path) -> None:
    """«Continua senza account»: solo locale, and the sign-in is not asked again."""
    account = account_api()
    if account is not None:
        account.skip_login(folder)


def destination_choice_pending(folder: Path) -> bool:
    """Right after the first sign-in with Drive allowed: ask where the copies go (once)."""
    account = account_api()
    if account is None:
        return False
    try:
        status = account.account_status(folder)
        if not (status.signed_in and getattr(status, "drive_allowed", False)):
            return False
        cloud = load_settings(folder).get("cloud")
    except Exception:
        return False
    return not (isinstance(cloud, dict) and "mode" in cloud)


# * — Mnemosyne in the background —


def pre_migration_backup(folder: Path) -> str:
    """Before the first Store.open of a session: keep a copy if the database is about to be migrated.
    Returns a warning to show, or ''."""
    backups = backups_api()
    if backups is None or not hasattr(backups, "maybe_pre_migration_snapshot"):
        return ""
    try:
        backups.maybe_pre_migration_snapshot(folder)
    except Exception as error:
        return f"copia prima dell'aggiornamento non riuscita: {error}"
    return ""


def auto_backup(folder: Path, now: Optional[datetime] = None) -> str:
    """The daily snapshot after data changed, then the copy to the cloud destination.

    Silent when there is nothing to do; returns a warning to show, or ''.
    Blocking: call it in a thread."""
    backups = backups_api()
    if backups is None or not hasattr(backups, "maybe_auto_snapshot"):
        return ""
    try:
        snapshot = backups.maybe_auto_snapshot(folder, now=now)
    except Exception as error:
        return f"backup automatico non riuscito: {error}"
    if snapshot is None:
        return ""
    return export_to_files_folder(folder) or sync_quietly(folder)


def sync_quietly(folder: Path) -> str:
    """Copy new encrypted snapshots to the chosen destination, if there is one.
    Never raises; returns a warning to show, or ''. Blocking: call it in a thread."""
    account, sync = account_api(), sync_api()
    if account is None or sync is None or not hasattr(sync, "maybe_sync"):
        return ""
    try:
        status = account.account_status(folder)
        if status.mode == "local":
            return ""
        if sync.maybe_sync(folder) is None:
            error = account.account_status(folder).last_sync_error
            if error:
                return f"copia su {status.mode_label} non riuscita: {error}. Riproverò al prossimo backup"
    except Exception as error:
        return f"copia del backup non riuscita: {error}"
    return ""


# * — updates (0.1.1) —


def check_updates(folder: Path) -> Any:
    """At start: the newer release, if any (at most one question to GitHub a day). Never raises."""
    from zibaldone.cloud import updates

    return updates.maybe_check(folder)


def check_updates_now(folder: Path) -> Any:
    """From the Info page: ask GitHub now. Raises CloudError with an Italian message."""
    from zibaldone.cloud import updates

    return updates.check_now(folder)


def update_check_enabled(folder: Path) -> bool:
    from zibaldone.cloud import updates

    return updates.auto_check_enabled(folder)


def set_update_check(folder: Path, enabled: bool) -> None:
    from zibaldone.cloud import updates

    updates.set_auto_check(folder, enabled)


# * — interface preferences —


def ui_settings(folder: Path) -> Dict[str, Any]:
    try:
        value = load_settings(folder).get(UI_SETTINGS_KEY, {})
    except SettingsError:
        return {}
    return dict(value) if isinstance(value, dict) else {}


def save_ui_settings(folder: Path, **changes: Any) -> None:
    settings = load_settings(folder)
    current = settings.get(UI_SETTINGS_KEY)
    section = dict(current) if isinstance(current, dict) else {}
    section.update(changes)
    settings[UI_SETTINGS_KEY] = section
    save_settings(folder, settings)


def theme_choice(folder: Path) -> Tuple[str, str]:
    """(accent, background) chosen in Kosmesis; the defaults when nothing was chosen."""
    saved = ui_settings(folder)
    return str(saved.get("accent", T.DEFAULT_ACCENT)), str(saved.get("background", T.DEFAULT_BG))


def set_theme_choice(folder: Path, accent: str, background: str) -> None:
    save_ui_settings(folder, accent=accent, background=background)


def shortcuts(folder: Path) -> List[str]:
    """The templates pinned on Oggi, in the order they were pinned."""
    value = ui_settings(folder).get("shortcuts", [])
    return [slug for slug in value if isinstance(slug, str)] if isinstance(value, list) else []


def toggle_shortcut(folder: Path, slug: str) -> bool:
    """Pin the template on Oggi, or unpin it; True when it is pinned now."""
    current = shortcuts(folder)
    pinned = slug not in current
    save_ui_settings(folder, shortcuts=[*current, slug] if pinned else [item for item in current if item != slug])
    return pinned


def backup_files_folder(folder: Path) -> str:
    """Where the backup files (.zbbackup) are written, chosen by the user; '' when none."""
    return str(ui_settings(folder).get("backup_files_folder", "") or "")


def backup_files_pending(folder: Path) -> bool:
    """The first start asks once where the backup files go (or «continue without»)."""
    return "backup_files_folder" not in ui_settings(folder)


def backup_mode(folder: Path) -> str:
    """Who manages the backup files: the app, the user, or both. A folder chosen before 0.3.3 stays «misto»: its files are not touched."""
    value = ui_settings(folder).get("backup_mode")
    if value in bf.MODES:
        return str(value)
    return bf.MODE_MIXED if backup_files_folder(folder) else bf.MODE_APP


def without_backup(folder: Path) -> bool:
    """The user went on without a backup folder: the strip «stai usando l'app senza backup» shows, unless switched off."""
    return not backup_files_folder(folder) and not ui_settings(folder).get("no_backup_notice_off", False)


def folder_history(folder: Path) -> List[str]:
    """The folders used before, only those that still exist."""
    value = ui_settings(folder).get("backup_folder_history", [])
    return bf.existing(value if isinstance(value, list) else [])


def keep_history(folder: Path) -> bool:
    """Rotated backup files go to «Storico» instead of being deleted; off unless the user turns it on."""
    return bool(ui_settings(folder).get("backup_keep_history", False))


def set_backup_folder(folder: Path, path: str, move_old: bool = False) -> List[Path]:
    """Use `path` from now on; with `move_old` the files of the app's own scheme in the old folder come along. The old path is remembered."""
    old = backup_files_folder(folder)
    moved: List[Path] = []
    if path:
        Path(path).mkdir(parents=True, exist_ok=True)
        if move_old and old and Path(old) != Path(path) and Path(old).is_dir():
            moved = bf.move_scheme(Path(old), Path(path))
    history = [item for item in ui_settings(folder).get("backup_folder_history", []) if isinstance(item, str)]
    for used in (old, path):
        if used and used not in history:
            history.append(used)
    save_ui_settings(folder, backup_files_folder=path, backup_folder_history=history, no_backup_notice_off=False)
    return moved


def set_backup_mode(folder: Path, mode: str) -> List[Path]:
    """Change who manages the backups, without losing any. «Gestisco io» turns the automatic copies off; «Gestisce l'app» sets the user's files aside in «Gestione manuale». Returns what was moved."""
    if mode not in bf.MODES:
        raise ValueError(f"modalità sconosciuta: {mode}")
    api = backups_api()
    if api is not None:
        settings = api.load_backup_settings(folder)
        settings.auto = mode != bf.MODE_USER
        api.save_backup_settings(folder, settings)
    target = backup_files_folder(folder)
    moved = bf.take_over(Path(target)) if mode == bf.MODE_APP and target and Path(target).is_dir() else []
    save_ui_settings(folder, backup_mode=mode)
    return moved


def suggested_folder() -> Path:
    """The folder proposed to the user: `ZibaldOne/Data` in the main storage of the phone, `Documenti/ZibaldOne/Data` elsewhere."""
    if running_on_android():
        return Path("/storage/emulated/0") / bf.SUGGESTED
    home = Path.home()
    documents = next((home / name for name in ("Documenti", "Documents") if (home / name).is_dir()), home / "Documents")
    return documents / bf.SUGGESTED


def create_suggested_folder(folder: Path) -> Path:
    """Make the proposed folder and use it. Raises OSError when it cannot be made (on Android: the permission is missing)."""
    path = suggested_folder()
    path.mkdir(parents=True, exist_ok=True)
    set_backup_folder(folder, str(path))
    return path


def keep_imported_copy(folder: Path, source: Path) -> None:
    """A backup file brought in from outside is copied to «importati» of the backup folder (not when the user manages it alone). Never raises."""
    target = backup_files_folder(folder)
    if not target or backup_mode(folder) == bf.MODE_USER:
        return
    try:
        bf.keep_imported_copy(Path(target), source)
    except OSError:
        pass


def export_to_files_folder(folder: Path) -> str:
    """Write the new backup files in the chosen folder, by the chosen mode, and rotate; returns a warning or ''. Blocking."""
    target = backup_files_folder(folder)
    if not target or backups_api() is None:
        return ""
    try:
        bf.export_snapshots(folder, Path(target), backup_mode(folder))
        if backup_mode(folder) != bf.MODE_USER:
            bf.rotate(Path(target), keep_history(folder))
    except Exception as error:
        return f"file di backup non salvato in {target}: {error}"
    return ""


def diario_suggestion_pending(folder: Path, installed_slugs: List[str]) -> bool:
    """Suggest the diary pack once, after consent, while its moments are missing."""
    if all(slug in installed_slugs for slug in ("mattina", "meta_giornata", "sera")):
        return False
    return not ui_settings(folder).get("diario_suggested", False)


# * — the Daimon while the app is open —


@dataclass(frozen=True)
class InAppMessage:
    title: str
    body: str


class InAppNotifier:
    """A Notifier (`name`, `send`) that queues messages for an in-app banner."""

    name = "app"

    def __init__(self) -> None:
        self.pending: List[InAppMessage] = []

    def send(self, title: str, body: str) -> bool:
        self.pending.append(InAppMessage(title, body))
        return True

    def take(self) -> List[InAppMessage]:
        messages, self.pending = self.pending, []
        return messages


def in_app_reminder(folder: Path, now: datetime) -> Any:
    """The gentle banner for Oggi, or None (also when anything goes wrong)."""
    try:
        from zibaldone.notify.service import in_app_reminder as banner

        with open_store(folder) as store:
            return banner(store, folder, now)
    except Exception:
        return None


def fire_reminders(folder: Path, now: datetime, notifier: InAppNotifier) -> Any:
    """Send the reminders due now through `notifier`; None when it could not run."""
    try:
        from zibaldone.notify.service import fire_due_reminders

        with open_store(folder) as store:
            return fire_due_reminders(store, folder, now, notifier)
    except Exception:
        return None


def streak_days(store: Store, today: Any) -> int:
    try:
        from zibaldone.core.reminders import streak
        from zibaldone.notify.service import writing_history

        return streak(writing_history(store).days, today)
    except Exception:
        return 0


def reminder_config(folder: Path) -> Tuple[Any, str]:
    """(ReminderConfig or None, error message)."""
    try:
        from zibaldone.storage.reminder_log import load_reminder_config

        return load_reminder_config(folder), ""
    except Exception as error:
        return None, str(error)


def reminder_overview(folder: Path, now: datetime) -> Tuple[Any, str]:
    try:
        from zibaldone.notify.service import reminder_overview as overview

        with open_store(folder) as store:
            return overview(store, folder, now), ""
    except Exception as error:
        return None, str(error)
