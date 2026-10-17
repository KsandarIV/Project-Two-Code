"""Encryption building blocks for backups, made only of `cryptography` primitives.

Two jobs (ADR-0006):

- **sealing**: encrypt a file to a long-term X25519 public key, so automatic
  backups never need the passphrase (the design of age and libsodium sealed
  boxes). Each file gets an ephemeral X25519 key; ECDH + HKDF-SHA256 give a
  fresh 256-bit AES-GCM key.
- **key wrapping**: protect the X25519 private key with key-encryption keys
  derived from the passphrase (scrypt), from the recovery code or from another
  32-byte secret (HKDF-SHA256).

Sealed file format, version 1::

    MAGIC (8 bytes) | version (1 byte) | header length (4 bytes, big endian)
    | header (UTF-8 JSON object) | nonce (12 bytes) | AES-256-GCM ciphertext + tag

Everything before the nonce is authenticated as associated data, so the
header can be read without the key but not changed without being noticed.
The header holds `alg`, `recipient` (key id), `ephemeral` (public key) and
any public fields the caller adds.
"""

import base64
import binascii
import hashlib
import json
import os
import secrets
import struct
import unicodedata
from dataclasses import dataclass
from typing import Any, BinaryIO, Dict, Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"ZBSEALED"
FORMAT_VERSION = 1
SEAL_ALGORITHM = "X25519-HKDF-SHA256-AES-256-GCM"
SEAL_INFO = b"zibaldone/sealed/v1"
KEY_ID_DOMAIN = b"zibaldone/key-id/v1"
RESERVED_HEADER_FIELDS = ("alg", "recipient", "ephemeral")

KEY_SIZE = 32
NONCE_SIZE = 12
TAG_SIZE = 16
SALT_SIZE = 16
MAX_PAYLOAD_SIZE = 1 << 30  # 1 GiB: a diary database is far smaller
MAX_HEADER_SIZE = 64 * 1024
PREFIX_SIZE = len(MAGIC) + 1 + 4

MIN_SCRYPT_N = 2**10  # only for fast tests; the default stays 2**15
MAX_SCRYPT_N = 2**20
MAX_SCRYPT_MEMORY = 1 << 30

# Crockford base32: no I, L, O, U, so the code is easy to read and copy by hand.
RECOVERY_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
RECOVERY_LOOKALIKES = str.maketrans({"O": "0", "I": "1", "L": "1"})
RECOVERY_GROUP_SIZE = 4
RECOVERY_DATA_GROUPS = 6  # 24 characters = 120 random bits
RECOVERY_BYTES = 15
RECOVERY_CHECK_BITS = 20  # one more group of 4 characters
RECOVERY_LENGTH = RECOVERY_GROUP_SIZE * (RECOVERY_DATA_GROUPS + 1)
RECOVERY_CHECK_DOMAIN = b"zibaldone/recovery-check/v1"


class CryptoError(Exception):
    """An encrypted file or key cannot be used. Messages are for the user."""


class DecryptionError(CryptoError):
    """Authentication failed: wrong key, or the data was altered or damaged."""


class RecoveryCodeError(CryptoError):
    """The recovery code is malformed or has a typo (checksum mismatch)."""


# * — encoding helpers —


def b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64decode(text: Any, what: str, size: Optional[int] = None) -> bytes:
    """Strict base64 decoding; `size` checks the decoded length."""
    try:
        data = base64.b64decode(text, validate=True)
    except (binascii.Error, TypeError, ValueError):
        raise CryptoError(f"{what}: valore non valido") from None
    if size is not None and len(data) != size:
        raise CryptoError(f"{what}: lunghezza sbagliata")
    return data


# * — X25519 keys —


def generate_private_key() -> X25519PrivateKey:
    return X25519PrivateKey.generate()


def public_key_bytes(public_key: X25519PublicKey) -> bytes:
    return public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def private_key_bytes(private_key: X25519PrivateKey) -> bytes:
    return private_key.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
    )


def load_public_key(raw: bytes) -> X25519PublicKey:
    if len(raw) != KEY_SIZE:
        raise CryptoError("chiave pubblica non valida")
    return X25519PublicKey.from_public_bytes(raw)


def load_private_key(raw: bytes) -> X25519PrivateKey:
    if len(raw) != KEY_SIZE:
        raise CryptoError("chiave privata non valida")
    return X25519PrivateKey.from_private_bytes(raw)


def key_fingerprint(public_key: X25519PublicKey) -> str:
    """Short public id of a key pair: 16 hex characters of a SHA-256."""
    return hashlib.sha256(KEY_ID_DOMAIN + public_key_bytes(public_key)).hexdigest()[:16]


# * — sealing to a public key —


@dataclass
class SealedFile:
    header: Dict[str, Any]
    plaintext: bytes


def is_sealed(data: bytes) -> bool:
    """True when `data` (or its first bytes) starts like a sealed file."""
    return data[: len(MAGIC)] == MAGIC


def _sealing_key(shared: bytes, ephemeral_public: bytes, recipient_public: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(), length=KEY_SIZE, salt=ephemeral_public + recipient_public, info=SEAL_INFO
    ).derive(shared)


