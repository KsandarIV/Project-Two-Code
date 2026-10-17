"""Where copies of the encrypted backups go. For the app a cloud is only a
place to put, list, fetch and delete files (ADR-0007), so adding OneDrive,
Dropbox or WebDAV later means one new class here and nothing else.

- `LocalFolderDestination`: any folder, for example a USB stick or the
  folder synced by Google Drive for desktop, OneDrive or Nextcloud;
- `GoogleDriveDestination`: the hidden app space (`appDataFolder`) of the
  user's Google Drive, through the Drive REST API v3.

Only flat file names are used; every file is already encrypted or public.
"""

import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Protocol
from urllib.parse import quote, urlencode

from zibaldone.cloud.http import CloudError, HttpClient, HttpResponse, error_detail, json_body

SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
FOLDER_NAME = "ZibaldOne"
DRIVE_FILES = "https://www.googleapis.com/drive/v3/files"
DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
UPLOAD_TIMEOUT = 300.0


@dataclass
class RemoteFile:
    name: str
    size: int
    modified: str = ""  # ISO time, as the destination reports it


class Destination(Protocol):
    kind: str

    @property
    def label(self) -> str: ...

    def list_files(self) -> List[RemoteFile]: ...

    def upload(self, name: str, data: bytes) -> RemoteFile: ...

    def download(self, name: str) -> bytes: ...

    def delete(self, name: str) -> bool: ...


def check_name(name: str) -> str:
    if not SAFE_NAME.match(name) or ".." in name:
        raise CloudError(f"nome di file non valido: {name!r}")
    return name


# * — a folder —


