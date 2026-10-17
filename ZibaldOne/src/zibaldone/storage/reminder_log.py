"""Files behind the reminders: `reminders-log.json` and the `reminders` key of settings.json."""

import json
import os
import tempfile
from datetime import date
from pathlib import Path

from zibaldone.core.reminders import (
    LOG_KEEP_DAYS,
    ReminderConfig,
    ReminderLog,
    config_from_settings,
    prune_log,
    settings_with_config,
)
from zibaldone.storage.settings import load_settings, save_settings

LOG_FILE = "reminders-log.json"


def log_path(folder: Path) -> Path:
    return folder / LOG_FILE


def load_log(folder: Path) -> ReminderLog:
    """Return the reminder log, or an empty one when nothing was sent yet."""
    path = log_path(folder)
    if not path.exists():
        return ReminderLog()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"non riesco a leggere il registro dei promemoria {path}: {error}. Puoi cancellarlo: verrà ricreato") from None
    try:
        return ReminderLog.from_dict(data)
    except ValueError as error:
        raise ValueError(f"{error} ({path}). Puoi cancellarlo: verrà ricreato") from None


def save_log(folder: Path, log: ReminderLog, today: date, keep_days: int = LOG_KEEP_DAYS) -> ReminderLog:
    """Keep only the last `keep_days` days and write atomically: temporary file first, then rename."""
    pruned = prune_log(log, today, keep_days)
    folder.mkdir(parents=True, exist_ok=True)
    text = json.dumps(pruned.to_dict(), indent=2, ensure_ascii=False)
    handle, temporary = tempfile.mkstemp(prefix=".reminders-log-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, log_path(folder))
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return pruned


def load_reminder_config(folder: Path) -> ReminderConfig:
    """The saved reminder settings, or the defaults (08:30, 13:30, 21:30, quiet 22:30–08:00)."""
    return config_from_settings(load_settings(folder))


def save_reminder_config(folder: Path, config: ReminderConfig) -> None:
    """Replace only the `reminders` key, keeping every other setting."""
    save_settings(folder, settings_with_config(load_settings(folder), config))
