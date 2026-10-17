"""Copies of the encrypted snapshots on the chosen destination, and the way back.

- `sync_now` uploads the encrypted snapshots that are missing remotely and
  `keys.json` (public key plus the wrapped private key: useless without the
  passphrase, the recovery code or the Google secret), then applies the same
  retention as on the device to the remote copies. Plain snapshots never
  leave the device: encryption must be on first.
- `enable_google_recovery` adds a "google" lock to the private key and puts
  its 32-byte secret in the hidden app space of the user's Drive. Whoever
  can enter that Google account can then open the backups: that is the
  trade-off of ADR-0006/0007, and the user turns it on knowingly.
- `recover_from_cloud` brings the data to a new device: keys, newest (or
  chosen) snapshot, restore.

Nothing is ever deleted remotely because it is missing locally: a lost
device must not wipe its own backups.
"""

import base64
import json
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from zibaldone.cloud.account import account_status, get_destination, update_cloud_settings
from zibaldone.cloud.destinations import Destination, RemoteFile
from zibaldone.cloud.http import CloudError, HttpClient
from zibaldone.storage import backups, keys
from zibaldone.storage.backups import BackupError, RestoreResult, SnapshotInfo
from zibaldone.storage.keys import KeysError

REMOTE_KEYS = "keys.json"
REMOTE_RECOVERY = "google-recovery.json"
RECOVERY_FORMAT = "zibaldone-google-recovery"
SECRET_NAME = "google"
NEEDS_ENCRYPTION = (
    "prima attiva la cifratura con `zbone backup setup`: "
    "nessun dato esce dal dispositivo in chiaro"
)


@dataclass
class SyncResult:
    destination: str
    uploaded: List[str] = field(default_factory=list)
    deleted: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)  # plain snapshots, never uploaded
    remote_count: int = 0

    @property
    def message(self) -> str:
        parts = [f"{len(self.uploaded)} caricate", f"{len(self.deleted)} scadute cancellate", f"{self.remote_count} in tutto"]
        text = f"Sincronizzato con {self.destination}: " + ", ".join(parts) + "."
        if self.skipped:
            text += f" {len(self.skipped)} istantanee in chiaro restano solo qui."
        return text


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _destination(folder: Path, destination: Optional[Destination], http: Optional[HttpClient]) -> Destination:
    chosen = destination or get_destination(folder, http)
    if chosen is None:
        raise CloudError("sei in modalità solo locale: scegli una destinazione con `zbone cloud use google` o `zbone cloud use folder PERCORSO`")
    return chosen


def _require_encryption(folder: Path) -> None:
    if not keys.is_configured(folder):
        raise CloudError(NEEDS_ENCRYPTION)


def _key_id_of(document_bytes: bytes) -> str:
    try:
        document = json.loads(document_bytes.decode("utf-8"))
        key_id = document["key_id"]
    except (UnicodeDecodeError, ValueError, KeyError, TypeError):
        raise CloudError("il file delle chiavi sulla destinazione è rovinato") from None
    if not isinstance(key_id, str):
        raise CloudError("il file delle chiavi sulla destinazione è rovinato")
    return key_id


def remote_snapshots(files: List[RemoteFile]) -> List[SnapshotInfo]:
    """Remote file names turned into SnapshotInfo (time from the name; reason unknown)."""
    found = []
    for item in files:
        match = backups.SNAPSHOT_NAME.match(item.name)
        if not match:
            continue
        created = datetime.strptime(match.group(1), backups.ID_TIME_FORMAT).replace(tzinfo=timezone.utc)
        found.append(SnapshotInfo(id=item.name[: -len(backups.SNAPSHOT_SUFFIX)], path=Path(item.name), created_at=created, size=item.size, encrypted=True))
    return sorted(found, key=lambda info: (info.created_at, info.id), reverse=True)


def list_remote(folder: Path, destination: Optional[Destination] = None, http: Optional[HttpClient] = None) -> List[SnapshotInfo]:
    return remote_snapshots(_destination(folder, destination, http).list_files())


