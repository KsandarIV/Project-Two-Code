"""The backup key pair, kept in `keys.json` inside the data folder.

The **public** key encrypts every snapshot without asking anything, so
automatic backups never need the passphrase. The **private** key, needed
only to restore or verify, is stored only wrapped (AES-256-GCM) by
key-encryption keys, one per "slot":

- `passphrase`: scrypt of the user's passphrase (parameters saved with it);
- `recovery`: HKDF of the random recovery code shown once at setup;
- `secret:<name>`: HKDF of any 32-byte secret (v0.0.8: recovery through the
  Google account, ADR-0007).

The passphrase, the recovery code and the plain private key are never
written to disk or logs: they exist only in memory while a command runs.

0.2.3, secret blocks (`core/secrets.py`): the `secrets` section keeps the
public half of the "everyday" key (derived from the backup key, so it needs
no backup of its own) and, when the user chose one, that key wrapped by the
PIN. Five wrong PINs in a row remove the PIN wrap: then only the passphrase
or the recovery code open the secrets.
"""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey

from zibaldone.core import crypto
from zibaldone.core.crypto import CryptoError, DecryptionError, ScryptParams

KEYS_FILE = "keys.json"
KEYS_FORMAT = "zibaldone-keys"
KEYS_FORMAT_VERSION = 1
MIN_PASSPHRASE_LENGTH = 10
DEFAULT_SCRYPT_PARAMS = ScryptParams()  # n=2**15, r=8, p=1; tests may lower it

PASSPHRASE_SLOT = "passphrase"
RECOVERY_SLOT = "recovery"
SECRET_PREFIX = "secret:"
SECRET_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
SECRET_SIZE = 32
WRAP_AAD = "zibaldone/keywrap/v1|{key_id}|{slot}"
KDF_INFO = "zibaldone/kek/v1/{slot}"

SECRETS_FIELD = "secrets"
PIN_SLOT = "pin"
PIN_MIN, PIN_MAX = 6, 12
PIN_ATTEMPTS = 5
PIN_SCRYPT_PARAMS = ScryptParams(n=2**16)  # 64 MiB: slow to try every PIN; tests may lower it


class KeysError(Exception):
    """The key file is missing, broken or the request is refused. Messages are for the user."""


class WrongSecretError(KeysError):
    """Wrong passphrase, recovery code or secret."""


@dataclass
class NewKeys:
    """A key pair just generated, not yet saved. Show `recovery_code` once."""

    key_id: str
    document: Dict[str, Any]
    recovery_code: str = field(repr=False)
    private_key: X25519PrivateKey = field(repr=False)


def keys_path(folder: Path) -> Path:
    return folder / KEYS_FILE


def is_configured(folder: Path) -> bool:
    """True once encryption has been set up (keys.json exists)."""
    return keys_path(folder).exists()


def format_key_id(key_id: str) -> str:
    """'3f9a1c0b7d2e4a56' -> '3f9a-1c0b-7d2e-4a56'."""
    return "-".join(key_id[index : index + 4] for index in range(0, len(key_id), 4))


