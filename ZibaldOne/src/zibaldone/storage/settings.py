"""User settings saved as `settings.json` inside the data folder."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

SETTINGS_FILE = "settings.json"
SCHEMA_VERSION = 1


class SettingsError(Exception):
    """The settings file exists but cannot be read."""


def settings_path(folder: Path) -> Path:
    return folder / SETTINGS_FILE


def load_settings(folder: Path) -> Dict[str, Any]:
    """Return the saved settings, or an empty dict when there are none yet."""
    path = settings_path(folder)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SettingsError(f"Cannot read {path}: {error}") from error


def save_settings(folder: Path, settings: Dict[str, Any]) -> None:
    """Write settings atomically: temporary file first, then rename."""
    folder.mkdir(parents=True, exist_ok=True)
    data = {**settings, "schema_version": SCHEMA_VERSION}
    path = settings_path(folder)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def consent_status(folder: Path) -> Dict[str, Any]:
    """Return the recorded privacy decision, or an empty dict."""
    return load_settings(folder).get("privacy", {})


def has_consent(folder: Path, notice_version: int) -> bool:
    """True when the user accepted the current version of the notice."""
    status = consent_status(folder)
    return status.get("accepted") is True and status.get("notice_version") == notice_version


def record_consent(folder: Path, accepted: bool, notice_version: int) -> None:
    """Save the user's decision with the notice version and the time."""
    settings = load_settings(folder)
    settings["privacy"] = {
        "accepted": accepted,
        "notice_version": notice_version,
        "decided_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    save_settings(folder, settings)
