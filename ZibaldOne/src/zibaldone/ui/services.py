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

from zibaldone.storage.database import Store
from zibaldone.storage.paths import ENV_DATA_DIR, data_dir
from zibaldone.storage.settings import SettingsError, load_settings, save_settings

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
    return sync_quietly(folder)


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
