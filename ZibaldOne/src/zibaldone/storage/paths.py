"""Where ZibaldOne keeps the user's data on each platform."""

import os
import sys
from pathlib import Path

APP_DIR_NAME = "ZibaldOne"
ENV_DATA_DIR = "ZIBALDONE_HOME"


def data_dir() -> Path:
    """Return the data folder. `ZIBALDONE_HOME` overrides the platform default."""
    override = os.environ.get(ENV_DATA_DIR)
    if override:
        return Path(override).expanduser()
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_DIR_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    # Linux. Android gets its private app folder from Flet in v0.0.8.
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_DIR_NAME.lower()


def folder_usage(folder: Path) -> tuple[int, int]:
    """Return (number of files, total bytes) inside `folder`; (0, 0) if missing."""
    if not folder.is_dir():
        return 0, 0
    files = [path for path in folder.rglob("*") if path.is_file()]
    return len(files), sum(path.stat().st_size for path in files)


def human_size(size: int) -> str:
    """Format a byte count, for example 1536 -> '1.5 KB'."""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"
