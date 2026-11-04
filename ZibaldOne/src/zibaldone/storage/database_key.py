"""Where the key of the encrypted database comes from (KAN-107).

- `seal_if_ready`: once the main password exists, the database is encrypted with a new random key. The key goes
  first into keys.json (sealed to the backup public key, no secret needed), then the plain file is replaced.
  The new key is returned so that the app can put it in the system keystore.
- `unlock_with_secret`: the main password or the recovery code open the private key, which opens the database key
  kept in keys.json (a new install, a wiped keystore, the terminal).
"""

import base64
import binascii
from pathlib import Path
from typing import Optional

from zibaldone.storage import keys, sealed_db
from zibaldone.storage.database import Store, database_path


def needs_sealing(folder: Path) -> bool:
    """The main password exists but the database is still plain (or not there yet)."""
    try:
        return keys.is_configured(folder) and keys.uses_generated_password(folder) and not sealed_db.is_sealed(folder)
    except keys.KeysError:
        return False


def is_locked(folder: Path) -> bool:
    """Encrypted, and its key not given to this process yet."""
    return sealed_db.is_sealed(folder) and not sealed_db.is_unlocked(folder)


def seal_if_ready(folder: Path) -> Optional[bytes]:
    """Encrypt the database when the main password exists. Returns the new key (for the keystore), or None."""
    if not needs_sealing(folder):
        if sealed_db.is_unlocked(folder) and keys.is_configured(folder) and not keys.has_database_key(folder):
            keys.add_database_key(folder, sealed_db.key_of(folder))  # new keys after «ricomincio»: keep the way back
        return None
    key = sealed_db.new_key()
    keys.add_database_key(folder, key)  # first: the key is never only in memory
    plain = database_path(folder)
    if plain.exists():
        sealed_db.seal_plain(folder, plain, key)
    else:
        sealed_db.unlock(folder, key)
        Store.open(folder).close()  # an empty database, encrypted from the start
    return key


def unlock_with_secret(folder: Path, password: Optional[str] = None, recovery_code: Optional[str] = None) -> bytes:
    """Open the database with the main password or the recovery code; returns its key (for the keystore)."""
    if password:
        private_key = keys.unlock_with_passphrase(folder, password)
    elif recovery_code:
        private_key = keys.unlock_with_recovery_code(folder, recovery_code)
    else:
        raise keys.KeysError("serve la password principale o il codice di recupero")
    key = keys.open_database_key(folder, private_key)
    sealed_db.unlock(folder, key)
    return key


def unlock_with_stored_key(folder: Path, text: Optional[str]) -> bool:
    """The key read back from the keystore (base64). False when missing or not the right one."""
    if not text:
        return False
    try:
        sealed_db.unlock(folder, base64.b64decode(text, validate=True))
    except (binascii.Error, ValueError, sealed_db.StoreError):
        return False
    return True


def stored_form(key: bytes) -> str:
    return base64.b64encode(key).decode("ascii")