def check_passphrase(passphrase: str) -> None:
    if not isinstance(passphrase, str) or len(passphrase) < MIN_PASSPHRASE_LENGTH:
        raise KeysError(
            f"la passphrase deve avere almeno {MIN_PASSPHRASE_LENGTH} caratteri: meglio tre o quattro parole a caso"
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# * — wrapping the private key —


def _aad(key_id: str, slot: str) -> bytes:
    return WRAP_AAD.format(key_id=key_id, slot=slot).encode("utf-8")


def _info(slot: str) -> bytes:
    return KDF_INFO.format(slot=slot).encode("utf-8")


def _passphrase_kek(passphrase: str, kdf: Dict[str, Any]) -> bytes:
    salt = crypto.b64decode(kdf.get("salt"), "sale", crypto.SALT_SIZE)
    return crypto.derive_passphrase_key(passphrase, salt, ScryptParams.from_dict(kdf))


def _secret_kek(secret: bytes, slot: str, kdf: Dict[str, Any]) -> bytes:
    salt = crypto.b64decode(kdf.get("salt"), "sale", crypto.SALT_SIZE)
    return crypto.derive_secret_key(secret, salt, _info(slot))


def _wrap(private_key: X25519PrivateKey, key_id: str, slot: str, kek: bytes, kdf: Dict[str, Any]) -> Dict[str, Any]:
    wrapped = crypto.wrap_key(kek, crypto.private_key_bytes(private_key), _aad(key_id, slot))
    return {"kdf": kdf, "cipher": "AES-256-GCM", **wrapped, "created_at": _now()}


def _passphrase_wrap(private_key: X25519PrivateKey, key_id: str, passphrase: str, params: Optional[ScryptParams]) -> Dict[str, Any]:
    check_passphrase(passphrase)
    kdf = {"name": "scrypt", **(params or DEFAULT_SCRYPT_PARAMS).validate().to_dict(), "salt": crypto.b64encode(crypto.new_salt())}
    return _wrap(private_key, key_id, PASSPHRASE_SLOT, _passphrase_kek(passphrase, kdf), kdf)


def _secret_wrap(private_key: X25519PrivateKey, key_id: str, slot: str, secret: bytes) -> Dict[str, Any]:
    kdf = {"name": "hkdf-sha256", "salt": crypto.b64encode(crypto.new_salt())}
    return _wrap(private_key, key_id, slot, _secret_kek(secret, slot, kdf), kdf)


def unwrap_private_key(wrap: Dict[str, Any], key_id: str, slot: str, kek: bytes, wrong: str) -> X25519PrivateKey:
    """Open one wrap and check that the key really is the one named by `key_id`."""
    try:
        private_key = crypto.load_private_key(crypto.unwrap_key(kek, wrap, _aad(key_id, slot)))
    except DecryptionError:
        raise WrongSecretError(wrong) from None
    except CryptoError as error:
        raise KeysError(f"chiave protetta rovinata: {error}") from None
    if crypto.key_fingerprint(private_key.public_key()) != key_id:
        raise KeysError("la chiave protetta non corrisponde alla chiave dei backup")
    return private_key


def unlock_recovery_wrap(wrap: Dict[str, Any], key_id: str, recovery_code: str) -> X25519PrivateKey:
    """Open a recovery wrap, also the copy stored inside each encrypted snapshot."""
    raw = crypto.parse_recovery_code(recovery_code)
    kdf = _kdf_of(wrap, "hkdf-sha256")
    return unwrap_private_key(
        wrap, key_id, RECOVERY_SLOT, _secret_kek(raw, RECOVERY_SLOT, kdf), "codice di recupero sbagliato: non è quello di questa chiave"
    )


def _kdf_of(wrap: Any, expected: str) -> Dict[str, Any]:
    kdf = wrap.get("kdf") if isinstance(wrap, dict) else None
    if not isinstance(kdf, dict) or kdf.get("name") != expected:
        raise KeysError("chiave protetta rovinata: derivazione sconosciuta")
    return kdf


# * — keys.json —


def _load(folder: Path) -> Dict[str, Any]:
    path = keys_path(folder)
    if not path.exists():
        raise KeysError("la cifratura dei backup non è ancora attiva: usa `zbone backup setup`")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise KeysError(f"non riesco a leggere {path}: {error}") from None
    if not isinstance(document, dict) or document.get("format") != KEYS_FORMAT:
        raise KeysError(f"{path} non è un file di chiavi di ZibaldOne")
    if document.get("format_version") != KEYS_FORMAT_VERSION:
        raise KeysError(f"{path} viene da una versione diversa di ZibaldOne (formato {document.get('format_version')})")
    try:
        public_key = crypto.load_public_key(crypto.b64decode(document.get("public_key"), "chiave pubblica", crypto.KEY_SIZE))
    except CryptoError as error:
        raise KeysError(f"{path}: {error}") from None
    if crypto.key_fingerprint(public_key) != document.get("key_id"):
        raise KeysError(f"{path}: l'id della chiave non corrisponde alla chiave pubblica")
    if not isinstance(document.get("wraps"), dict) or PASSPHRASE_SLOT not in document["wraps"]:
        raise KeysError(f"{path}: manca la chiave protetta dalla passphrase")
    return document


def _save(folder: Path, document: Dict[str, Any]) -> None:
    """Atomic write (temporary file, fsync, rename), readable only by the user where possible."""
    folder.mkdir(parents=True, exist_ok=True)
    path = keys_path(folder)
    temporary = path.with_name(f".{KEYS_FILE}.tmp")
    document = {**document, "updated_at": _now()}
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(document, indent=2, ensure_ascii=False))
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass  # Windows: the data folder is already private to the user
    os.replace(temporary, path)