def _push(folder: Path, destination: Destination) -> SyncResult:
    _require_encryption(folder)
    result = SyncResult(destination=destination.label)
    remote = {item.name: item for item in destination.list_files()}
    local_keys = keys.keys_path(folder).read_bytes()
    if REMOTE_KEYS in remote:
        remote_key = _key_id_of(destination.download(REMOTE_KEYS))
        if remote_key != keys.key_id(folder):
            raise CloudError(
                f"sulla destinazione ci sono i backup di un'altra chiave ({keys.format_key_id(remote_key)}). "
                "Per usarli su questo dispositivo: `zbone cloud recover`; altrimenti scegli un'altra destinazione"
            )
    destination.upload(REMOTE_KEYS, local_keys)
    local = backups.list_snapshots(folder)
    for snapshot in local:
        name = snapshot.path.name
        if not snapshot.encrypted:
            result.skipped.append(snapshot.id)
            continue
        if name in remote and remote[name].size == snapshot.size:
            continue
        destination.upload(name, snapshot.path.read_bytes())
        result.uploaded.append(snapshot.id)
    remote_now = remote_snapshots(destination.list_files())
    # What the device still keeps stays remote too (no upload/delete churn);
    # beyond that, the same retention as on the device.
    keep_local = [snapshot.id for snapshot in local if snapshot.encrypted]
    plan = backups.plan_retention(remote_now, backups.load_backup_settings(folder).retention, protect=keep_local)
    for info in plan.remove:
        if destination.delete(info.path.name):
            result.deleted.append(info.id)
    result.remote_count = len(remote_now) - len(result.deleted)
    return result


def sync_now(folder: Path, destination: Optional[Destination] = None, http: Optional[HttpClient] = None) -> SyncResult:
    """Upload what is missing and prune the remote copies; the outcome is saved in settings."""
    chosen = _destination(folder, destination, http)
    try:
        result = _push(folder, chosen)
    except (CloudError, BackupError, KeysError, OSError) as error:
        update_cloud_settings(folder, last_sync_error=str(error))
        if isinstance(error, CloudError):
            raise
        raise CloudError(str(error)) from None
    update_cloud_settings(folder, last_sync=_now(), last_sync_error=None)
    return result


def maybe_sync(folder: Path, http: Optional[HttpClient] = None) -> Optional[SyncResult]:
    """After an automatic snapshot: sync if a destination is chosen. Never raises;
    a failure is saved as `last_sync_error` and shown by `zbone cloud`."""
    try:
        if account_status(folder).mode == "local" or not keys.is_configured(folder):
            return None
        return sync_now(folder, http=http)
    except (CloudError, BackupError, KeysError, OSError):
        return None


# * — recovery through the Google account —


def enable_google_recovery(folder: Path, passphrase: str, destination: Optional[Destination] = None, http: Optional[HttpClient] = None) -> None:
    """Add the Google lock to the backup key and store its secret on Drive."""
    status = account_status(folder)
    if status.mode != "google":
        raise CloudError("il recupero con Google funziona solo in modalità Google Drive")
    _require_encryption(folder)
    private_key = keys.unlock_with_passphrase(folder, passphrase)
    chosen = _destination(folder, destination, http)
    secret = secrets.token_bytes(keys.SECRET_SIZE)
    document = {"format": RECOVERY_FORMAT, "key_id": keys.key_id(folder), "secret": base64.b64encode(secret).decode("ascii")}
    chosen.upload(REMOTE_RECOVERY, json.dumps(document).encode("utf-8"))
    keys.add_secret_wrap(folder, private_key, SECRET_NAME, secret)
    chosen.upload(REMOTE_KEYS, keys.keys_path(folder).read_bytes())
    update_cloud_settings(folder, google_recovery=True)


def disable_google_recovery(folder: Path, destination: Optional[Destination] = None, http: Optional[HttpClient] = None) -> None:
    removed = keys.remove_secret_wrap(folder, SECRET_NAME) if keys.is_configured(folder) else False
    try:
        chosen = _destination(folder, destination, http)
        chosen.delete(REMOTE_RECOVERY)
        if removed:
            chosen.upload(REMOTE_KEYS, keys.keys_path(folder).read_bytes())
    finally:
        update_cloud_settings(folder, google_recovery=False)


def _google_secret(destination: Destination, key_id: str) -> Optional[bytes]:
    names = {item.name for item in destination.list_files()}
    if REMOTE_RECOVERY not in names:
        return None
    try:
        document = json.loads(destination.download(REMOTE_RECOVERY).decode("utf-8"))
        if document.get("format") != RECOVERY_FORMAT or document.get("key_id") != key_id:
            return None
        secret = base64.b64decode(document["secret"])
    except (UnicodeDecodeError, ValueError, KeyError, TypeError):
        return None
    return secret if len(secret) == keys.SECRET_SIZE else None


