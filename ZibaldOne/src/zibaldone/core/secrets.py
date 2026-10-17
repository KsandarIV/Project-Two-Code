"""Arcana (0.2.3): secret blocks, sealed with the user's key.

A secret block (type `secret` in `core/blocks.py`) never keeps its text in
clear: the Store seals it before saving (`seal_entry_values`), with the same
sealing as the backups (`core/crypto.py`: X25519, HKDF-SHA256, AES-256-GCM).
Two levels of security, two keys:

- **massimo**: sealed to the backup key; only the passphrase (or the recovery
  code) opens it.
- **protetto**: sealed to the "everyday" key, derived from the backup key with
  HKDF, so whoever can open the backups can always open these too, also from
  a snapshot on a new device; the PIN opens only this key.

Writing a secret needs only the public keys, so the diary can be written
without unlocking anything. Reading needs a `Vault` opened with the PIN or the
passphrase; the app closes it again after a few idle minutes.

The text of a secret never reaches the search index, the links, the
statistics, the exports or what is given to the anonymizer or an AI: all of
them read `to_text`, which for a secret is only "🔒 cifrato".

`cryptography` is imported only when a secret is sealed or opened, like the
backups: the rest of the app works without it.
"""

import base64
import binascii
import io
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

SECRET_PREFIX = "zbs1:"
PROTECTED, MAXIMUM = "protetto", "massimo"
LEVELS = (PROTECTED, MAXIMUM)
LEVEL_LABELS = {PROTECTED: "Protetto: si apre con il PIN o la passphrase", MAXIMUM: "Massimo: si apre solo con la passphrase"}
LOCKED_TEXT = "🔒 cifrato"
MAX_SECRET_CHARS = 20_000
EVERYDAY_INFO = b"zibaldone/secrets/everyday/v1"
VAULT_MINUTES = 5  # the app closes the secrets after this much time without using them


class SecretsError(ValueError):
    """A secret cannot be written or read. Messages are for the user."""


def level_of(options: Mapping[str, Any]) -> str:
    level = options.get("level", PROTECTED)
    return level if level in LEVELS else PROTECTED


def _raw(value: Any) -> Optional[bytes]:
    if not isinstance(value, str) or not value.startswith(SECRET_PREFIX):
        return None
    try:
        return base64.b64decode(value[len(SECRET_PREFIX):], validate=True)
    except (binascii.Error, ValueError):
        return None


def _header(value: Any) -> Optional[Dict[str, Any]]:
    raw = _raw(value)
    if raw is None:
        return None
    from zibaldone.core import crypto

    try:
        header = crypto.read_sealed_header(io.BytesIO(raw))
    except crypto.CryptoError:
        return None
    return header if header.get("level") in LEVELS else None


def is_sealed_value(value: Any) -> bool:
    """True for a secret as stored: the prefix, then a sealed file with its level."""
    return _header(value) is not None


def value_level(value: Any) -> str:
    header = _header(value)
    if header is None:
        raise SecretsError("non è un segreto cifrato")
    return header["level"]


def value_recipient(value: Any) -> str:
    """The id of the key that opens this secret."""
    header = _header(value)
    if header is None:
        raise SecretsError("non è un segreto cifrato")
    return header["recipient"]


def seal_value(text: str, public_key: Any, level: str) -> str:
    from zibaldone.core import crypto

    if level not in LEVELS:
        raise SecretsError(f"livello sconosciuto: {level}")
    sealed = crypto.seal(text.encode("utf-8"), public_key, {"level": level})
    return SECRET_PREFIX + crypto.b64encode(sealed)


def open_value(value: str, private_key: Any) -> str:
    from zibaldone.core import crypto

    raw = _raw(value)
    if raw is None:
        raise SecretsError("non è un segreto cifrato")
    try:
        return crypto.open_sealed(raw, private_key).plaintext.decode("utf-8")
    except (crypto.CryptoError, UnicodeDecodeError) as error:
        raise SecretsError(f"non riesco ad aprire questo segreto: {error}") from None


def everyday_key(main_private: Any) -> Any:
    """The key of the "protetto" level, always the same for the same backup key."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    from zibaldone.core import crypto

    raw = HKDF(algorithm=hashes.SHA256(), length=crypto.KEY_SIZE, salt=None, info=EVERYDAY_INFO).derive(crypto.private_key_bytes(main_private))
    return crypto.load_private_key(raw)


def key_id_of(private_key: Any) -> str:
    from zibaldone.core import crypto

    return crypto.key_fingerprint(private_key.public_key())


# * — entries —


def secret_specs(template: Any) -> List[Any]:
    return [spec for spec in template.blocks if spec.type == "secret"]


def has_plain_secrets(template: Any, values: Mapping[str, Any]) -> bool:
    return any(isinstance(values.get(spec.key), str) and values[spec.key] and not is_sealed_value(values[spec.key]) for spec in secret_specs(template))


def seal_entry_values(template: Any, values: Mapping[str, Any], public_key_for: Callable[[str], Any]) -> Dict[str, Any]:
    """The values with every secret written in clear sealed at its block's level."""
    sealed = dict(values)
    for spec in secret_specs(template):
        value = sealed.get(spec.key)
        if isinstance(value, str) and value and not is_sealed_value(value):
            level = level_of(spec.options)
            sealed[spec.key] = seal_value(value, public_key_for(level), level)
    return sealed


def check_sealed(template: Any, values: Mapping[str, Any]) -> None:
    """The last guard before saving: no secret may be written in clear."""
    for spec in secret_specs(template):
        if spec.key in values and not is_sealed_value(values[spec.key]):
            raise SecretsError(f"«{spec.label}» non è cifrato: non lo salvo")


# * — the vault: the keys opened for a while —


class Vault:
    """Private keys opened by the PIN or the passphrase, kept only in memory and only for a while."""

    def __init__(self, minutes: int = VAULT_MINUTES) -> None:
        self.minutes = minutes
        self._keys: Dict[str, Any] = {}
        self._last: Optional[datetime] = None

    def unlock(self, private_keys: Iterable[Any], now: datetime) -> None:
        for key in private_keys:
            self._keys[key_id_of(key)] = key
        self._last = now

    def lock(self) -> None:
        self._keys.clear()
        self._last = None

    def is_open(self, now: datetime) -> bool:
        if self._keys and self._last is not None and now - self._last > timedelta(minutes=self.minutes):
            self.lock()
        return bool(self._keys)

    def can_open(self, value: Any, now: datetime) -> bool:
        return self.is_open(now) and is_sealed_value(value) and value_recipient(value) in self._keys

    def reveal(self, value: str, now: datetime) -> str:
        """The text of a secret; SecretsError when the vault cannot open it."""
        if not self.is_open(now):
            raise SecretsError("i segreti sono chiusi: aprili con il PIN o la passphrase")
        key = self._keys.get(value_recipient(value))
        if key is None:
            raise SecretsError("questo segreto è di livello massimo: si apre solo con la passphrase")
        self._last = now
        return open_value(value, key)