def key_id(folder: Path) -> str:
    return _load(folder)["key_id"]


def load_public_key(folder: Path) -> X25519PublicKey:
    """The key every snapshot is encrypted to; never needs the passphrase."""
    return crypto.load_public_key(crypto.b64decode(_load(folder)["public_key"], "chiave pubblica", crypto.KEY_SIZE))


def _recovery_wrap_of(document: Dict[str, Any]) -> Dict[str, Any]:
    wrap = document["wraps"].get(RECOVERY_SLOT)
    if not isinstance(wrap, dict):
        raise KeysError("manca la chiave protetta dal codice di recupero")
    return wrap


def recovery_wrap(folder: Path) -> Dict[str, Any]:
    """The recovery-code wrap, copied into each encrypted snapshot so a single
    file can be opened elsewhere with the recovery code alone."""
    return _recovery_wrap_of(_load(folder))


# * — setup —


def create_keys(passphrase: str, scrypt_params: Optional[ScryptParams] = None) -> NewKeys:
    """Generate the key pair and its wraps in memory; nothing is saved yet."""
    check_passphrase(passphrase)
    private_key = crypto.generate_private_key()
    public_key = private_key.public_key()
    new_key_id = crypto.key_fingerprint(public_key)
    recovery_code = crypto.generate_recovery_code()
    recovery_raw = crypto.parse_recovery_code(recovery_code)
    created = _now()
    from zibaldone.core.secrets import everyday_key

    everyday = everyday_key(private_key).public_key()
    document = {
        "format": KEYS_FORMAT,
        "format_version": KEYS_FORMAT_VERSION,
        "algorithm": "X25519",
        "key_id": new_key_id,
        "public_key": crypto.b64encode(crypto.public_key_bytes(public_key)),
        "created_at": created,
        "wraps": {
            PASSPHRASE_SLOT: _passphrase_wrap(private_key, new_key_id, passphrase, scrypt_params),
            RECOVERY_SLOT: _secret_wrap(private_key, new_key_id, RECOVERY_SLOT, recovery_raw),
        },
        SECRETS_FIELD: {"key_id": crypto.key_fingerprint(everyday), "public_key": crypto.b64encode(crypto.public_key_bytes(everyday))},
    }
    return NewKeys(key_id=new_key_id, document=document, recovery_code=recovery_code, private_key=private_key)


def save_new_keys(folder: Path, new_keys: NewKeys) -> None:
    if is_configured(folder):
        raise KeysError("la cifratura è già attiva: per cambiare passphrase usa `zbone backup passphrase`")
    _save(folder, new_keys.document)


def setup_keys(folder: Path, passphrase: str, scrypt_params: Optional[ScryptParams] = None) -> NewKeys:
    """Create and save the keys in one step. Returns the recovery code to show once."""
    if is_configured(folder):
        raise KeysError("la cifratura è già attiva: per cambiare passphrase usa `zbone backup passphrase`")
    new_keys = create_keys(passphrase, scrypt_params)
    save_new_keys(folder, new_keys)
    return new_keys


# * — unlocking —


def unlock_with_passphrase(folder: Path, passphrase: str) -> X25519PrivateKey:
    document = _load(folder)
    wrap = document["wraps"][PASSPHRASE_SLOT]
    try:
        kek = _passphrase_kek(passphrase, _kdf_of(wrap, "scrypt"))
    except CryptoError as error:
        raise KeysError(f"chiave protetta rovinata: {error}") from None
    return unwrap_private_key(wrap, document["key_id"], PASSPHRASE_SLOT, kek, "passphrase sbagliata")


def unlock_with_recovery_code(folder: Path, recovery_code: str) -> X25519PrivateKey:
    """Raises RecoveryCodeError for typos, WrongSecretError for a valid but different code."""
    document = _load(folder)
    return unlock_recovery_wrap(_recovery_wrap_of(document), document["key_id"], recovery_code)