# * — a new device —


def _install_keys(folder: Path, data: bytes) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    path = keys.keys_path(folder)
    temporary = path.with_name(f".{keys.KEYS_FILE}.download")
    temporary.write_bytes(data)
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    os.replace(temporary, path)
    try:
        keys.key_id(folder)  # validates format and public key
    except KeysError:
        path.unlink()
        raise


def _pick(snapshots: List[SnapshotInfo], reference: Optional[str]) -> SnapshotInfo:
    if not snapshots:
        raise CloudError("sulla destinazione non c'è nessuna istantanea")
    if not reference:
        return snapshots[0]
    matches = [item for item in snapshots if item.id == reference or item.id.startswith(reference) or item.id.endswith(reference)]
    if len(matches) != 1:
        raise CloudError(f"istantanea '{reference}' {'ambigua' if matches else 'non trovata'} sulla destinazione")
    return matches[0]


def unlock_for_recovery(
    folder: Path,
    destination: Destination,
    passphrase: Optional[str] = None,
    recovery_code: Optional[str] = None,
) -> X25519PrivateKey:
    """Make sure this device has the backup keys, then unlock them."""
    remote = {item.name for item in destination.list_files()}
    if REMOTE_KEYS not in remote:
        raise CloudError("sulla destinazione non ci sono backup di ZibaldOne")
    remote_keys = destination.download(REMOTE_KEYS)
    remote_key = _key_id_of(remote_keys)
    if keys.is_configured(folder):
        if keys.key_id(folder) != remote_key:
            raise CloudError(
                f"questo dispositivo ha già un'altra chiave dei backup ({keys.format_key_id(keys.key_id(folder))}). "
                "Il recupero serve su un dispositivo nuovo o su uno che usa la stessa chiave"
            )
    else:
        _install_keys(folder, remote_keys)
    if passphrase:
        return keys.unlock_with_passphrase(folder, passphrase)
    if recovery_code:
        return keys.unlock_with_recovery_code(folder, recovery_code)
    secret = _google_secret(destination, remote_key)
    if secret is None or SECRET_NAME not in keys.secret_names(folder):
        raise CloudError("serve la passphrase dei backup o il codice di recupero")
    return keys.unlock_with_secret(folder, SECRET_NAME, secret)


def google_recovery_available(folder: Path, destination: Optional[Destination] = None, http: Optional[HttpClient] = None) -> bool:
    chosen = _destination(folder, destination, http)
    try:
        remote_key = _key_id_of(chosen.download(REMOTE_KEYS))
    except CloudError:
        return False
    return _google_secret(chosen, remote_key) is not None


def recover_from_cloud(
    folder: Path,
    passphrase: Optional[str] = None,
    recovery_code: Optional[str] = None,
    reference: Optional[str] = None,
    destination: Optional[Destination] = None,
    http: Optional[HttpClient] = None,
) -> RestoreResult:
    """Download keys and a snapshot (the newest unless `reference`), then restore it.
    Close every Store on `folder` first, as for `backups.restore_snapshot`."""
    chosen = _destination(folder, destination, http)
    private_key = unlock_for_recovery(folder, chosen, passphrase, recovery_code)
    snapshot = _pick(remote_snapshots(chosen.list_files()), reference)
    local_path = backups.backups_dir(folder) / snapshot.path.name
    if not local_path.exists():
        local_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = local_path.with_name(f"{backups.TEMP_PREFIX}{secrets.token_hex(4)}")
        temporary.write_bytes(chosen.download(snapshot.path.name))
        os.replace(temporary, local_path)
    return backups.restore_snapshot(folder, snapshot.id, private_key)


def forget_remote(folder: Path, destination: Optional[Destination] = None, http: Optional[HttpClient] = None) -> int:
    """Delete every ZibaldOne file on the destination. Local data and backups stay."""
    chosen = _destination(folder, destination, http)
    count = 0
    for item in chosen.list_files():
        if item.name in (REMOTE_KEYS, REMOTE_RECOVERY) or backups.SNAPSHOT_NAME.match(item.name):
            if chosen.delete(item.name):
                count += 1
    update_cloud_settings(folder, google_recovery=False)
    return count
