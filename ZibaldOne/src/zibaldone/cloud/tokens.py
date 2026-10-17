"""The Google tokens, kept in `account-token.json` inside the data folder.

On Windows the file content is protected with DPAPI (`CryptProtectData`),
so only the same Windows user on the same PC can read it. On Android the
data folder is the app's private storage; on Linux the file is readable only
by the user (0600). The tokens are never written to settings.json or logs.
"""

import base64
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

TOKEN_FILE = "account-token.json"
TOKEN_FORMAT = "zibaldone-token"
EXPIRY_MARGIN = timedelta(seconds=60)


@dataclass
class Tokens:
    access_token: str
    refresh_token: Optional[str]
    expires_at: str  # ISO time in UTC
    scope: str = ""

    def expired(self, now: Optional[datetime] = None) -> bool:
        moment = now or datetime.now(timezone.utc)
        try:
            expiry = datetime.fromisoformat(self.expires_at)
        except ValueError:
            return True
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return moment >= expiry - EXPIRY_MARGIN

    def __repr__(self) -> str:  # never print tokens by accident
        return f"Tokens(expires_at={self.expires_at!r}, scope={self.scope!r})"


def expiry_from_now(seconds: float, now: Optional[datetime] = None) -> str:
    moment = (now or datetime.now(timezone.utc)) + timedelta(seconds=float(seconds))
    return moment.isoformat(timespec="seconds")


# * — Windows DPAPI —


def _dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DataBlob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    buffer = ctypes.create_string_buffer(data, len(data))
    source = DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    target = DataBlob()
    description = ctypes.c_wchar_p("ZibaldOne")
    flags = 0x1  # CRYPTPROTECT_UI_FORBIDDEN
    if protect:
        ok = crypt32.CryptProtectData(ctypes.byref(source), description, None, None, None, flags, ctypes.byref(target))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, flags, ctypes.byref(target))
    if not ok:
        raise OSError("DPAPI non disponibile")
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel32.LocalFree(target.pbData)


def _is_windows() -> bool:
    return sys.platform == "win32"


def protect(data: bytes) -> tuple:
    """Return (method, bytes): 'dpapi' on Windows when it works, else 'plain'."""
    if _is_windows():
        try:
            return "dpapi", _dpapi(data, protect=True)
        except (OSError, AttributeError, ValueError):
            pass
    return "plain", data


def unprotect(method: str, data: bytes) -> bytes:
    if method == "dpapi":
        return _dpapi(data, protect=False)
    if method == "plain":
        return data
    raise ValueError(f"protezione sconosciuta: {method}")


# * — file —


def token_path(folder: Path) -> Path:
    return folder / TOKEN_FILE


def save_tokens(folder: Path, tokens: Tokens) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    method, payload = protect(json.dumps(asdict(tokens)).encode("utf-8"))
    document = {"format": TOKEN_FORMAT, "protection": method, "data": base64.b64encode(payload).decode("ascii")}
    path = token_path(folder)
    temporary = path.with_name(f".{TOKEN_FILE}.tmp")
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(document))
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    os.replace(temporary, path)


def load_tokens(folder: Path) -> Optional[Tokens]:
    """The saved tokens, or None when there are none or they can't be read (then sign in again)."""
    path = token_path(folder)
    if not path.exists():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("format") != TOKEN_FORMAT:
            return None
        raw = unprotect(document["protection"], base64.b64decode(document["data"]))
        data = json.loads(raw.decode("utf-8"))
        return Tokens(
            access_token=str(data["access_token"]),
            refresh_token=data.get("refresh_token"),
            expires_at=str(data["expires_at"]),
            scope=str(data.get("scope", "")),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def delete_tokens(folder: Path) -> bool:
    try:
        token_path(folder).unlink()
        return True
    except FileNotFoundError:
        return False