def _secret_slot(name: str) -> str:
    if not isinstance(name, str) or not SECRET_NAME.match(name):
        raise KeysError(f"nome del segreto non valido: '{name}' (minuscole, numeri, - e _)")
    return SECRET_PREFIX + name


def _check_secret(secret: bytes) -> None:
    if not isinstance(secret, bytes) or len(secret) != SECRET_SIZE:
        raise KeysError(f"il segreto deve essere di {SECRET_SIZE} byte")


def unlock_with_secret(folder: Path, name: str, secret: bytes) -> X25519PrivateKey:
    slot = _secret_slot(name)
    _check_secret(secret)
    document = _load(folder)
    wrap = document["wraps"].get(slot)
    if wrap is None:
        raise KeysError(f"non esiste un segreto '{name}' per questa chiave")
    kek = _secret_kek(secret, slot, _kdf_of(wrap, "hkdf-sha256"))
    return unwrap_private_key(wrap, document["key_id"], slot, kek, f"il segreto '{name}' non è quello giusto")


# * — changing the wraps —


def _check_matches(document: Dict[str, Any], private_key: X25519PrivateKey) -> None:
    if crypto.key_fingerprint(private_key.public_key()) != document["key_id"]:
        raise KeysError("questa chiave privata non è quella dei backup")


def change_passphrase(folder: Path, old_passphrase: str, new_passphrase: str, scrypt_params: Optional[ScryptParams] = None) -> None:
    private_key = unlock_with_passphrase(folder, old_passphrase)
    _replace_passphrase(folder, private_key, new_passphrase, scrypt_params)


def reset_passphrase(folder: Path, recovery_code: str, new_passphrase: str, scrypt_params: Optional[ScryptParams] = None) -> None:
    """Forgotten passphrase: the recovery code sets a new one (the code stays valid)."""
    private_key = unlock_with_recovery_code(folder, recovery_code)
    _replace_passphrase(folder, private_key, new_passphrase, scrypt_params)


def _replace_passphrase(folder: Path, private_key: X25519PrivateKey, passphrase: str, scrypt_params: Optional[ScryptParams]) -> None:
    document = _load(folder)
    _check_matches(document, private_key)
    document["wraps"][PASSPHRASE_SLOT] = _passphrase_wrap(private_key, document["key_id"], passphrase, scrypt_params)
    _save(folder, document)


def add_secret_wrap(folder: Path, private_key: X25519PrivateKey, name: str, secret: bytes) -> None:
    """Let a 32-byte secret (for example one kept by the Google account) unlock the key."""
    slot = _secret_slot(name)
    _check_secret(secret)
    document = _load(folder)
    _check_matches(document, private_key)
    document["wraps"][slot] = _secret_wrap(private_key, document["key_id"], slot, secret)
    _save(folder, document)


def remove_secret_wrap(folder: Path, name: str) -> bool:
    """Remove a secret wrap; True if it existed. Copies made elsewhere are not affected."""
    slot = _secret_slot(name)
    document = _load(folder)
    if document["wraps"].pop(slot, None) is None:
        return False
    _save(folder, document)
    return True


def secret_names(folder: Path) -> List[str]:
    return sorted(slot[len(SECRET_PREFIX) :] for slot in _load(folder)["wraps"] if slot.startswith(SECRET_PREFIX))


# * — 0.2.3: the keys of the secret blocks —


def _secrets_section(document: Dict[str, Any]) -> Dict[str, Any]:
    section = document.get(SECRETS_FIELD)
    return section if isinstance(section, dict) else {}


def secret_public_keys(folder: Path) -> Dict[str, X25519PublicKey]:
    """Level → public key that seals it. 'protetto' is missing until the everyday key is known."""
    from zibaldone.core.secrets import MAXIMUM, PROTECTED

    document = _load(folder)
    found = {MAXIMUM: crypto.load_public_key(crypto.b64decode(document["public_key"], "chiave pubblica", crypto.KEY_SIZE))}
    section = _secrets_section(document)
    if section.get("public_key"):
        try:
            everyday = crypto.load_public_key(crypto.b64decode(section["public_key"], "chiave dei segreti", crypto.KEY_SIZE))
        except CryptoError as error:
            raise KeysError(f"{keys_path(folder)}: {error}") from None
        if crypto.key_fingerprint(everyday) == section.get("key_id"):
            found[PROTECTED] = everyday
    return found


