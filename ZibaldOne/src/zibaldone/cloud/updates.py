"""Is there a newer ZibaldOne? (ADR-0003)

Releases live on GitHub: tag `zibaldone-vX.Y.Z`, with the APK attached.
The check reads GitHub's public API without an account: GitHub sees the
device's IP address and the app version (User-Agent); nothing about the user is sent.
The graphical app checks at most once a day; it can be turned off.
"""

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from zibaldone import __version__
from zibaldone.cloud.http import CloudError, HttpClient, UrllibHttp, error_detail
from zibaldone.storage.settings import SettingsError, load_settings, save_settings

REPOSITORY = "KsandarIV/Project-Two-Code"
RELEASES_API = f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=30"
RELEASES_PAGE = f"https://github.com/{REPOSITORY}/releases"
TAG_PREFIX = "zibaldone-v"
SETTINGS_KEY = "updates"
CHECK_INTERVAL = timedelta(hours=24)
# X.Y.Z, or X.Y.Z.N for a mini patch (N from 1; `0.3.2.0` is never written, it is `0.3.2`).
VERSION = re.compile(r"^(\d{1,3})\.(\d{1,2})\.(\d{1,3})(?:\.([1-9]\d?))?$")


@dataclass
class Release:
    version: str
    tag: str
    page_url: str
    apk_url: Optional[str] = None
    published_at: str = ""
    notes: str = ""


def parse_version(text: str) -> Tuple[int, int, int, int]:
    """(major, minor, patch, fix); `fix` is 0 for a normal release, so tuples sort in release order."""
    match = VERSION.match(text.strip())
    if not match:
        raise ValueError(f"versione non valida: {text!r}")
    major, minor, patch, fix = match.groups()
    return int(major), int(minor), int(patch), int(fix or 0)


def version_code(text: str) -> int:
    """Android `versionCode`: always growing. 0.3.2 -> 300200, 0.3.2.1 -> 300201, 1.2.3 -> 10200300.

    Larger than every code of the old three-number formula (0.3.2 was 3002), so installed apps still update.
    """
    major, minor, patch, fix = parse_version(text)
    if major > 209:
        raise ValueError(f"versione troppo grande per Android: {text}")
    return major * 10_000_000 + minor * 100_000 + patch * 100 + fix


def releases_from(data: Any) -> List[Release]:
    """The ZibaldOne releases in a GitHub API answer, newest first. Drafts and other tags are skipped."""
    found = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict) or item.get("draft"):
            continue
        tag = item.get("tag_name") or ""
        if not tag.startswith(TAG_PREFIX):
            continue
        version = tag[len(TAG_PREFIX):]
        try:
            parse_version(version)
        except ValueError:
            continue
        apk = next(
            (asset.get("browser_download_url") for asset in item.get("assets") or [] if str(asset.get("name", "")).endswith(".apk")),
            None,
        )
        found.append(Release(version, tag, item.get("html_url") or RELEASES_PAGE, apk, item.get("published_at") or "", (item.get("body") or "")[:2000]))
    return sorted(found, key=lambda release: parse_version(release.version), reverse=True)


def latest_release(http: Optional[HttpClient] = None) -> Optional[Release]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"ZibaldOne/{__version__}",
    }
    response = (http or UrllibHttp()).request("GET", RELEASES_API, headers, timeout=15)
    if response.status in (403, 429):
        raise CloudError("GitHub ha ricevuto troppe richieste da questa rete: riprova tra un'ora")
    if response.status == 404:
        raise CloudError("non trovo le versioni di ZibaldOne su GitHub (il repository è privato?)")
    if not response.ok:
        raise CloudError(f"non riesco a controllare gli aggiornamenti ({error_detail(response)})")
    releases = releases_from(response.json())
    return releases[0] if releases else None


def is_newer(release: Optional[Release], current: str = __version__) -> bool:
    return release is not None and parse_version(release.version) > parse_version(current)


# * — settings: automatic check and the last answer —


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _section(folder: Path) -> Dict[str, Any]:
    value = load_settings(folder).get(SETTINGS_KEY)
    return dict(value) if isinstance(value, dict) else {}


def _save(folder: Path, section: Dict[str, Any]) -> None:
    settings = load_settings(folder)
    settings[SETTINGS_KEY] = section
    save_settings(folder, settings)


def auto_check_enabled(folder: Path) -> bool:
    try:
        return _section(folder).get("auto", True) is not False
    except SettingsError:
        return False


def set_auto_check(folder: Path, enabled: bool) -> None:
    section = _section(folder)
    section["auto"] = bool(enabled)
    _save(folder, section)


def cached_release(folder: Path, current: str = __version__) -> Optional[Release]:
    """The newer release seen at the last check, without going online."""
    try:
        latest = _section(folder).get("latest")
        release = Release(**latest) if isinstance(latest, dict) else None
        return release if is_newer(release, current) else None
    except (SettingsError, TypeError, ValueError):
        return None


def check_now(folder: Path, current: str = __version__, http: Optional[HttpClient] = None, now: Optional[datetime] = None) -> Optional[Release]:
    """Ask GitHub now; return the newer release, or None when up to date. Raises CloudError."""
    release = latest_release(http)
    section = _section(folder)
    section["last_check"] = (now or _now()).isoformat(timespec="seconds")
    section["latest"] = asdict(release) if release else None
    _save(folder, section)
    return release if is_newer(release, current) else None


def maybe_check(folder: Path, current: str = __version__, http: Optional[HttpClient] = None, now: Optional[datetime] = None) -> Optional[Release]:
    """At app start: at most once a day, only if the automatic check is on. Never raises."""
    moment = now or _now()
    try:
        if not auto_check_enabled(folder):
            return None
        last = _section(folder).get("last_check")
        if last:
            try:
                previous = datetime.fromisoformat(last)
                if previous.tzinfo is None:
                    previous = previous.replace(tzinfo=timezone.utc)
                if timedelta(0) <= moment - previous < CHECK_INTERVAL:
                    return cached_release(folder, current)
            except ValueError:
                pass
        return check_now(folder, current, http, moment)
    except (CloudError, SettingsError, OSError, ValueError):
        return cached_release(folder, current)
