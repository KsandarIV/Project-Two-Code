"""The account on this device and where the backups go (ADR-0007).

settings.json keeps only what is not secret:
- `account`: provider, email, name, when, whether Drive was allowed;
- `cloud`: mode (`local`, `google`, `folder`), the folder path, the last sync.
Tokens live in `account-token.json` (see `tokens.py`).

Signing in with Google is required at first start once the app has a Google
client configured (`google_auth.find_client`). Until then, during
development, the app works locally without an account.
"""

import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from zibaldone.cloud import google_auth, tokens as token_store
from zibaldone.cloud.destinations import Destination, GoogleDriveDestination, LocalFolderDestination
from zibaldone.cloud.google_auth import AuthError, GoogleClient
from zibaldone.cloud.http import CloudError, HttpClient, UrllibHttp
from zibaldone.storage.settings import SettingsError, load_settings, save_settings

MODES = ("local", "google", "folder")
MODE_LABELS = {
    "local": "solo locale",
    "google": "locale + Google Drive",
    "folder": "locale + una cartella",
}
NOT_CONFIGURED = (
    "l'accesso con Google non è ancora configurato in questa copia di ZibaldOne "
    "(manca il client OAuth: vedi docs/sviluppo/google-cloud.md)"
)


@dataclass
class AccountStatus:
    signed_in: bool
    email: Optional[str]
    name: Optional[str]
    mode: str
    folder_path: Optional[str]
    google_configured: bool
    last_sync: Optional[str]
    last_sync_error: Optional[str]
    drive_allowed: bool = False
    google_recovery: bool = False
    login_skipped: bool = False  # the user chose to go on without an account

    @property
    def mode_label(self) -> str:
        return MODE_LABELS.get(self.mode, self.mode)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _settings(folder: Path) -> Dict[str, Any]:
    try:
        return load_settings(folder)
    except SettingsError as error:
        raise CloudError(str(error)) from None