def remember_everyday_key(folder: Path, main_private: X25519PrivateKey) -> X25519PrivateKey:
    """The everyday key of this backup key; its public half is saved for writing without unlocking."""
    from zibaldone.core.secrets import everyday_key

    document = _load(folder)
    _check_matches(document, main_private)
    everyday = everyday_key(main_private)
    public = everyday.public_key()
    section = _secrets_section(document)
    if section.get("key_id") != crypto.key_fingerprint(public):
        document[SECRETS_FIELD] = {"key_id": crypto.key_fingerprint(public), "public_key": crypto.b64encode(crypto.public_key_bytes(public))}
        _save(folder, document)
    return everyday


def unlock_secrets_with_passphrase(folder: Path, passphrase: str) -> List[X25519PrivateKey]:
    """Both keys of the secrets: the backup key ('massimo') and the everyday key ('protetto')."""
    main = unlock_with_passphrase(folder, passphrase)
    return [main, remember_everyday_key(folder, main)]


def unlock_secrets_with_recovery_code(folder: Path, recovery_code: str) -> List[X25519PrivateKey]:
    main = unlock_with_recovery_code(folder, recovery_code)
    return [main, remember_everyday_key(folder, main)]


def check_pin(pin: str) -> None:
    if not isinstance(pin, str) or not pin.isdigit() or not PIN_MIN <= len(pin) <= PIN_MAX:
        raise KeysError(f"il PIN è fatto di cifre, da {PIN_MIN} a {PIN_MAX}")


def has_pin(folder: Path) -> bool:
    try:
        return PIN_SLOT in _secrets_section(_load(folder))
    except KeysError:
        return False


def set_pin(folder: Path, main_private: X25519PrivateKey, pin: str, scrypt_params: Optional[ScryptParams] = None) -> None:
    """Let the PIN open the everyday key (the 'protetto' secrets), never the backup key."""
    check_pin(pin)
    everyday = remember_everyday_key(folder, main_private)
    document = _load(folder)
    section = _secrets_section(document)
    kdf = {"name": "scrypt", **(scrypt_params or PIN_SCRYPT_PARAMS).validate().to_dict(), "salt": crypto.b64encode(crypto.new_salt())}
    section[PIN_SLOT] = _wrap(everyday, section["key_id"], PIN_SLOT, _passphrase_kek(pin, kdf), kdf)
    section["pin_failures"] = 0
    document[SECRETS_FIELD] = section
    _save(folder, document)


def remove_pin(folder: Path) -> bool:
    document = _load(folder)
    section = _secrets_section(document)
    if section.pop(PIN_SLOT, None) is None:
        return False
    section.pop("pin_failures", None)
    document[SECRETS_FIELD] = section
    _save(folder, document)
    return True


def unlock_with_pin(folder: Path, pin: str) -> X25519PrivateKey:
    """The everyday key. After PIN_ATTEMPTS wrong PINs in a row the PIN is removed."""
    document = _load(folder)
    section = _secrets_section(document)
    wrap = section.get(PIN_SLOT)
    if not isinstance(wrap, dict):
        raise KeysError("non hai ancora scelto un PIN: apri i segreti con la passphrase")
    try:
        kek = _passphrase_kek(pin, _kdf_of(wrap, "scrypt"))
    except CryptoError as error:
        raise KeysError(f"PIN protetto rovinato: {error}") from None
    try:
        everyday = unwrap_private_key(wrap, section["key_id"], PIN_SLOT, kek, "PIN sbagliato")
    except WrongSecretError:
        failures = int(section.get("pin_failures", 0)) + 1
        if failures >= PIN_ATTEMPTS:
            section.pop(PIN_SLOT, None)
            section.pop("pin_failures", None)
            _save(folder, document)
            raise WrongSecretError(f"PIN sbagliato {PIN_ATTEMPTS} volte: l'ho tolto. Apri i segreti con la passphrase e scegline uno nuovo.") from None
        section["pin_failures"] = failures
        _save(folder, document)
        left = PIN_ATTEMPTS - failures
        raise WrongSecretError(f"PIN sbagliato: ancora {left} tentativ{'o' if left == 1 else 'i'}") from None
    if section.get("pin_failures"):
        section["pin_failures"] = 0
        _save(folder, document)
    return everyday