class LocalFolderDestination:
    """Files in `<chosen folder>/ZibaldOne/`, written atomically."""

    kind = "folder"

    def __init__(self, folder: Path) -> None:
        self.root = Path(folder).expanduser()
        self.directory = self.root / FOLDER_NAME

    @property
    def label(self) -> str:
        return f"cartella {self.directory}"

    def _ready(self) -> Path:
        if not self.root.exists():
            raise CloudError(f"la cartella {self.root} non esiste (chiavetta scollegata?)")
        self.directory.mkdir(exist_ok=True)
        return self.directory

    def list_files(self) -> List[RemoteFile]:
        if not self.directory.exists():
            return []
        files = []
        for path in sorted(self.directory.iterdir()):
            if path.is_file() and SAFE_NAME.match(path.name):
                stat = path.stat()
                files.append(RemoteFile(path.name, stat.st_size, str(int(stat.st_mtime))))
        return files

    def upload(self, name: str, data: bytes) -> RemoteFile:
        directory = self._ready()
        target = directory / check_name(name)
        temporary = directory / f".zbtmp-{secrets.token_hex(4)}"
        try:
            with open(temporary, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except OSError as error:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise CloudError(f"non riesco a scrivere in {directory}: {error}") from None
        return RemoteFile(name, len(data))

    def download(self, name: str) -> bytes:
        path = self.directory / check_name(name)
        try:
            return path.read_bytes()
        except FileNotFoundError:
            raise CloudError(f"{name} non c'è in {self.directory}") from None
        except OSError as error:
            raise CloudError(f"non riesco a leggere {path}: {error}") from None

    def delete(self, name: str) -> bool:
        try:
            (self.directory / check_name(name)).unlink()
            return True
        except FileNotFoundError:
            return False
        except OSError as error:
            raise CloudError(f"non riesco a cancellare {name}: {error}") from None


# * — Google Drive, hidden app space —


class GoogleDriveDestination:
    """Drive REST v3 in `appDataFolder`: the user doesn't see these files in
    Drive, but can see the space they take and delete them from Drive's
    settings ("Gestisci app"). The scope `drive.appdata` reaches nothing else.

    `access_token` is a callable so the caller can refresh an expired token;
    `on_unauthorized` is called once on a 401 and must return a fresh token.
    """

    kind = "google"

    def __init__(self, http: HttpClient, access_token: Callable[[], str], on_unauthorized: Optional[Callable[[], str]] = None, email: str = "") -> None:
        self.http = http
        self._token = access_token
        self._on_unauthorized = on_unauthorized
        self.email = email
        self._ids: Dict[str, str] = {}

    @property
    def label(self) -> str:
        return f"Google Drive{' di ' + self.email if self.email else ''} (spazio nascosto dell'app)"

    def _send(self, method: str, url: str, headers: Optional[Dict[str, str]] = None, body: Optional[bytes] = None, timeout: float = 30.0) -> HttpResponse:
        token = self._token()
        for attempt in range(2):
            response = self.http.request(method, url, {**(headers or {}), "Authorization": f"Bearer {token}"}, body, timeout)
            if response.status == 401 and attempt == 0 and self._on_unauthorized:
                token = self._on_unauthorized()
                continue
            break
        if response.status == 401:
            raise CloudError("l'accesso a Google è scaduto: entra di nuovo con `zbone account login`")
        if response.status == 403:
            raise CloudError(f"Google Drive ha rifiutato la richiesta ({error_detail(response)}). Hai dato il permesso per Drive all'accesso?")
        if response.status == 507 or b"storageQuotaExceeded" in response.body:
            raise CloudError("il tuo Google Drive è pieno")
        return response

    def list_files(self) -> List[RemoteFile]:
        files: List[RemoteFile] = []
        page_token = ""
        self._ids = {}
        while True:
            params = {"spaces": "appDataFolder", "fields": "nextPageToken,files(id,name,size,modifiedTime)", "pageSize": "1000"}
            if page_token:
                params["pageToken"] = page_token
            response = self._send("GET", f"{DRIVE_FILES}?{urlencode(params)}")
            if not response.ok:
                raise CloudError(f"non riesco a elencare i file su Drive ({error_detail(response)})")
            data = response.json()
            for item in data.get("files", []):
                name = item.get("name", "")
                if not SAFE_NAME.match(name):
                    continue
                if name in self._ids:  # Drive allows duplicates: keep the first, newest wins on upload
                    continue
                self._ids[name] = item["id"]
                files.append(RemoteFile(name, int(item.get("size", 0) or 0), item.get("modifiedTime", "")))
            page_token = data.get("nextPageToken", "")
            if not page_token:
                return sorted(files, key=lambda remote: remote.name)

    def _id_of(self, name: str) -> Optional[str]:
        if name not in self._ids:
            self.list_files()
        return self._ids.get(name)

    def upload(self, name: str, data: bytes) -> RemoteFile:
        check_name(name)
        existing = self._id_of(name)
        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "application/octet-stream",
            "X-Upload-Content-Length": str(len(data)),
        }
        if existing:
            start = self._send("PATCH", f"{DRIVE_UPLOAD}/{quote(existing)}?uploadType=resumable", headers, json_body({}))
        else:
            start = self._send("POST", f"{DRIVE_UPLOAD}?uploadType=resumable", headers, json_body({"name": name, "parents": ["appDataFolder"]}))
        location = start.header("Location")
        if not start.ok or not location:
            raise CloudError(f"Drive non ha accettato il caricamento di {name} ({error_detail(start)})")
        done = self._send("PUT", location, {"Content-Type": "application/octet-stream", "Content-Length": str(len(data))}, data, UPLOAD_TIMEOUT)
        if not done.ok:
            raise CloudError(f"caricamento di {name} non riuscito ({error_detail(done)})")
        item = done.json() or {}
        if isinstance(item, dict) and item.get("id"):
            self._ids[name] = item["id"]
        return RemoteFile(name, len(data))

    def download(self, name: str) -> bytes:
        file_id = self._id_of(check_name(name))
        if not file_id:
            raise CloudError(f"{name} non c'è su Google Drive")
        response = self._send("GET", f"{DRIVE_FILES}/{quote(file_id)}?alt=media", timeout=UPLOAD_TIMEOUT)
        if not response.ok:
            raise CloudError(f"non riesco a scaricare {name} ({error_detail(response)})")
        return response.body

    def delete(self, name: str) -> bool:
        file_id = self._id_of(check_name(name))
        if not file_id:
            return False
        response = self._send("DELETE", f"{DRIVE_FILES}/{quote(file_id)}")
        if response.status == 404:
            self._ids.pop(name, None)
            return False
        if not response.ok:
            raise CloudError(f"non riesco a cancellare {name} da Drive ({error_detail(response)})")
        self._ids.pop(name, None)
        return True