def _encode_header(header: Dict[str, Any]) -> bytes:
    return json.dumps(header, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def seal(plaintext: bytes, recipient: X25519PublicKey, header_fields: Optional[Dict[str, Any]] = None) -> bytes:
    """Encrypt `plaintext` so that only the owner of `recipient`'s private key can read it.

    `header_fields` are public (readable without the key) but authenticated.
    """
    if len(plaintext) > MAX_PAYLOAD_SIZE:
        raise CryptoError("file troppo grande da cifrare (massimo 1 GiB)")
    fields = dict(header_fields or {})
    clash = [name for name in RESERVED_HEADER_FIELDS if name in fields]
    if clash:
        raise ValueError(f"campi riservati nell'intestazione: {', '.join(clash)}")
    ephemeral = X25519PrivateKey.generate()
    ephemeral_public = public_key_bytes(ephemeral.public_key())
    try:
        shared = ephemeral.exchange(recipient)
    except ValueError:
        raise CryptoError("chiave pubblica non valida") from None
    key = _sealing_key(shared, ephemeral_public, public_key_bytes(recipient))
    header = {**fields, "alg": SEAL_ALGORITHM, "recipient": key_fingerprint(recipient), "ephemeral": b64encode(ephemeral_public)}
    header_bytes = _encode_header(header)
    if len(header_bytes) > MAX_HEADER_SIZE:
        raise CryptoError("intestazione troppo grande")
    prefix = MAGIC + bytes([FORMAT_VERSION]) + struct.pack(">I", len(header_bytes)) + header_bytes
    nonce = os.urandom(NONCE_SIZE)
    return prefix + nonce + AESGCM(key).encrypt(nonce, plaintext, prefix)


def _parse_prefix(prefix: bytes) -> int:
    """Check magic and version; return the header length."""
    if len(prefix) < PREFIX_SIZE or not is_sealed(prefix):
        raise CryptoError("non è un file cifrato di ZibaldOne")
    version = prefix[len(MAGIC)]
    if version > FORMAT_VERSION:
        raise CryptoError(f"file cifrato con un formato più recente ({version}): aggiorna ZibaldOne")
    if version != FORMAT_VERSION:
        raise CryptoError(f"formato di cifratura sconosciuto ({version})")
    (length,) = struct.unpack(">I", prefix[len(MAGIC) + 1 : PREFIX_SIZE])
    if not 2 <= length <= MAX_HEADER_SIZE:
        raise CryptoError("intestazione del file cifrato non valida")
    return length


def _parse_header(header_bytes: bytes) -> Dict[str, Any]:
    try:
        header = json.loads(header_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise CryptoError("intestazione del file cifrato rovinata") from None
    if not isinstance(header, dict) or header.get("alg") != SEAL_ALGORITHM:
        raise CryptoError("algoritmo di cifratura sconosciuto")
    if not isinstance(header.get("recipient"), str):
        raise CryptoError("intestazione del file cifrato rovinata")
    b64decode(header.get("ephemeral"), "chiave effimera", KEY_SIZE)
    return header


def read_sealed_header(stream: BinaryIO) -> Dict[str, Any]:
    """Read only the public header of a sealed file (no key needed)."""
    length = _parse_prefix(stream.read(PREFIX_SIZE))
    header_bytes = stream.read(length)
    if len(header_bytes) != length:
        raise CryptoError("file cifrato troncato")
    return _parse_header(header_bytes)


def open_sealed(data: bytes, private_key: X25519PrivateKey) -> SealedFile:
    """Decrypt a sealed file. Raises DecryptionError if anything was altered."""
    if len(data) > MAX_PAYLOAD_SIZE + MAX_HEADER_SIZE + PREFIX_SIZE + NONCE_SIZE + TAG_SIZE:
        raise CryptoError("file troppo grande (massimo 1 GiB)")
    length = _parse_prefix(data[:PREFIX_SIZE])
    header_end = PREFIX_SIZE + length
    if len(data) < header_end + NONCE_SIZE + TAG_SIZE:
        raise CryptoError("file cifrato troncato")
    header = _parse_header(data[PREFIX_SIZE:header_end])
    if header["recipient"] != key_fingerprint(private_key.public_key()):
        raise CryptoError(f"il file è cifrato con un'altra chiave (id {header['recipient']})")
    ephemeral_public = b64decode(header["ephemeral"], "chiave effimera", KEY_SIZE)
    try:
        shared = private_key.exchange(load_public_key(ephemeral_public))
    except ValueError:
        raise DecryptionError("il file è stato alterato o è rovinato") from None
    key = _sealing_key(shared, ephemeral_public, public_key_bytes(private_key.public_key()))
    nonce = data[header_end : header_end + NONCE_SIZE]
    try:
        plaintext = AESGCM(key).decrypt(nonce, data[header_end + NONCE_SIZE :], data[:header_end])
    except InvalidTag:
        raise DecryptionError("il file è stato alterato o è rovinato") from None
    return SealedFile(header=header, plaintext=plaintext)


# * — key-encryption keys and wrapping —


@dataclass(frozen=True)
class ScryptParams:
    """scrypt cost: 128 * r * n bytes of memory (32 MiB with the defaults)."""

    n: int = 2**15
    r: int = 8
    p: int = 1

    def validate(self) -> "ScryptParams":
        for name in ("n", "r", "p"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise CryptoError(f"parametro scrypt '{name}' non valido")
        if self.n & (self.n - 1) or not MIN_SCRYPT_N <= self.n <= MAX_SCRYPT_N:
            raise CryptoError("parametro scrypt 'n' non valido")
        if not 1 <= self.r <= 32 or not 1 <= self.p <= 16 or 128 * self.r * self.n > MAX_SCRYPT_MEMORY:
            raise CryptoError("parametri scrypt fuori dai limiti")
        return self

    def to_dict(self) -> Dict[str, int]:
        return {"n": self.n, "r": self.r, "p": self.p}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScryptParams":
        return cls(n=data.get("n"), r=data.get("r"), p=data.get("p")).validate()


def normalize_passphrase(passphrase: str) -> bytes:
    """NFC form, so the same passphrase typed on Windows or Android gives the same bytes."""
    return unicodedata.normalize("NFC", passphrase).encode("utf-8")


def derive_passphrase_key(passphrase: str, salt: bytes, params: ScryptParams) -> bytes:
    params.validate()
    return Scrypt(salt=salt, length=KEY_SIZE, n=params.n, r=params.r, p=params.p).derive(normalize_passphrase(passphrase))


def derive_secret_key(secret: bytes, salt: bytes, info: bytes) -> bytes:
    """KEK from a high-entropy secret (recovery code, 32-byte secret)."""
    return HKDF(algorithm=hashes.SHA256(), length=KEY_SIZE, salt=salt, info=info).derive(secret)


def wrap_key(kek: bytes, key_material: bytes, aad: bytes) -> Dict[str, str]:
    nonce = os.urandom(NONCE_SIZE)
    return {"nonce": b64encode(nonce), "ciphertext": b64encode(AESGCM(kek).encrypt(nonce, key_material, aad))}


def unwrap_key(kek: bytes, wrapped: Dict[str, Any], aad: bytes) -> bytes:
    nonce = b64decode(wrapped.get("nonce"), "nonce", NONCE_SIZE)
    ciphertext = b64decode(wrapped.get("ciphertext"), "chiave protetta")
    try:
        return AESGCM(kek).decrypt(nonce, ciphertext, aad)
    except InvalidTag:
        raise DecryptionError("chiave sbagliata o dati alterati") from None


# * — recovery code —


def _symbols(number: int, count: int) -> str:
    return "".join(RECOVERY_ALPHABET[(number >> (5 * (count - 1 - index))) & 31] for index in range(count))


def _checksum(raw: bytes) -> str:
    digest = int.from_bytes(hashlib.sha256(RECOVERY_CHECK_DOMAIN + raw).digest()[:3], "big")
    return _symbols(digest >> (24 - RECOVERY_CHECK_BITS), RECOVERY_GROUP_SIZE)


def recovery_code_from_bytes(raw: bytes) -> str:
    """'XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-CCCC': 6 groups of data and 1 checksum group."""
    if len(raw) != RECOVERY_BYTES:
        raise ValueError(f"servono {RECOVERY_BYTES} byte")
    text = _symbols(int.from_bytes(raw, "big"), RECOVERY_GROUP_SIZE * RECOVERY_DATA_GROUPS) + _checksum(raw)
    return "-".join(text[index : index + RECOVERY_GROUP_SIZE] for index in range(0, len(text), RECOVERY_GROUP_SIZE))


def generate_recovery_code() -> str:
    return recovery_code_from_bytes(secrets.token_bytes(RECOVERY_BYTES))


def parse_recovery_code(text: str) -> bytes:
    """Return the 15 secret bytes; spaces, dashes, case and O/0, I/L/1 are forgiven."""
    cleaned = "".join(text.split()).replace("-", "").upper().translate(RECOVERY_LOOKALIKES)
    if len(cleaned) != RECOVERY_LENGTH:
        raise RecoveryCodeError(
            f"il codice di recupero ha {RECOVERY_LENGTH} caratteri (7 gruppi da 4): ne hai scritti {len(cleaned)}"
        )
    wrong = sorted({char for char in cleaned if char not in RECOVERY_ALPHABET})
    if wrong:
        raise RecoveryCodeError(f"il codice di recupero non contiene questi caratteri: {' '.join(wrong)}")
    data_length = RECOVERY_GROUP_SIZE * RECOVERY_DATA_GROUPS
    number = 0
    for char in cleaned[:data_length]:
        number = (number << 5) | RECOVERY_ALPHABET.index(char)
    raw = number.to_bytes(RECOVERY_BYTES, "big")
    if not secrets.compare_digest(_checksum(raw), cleaned[data_length:]):
        raise RecoveryCodeError("il codice di recupero contiene un errore di battitura: ricontrolla ogni gruppo")
    return raw


def recovery_code_last_group(code: str) -> str:
    return code.split("-")[-1]


def new_salt() -> bytes:
    return os.urandom(SALT_SIZE)