def _section(settings: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = settings.get(key)
    return dict(value) if isinstance(value, dict) else {}


def update_cloud_settings(folder: Path, **changes: Any) -> None:
    settings = _settings(folder)
    cloud = _section(settings, "cloud")
    cloud.update(changes)
    settings["cloud"] = cloud
    save_settings(folder, settings)


def google_configured(folder: Path) -> bool:
    try:
        return google_auth.find_client(folder) is not None
    except AuthError:
        return True  # a broken client file: sign-in will explain what is wrong


def account_status(folder: Path) -> AccountStatus:
    settings = _settings(folder)
    account = _section(settings, "account")
    cloud = _section(settings, "cloud")
    mode = cloud.get("mode") if cloud.get("mode") in MODES else "local"
    return AccountStatus(
        signed_in=bool(account.get("email")),
        email=account.get("email"),
        name=account.get("name") or None,
        mode=mode,
        folder_path=cloud.get("folder_path"),
        google_configured=google_configured(folder),
        last_sync=cloud.get("last_sync"),
        last_sync_error=cloud.get("last_sync_error"),
        drive_allowed=bool(account.get("drive")),
        google_recovery=bool(cloud.get("google_recovery")),
        login_skipped=bool(settings.get("login_skipped")),
    )


def login_required(folder: Path) -> bool:
    """True at first start when Google sign-in is available and the user has not said «no, grazie»."""
    status = account_status(folder)
    return status.google_configured and not status.signed_in and not status.login_skipped


def skip_login(folder: Path) -> None:
    """The user goes on without an account (solo locale): sign-in is not asked again, `zbone account login` still works."""
    settings = _settings(folder)
    settings["login_skipped"] = True
    save_settings(folder, settings)


def _client(folder: Path) -> GoogleClient:
    client = google_auth.find_client(folder)
    if client is None:
        raise AuthError(NOT_CONFIGURED)
    return client


def sign_in_with_google(
    folder: Path,
    open_browser: Callable[[str], Any] = webbrowser.open,
    timeout: float = google_auth.DEFAULT_TIMEOUT,
    http: Optional[HttpClient] = None,
) -> AccountStatus:
    """Open the browser, wait for Google, save tokens and email. Blocking: run it off the UI thread."""
    client = _client(folder)
    previous = account_status(folder)
    tokens, profile = google_auth.sign_in(client, http or UrllibHttp(), open_browser, timeout, login_hint=previous.email or "")
    token_store.save_tokens(folder, tokens)
    settings = _settings(folder)
    settings.pop("login_skipped", None)
    settings["account"] = {
        "provider": "google",
        "email": profile.email,
        "name": profile.name,
        "signed_in_at": _now(),
        "drive": google_auth.drive_granted(tokens),
    }
    cloud = _section(settings, "cloud")
    if cloud.get("mode") == "google" and (previous.email not in (None, profile.email) or not google_auth.drive_granted(tokens)):
        cloud.update(mode="local", google_recovery=False)  # the Drive copies belong to the other account
    settings["cloud"] = cloud
    save_settings(folder, settings)
    return account_status(folder)


def sign_out(folder: Path, http: Optional[HttpClient] = None) -> bool:
    """Forget the account on this device. Data and local backups stay. Returns
    True when Google confirmed the access was revoked."""
    saved = token_store.load_tokens(folder)
    revoked = google_auth.revoke(http or UrllibHttp(), saved) if saved else False
    token_store.delete_tokens(folder)
    settings = _settings(folder)
    settings.pop("account", None)
    settings["login_skipped"] = True  # signing out is a choice: no nagging at the next start
    cloud = _section(settings, "cloud")
    if cloud.get("mode") == "google":
        cloud["mode"] = "local"
    settings["cloud"] = cloud
    save_settings(folder, settings)
    return revoked


def choose_mode(folder: Path, mode: str, folder_path: Optional[str] = None, passphrase: Optional[str] = None) -> AccountStatus:
    """Switch between solo locale, Google Drive and a folder. Nothing is
    deleted anywhere when switching. With `passphrase`, the Google mode also
    turns on recovery through the Google account (see `sync.enable_google_recovery`)."""
    if mode not in MODES:
        raise CloudError(f"modalità sconosciuta '{mode}': scegli tra {', '.join(MODES)}")
    status = account_status(folder)
    changes: Dict[str, Any] = {"mode": mode, "last_sync_error": None}
    if mode == "google":
        if not status.signed_in:
            raise CloudError("prima entra con Google: `zbone account login`")
        if not status.drive_allowed:
            raise CloudError("all'accesso non hai dato il permesso per Drive: esci e rientra lasciando la casella spuntata")
    if mode == "folder":
        if not folder_path:
            raise CloudError("indica la cartella, per esempio una chiavetta o la cartella di OneDrive")
        target = Path(folder_path).expanduser()
        if not target.is_dir():
            raise CloudError(f"la cartella {target} non esiste")
        if target.resolve() == folder.resolve() or folder.resolve() in target.resolve().parents:
            raise CloudError("scegli una cartella fuori dalla cartella dati di ZibaldOne")
        changes["folder_path"] = str(target)
    update_cloud_settings(folder, **changes)
    if mode == "google" and passphrase:
        from zibaldone.cloud.sync import enable_google_recovery

        enable_google_recovery(folder, passphrase)
    return account_status(folder)


# * — tokens for API calls —


class GoogleSession:
    """Fresh access tokens for this device's account, refreshed and saved as needed."""

    def __init__(self, folder: Path, http: Optional[HttpClient] = None) -> None:
        self.folder = folder
        self.http = http or UrllibHttp()

    def _saved(self) -> token_store.Tokens:
        saved = token_store.load_tokens(self.folder)
        if saved is None:
            raise AuthError("non sei collegato a Google su questo dispositivo: `zbone account login`")
        return saved

    def refresh(self) -> str:
        fresh = google_auth.refresh_tokens(self.http, _client(self.folder), self._saved())
        token_store.save_tokens(self.folder, fresh)
        return fresh.access_token

    def access_token(self) -> str:
        saved = self._saved()
        return self.refresh() if saved.expired() else saved.access_token


def get_destination(folder: Path, http: Optional[HttpClient] = None) -> Optional[Destination]:
    """The destination chosen for this device, or None in solo locale."""
    status = account_status(folder)
    if status.mode == "folder":
        if not status.folder_path:
            raise CloudError("manca la cartella dei backup: `zbone cloud use folder PERCORSO`")
        return LocalFolderDestination(Path(status.folder_path))
    if status.mode == "google":
        session = GoogleSession(folder, http)
        return GoogleDriveDestination(session.http, session.access_token, session.refresh, email=status.email or "")
    return None
