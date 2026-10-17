import base64
import io
import json

import pytest

from zibaldone.core import crypto
from zibaldone.core.crypto import CryptoError, DecryptionError, RecoveryCodeError, ScryptParams
from zibaldone.storage import keys
from zibaldone.storage.keys import KeysError, WrongSecretError

FAST_SCRYPT = ScryptParams(n=2**10)
PASSPHRASE = "cavallo batteria graffetta"


@pytest.fixture(autouse=True)
def fast_scrypt(monkeypatch):
    """scrypt with n=2**10 keeps the tests fast; the real default stays 2**15."""
    monkeypatch.setattr(keys, "DEFAULT_SCRYPT_PARAMS", FAST_SCRYPT)


@pytest.fixture
def folder(tmp_path):
    return tmp_path / "data"


def flip(data: bytes, index: int) -> bytes:
    return data[:index] + bytes([data[index] ^ 0x01]) + data[index + 1 :]


# * — sealing —


def test_seal_round_trip_and_public_header() -> None:
    private_key = crypto.generate_private_key()
    sealed = crypto.seal(b"diario segreto", private_key.public_key(), {"snapshot": {"id": "x"}})
    assert crypto.is_sealed(sealed) and b"diario" not in sealed
    header = crypto.read_sealed_header(io.BytesIO(sealed))
    assert header["snapshot"] == {"id": "x"}
    assert header["recipient"] == crypto.key_fingerprint(private_key.public_key())
    opened = crypto.open_sealed(sealed, private_key)
    assert opened.plaintext == b"diario segreto" and opened.header == header


def test_each_seal_uses_a_fresh_ephemeral_key() -> None:
    public_key = crypto.generate_private_key().public_key()
    first, second = crypto.seal(b"same", public_key), crypto.seal(b"same", public_key)
    assert first != second


def test_any_flipped_byte_is_detected() -> None:
    private_key = crypto.generate_private_key()
    sealed = crypto.seal(b"x" * 100, private_key.public_key(), {"note": "abc"})
    header_end = crypto.PREFIX_SIZE + int.from_bytes(sealed[len(crypto.MAGIC) + 1 : crypto.PREFIX_SIZE], "big")
    positions = [0, len(crypto.MAGIC), crypto.PREFIX_SIZE + 3, header_end - 3, header_end + 1, header_end + 20, len(sealed) - 1]
    for index in positions:
        with pytest.raises(CryptoError):
            crypto.open_sealed(flip(sealed, index), private_key)


def test_authenticated_header_cannot_be_edited() -> None:
    private_key = crypto.generate_private_key()
    sealed = crypto.seal(b"payload", private_key.public_key(), {"reason": "auto"})
    edited = sealed.replace(b'"reason":"auto"', b'"reason":"mano"')
    assert edited != sealed
    assert crypto.read_sealed_header(io.BytesIO(edited))["reason"] == "mano"
    with pytest.raises(DecryptionError, match="alterato"):
        crypto.open_sealed(edited, private_key)


def test_wrong_key_truncation_and_newer_format() -> None:
    private_key = crypto.generate_private_key()
    sealed = crypto.seal(b"payload", private_key.public_key())
    with pytest.raises(CryptoError, match="un'altra chiave"):
        crypto.open_sealed(sealed, crypto.generate_private_key())
    with pytest.raises(CryptoError, match="troncato"):
        crypto.open_sealed(sealed[: crypto.PREFIX_SIZE + 10], private_key)
    newer = sealed[: len(crypto.MAGIC)] + bytes([crypto.FORMAT_VERSION + 1]) + sealed[len(crypto.MAGIC) + 1 :]
    with pytest.raises(CryptoError, match="più recente"):
        crypto.open_sealed(newer, private_key)
    with pytest.raises(CryptoError, match="non è un file cifrato"):
        crypto.open_sealed(b"PK\x03\x04" + sealed, private_key)


def test_payload_size_limit_and_reserved_fields(monkeypatch) -> None:
    public_key = crypto.generate_private_key().public_key()
    monkeypatch.setattr(crypto, "MAX_PAYLOAD_SIZE", 10)
    with pytest.raises(CryptoError, match="troppo grande"):
        crypto.seal(b"x" * 11, public_key)
    with pytest.raises(ValueError):
        crypto.seal(b"x", public_key, {"recipient": "someone"})


# * — recovery code —


def test_recovery_code_format_and_round_trip() -> None:
    raw = bytes(range(15))
    code = crypto.recovery_code_from_bytes(raw)
    groups = code.split("-")
    assert len(groups) == 7 and all(len(group) == 4 for group in groups)
    assert set(code.replace("-", "")) <= set(crypto.RECOVERY_ALPHABET)
    assert crypto.parse_recovery_code(code) == raw
    assert crypto.parse_recovery_code(" " + code.lower().replace("-", " ") + " ") == raw
    assert crypto.parse_recovery_code(crypto.generate_recovery_code()) != raw


def test_recovery_code_lookalike_letters_are_forgiven() -> None:
    raw = bytes(15)
    code = crypto.recovery_code_from_bytes(raw)  # all zeros: '0000-…'
    assert crypto.parse_recovery_code(code.replace("0", "O")) == raw


def test_recovery_code_typos_are_detected() -> None:
    code = crypto.recovery_code_from_bytes(bytes(range(100, 115)))
    chars = list(code.replace("-", ""))
    for index in (0, 7, 13, 23, 26):  # data groups and checksum group
        changed = chars.copy()
        changed[index] = "Z" if changed[index] != "Z" else "Y"
        with pytest.raises(RecoveryCodeError, match="errore di battitura"):
            crypto.parse_recovery_code("".join(changed))
    swapped = chars.copy()
    first = next(i for i in range(len(chars) - 1) if chars[i] != chars[i + 1])
    swapped[first], swapped[first + 1] = swapped[first + 1], swapped[first]
    with pytest.raises(RecoveryCodeError):
        crypto.parse_recovery_code("".join(swapped))
    with pytest.raises(RecoveryCodeError, match="28 caratteri"):
        crypto.parse_recovery_code(code[:-1])
    with pytest.raises(RecoveryCodeError, match="non contiene"):
        crypto.parse_recovery_code("U" + code[1:])


# * — scrypt parameters —


def test_scrypt_defaults_are_strong_and_bounds_are_checked() -> None:
    assert ScryptParams() == ScryptParams(n=2**15, r=8, p=1)
    for bad in (ScryptParams(n=1000), ScryptParams(n=2**8), ScryptParams(n=2**21), ScryptParams(r=0), ScryptParams(p=True)):
        with pytest.raises(CryptoError):
            bad.validate()


# * — keys.json —


def test_setup_unlock_and_nothing_secret_on_disk(folder) -> None:
    assert not keys.is_configured(folder)
    new_keys = keys.setup_keys(folder, PASSPHRASE)
    assert keys.is_configured(folder)
    assert new_keys.recovery_code not in repr(new_keys)
    text = keys.keys_path(folder).read_text(encoding="utf-8")
    raw_private = crypto.private_key_bytes(new_keys.private_key)
    for secret in (PASSPHRASE, new_keys.recovery_code, new_keys.recovery_code.replace("-", ""), base64.b64encode(raw_private).decode(), raw_private.hex()):
        assert secret not in text
    document = json.loads(text)
    assert document["key_id"] == new_keys.key_id
    assert document["wraps"]["passphrase"]["kdf"] == {"name": "scrypt", "n": 2**10, "r": 8, "p": 1, "salt": document["wraps"]["passphrase"]["kdf"]["salt"]}
    unlocked = keys.unlock_with_passphrase(folder, PASSPHRASE)
    assert crypto.private_key_bytes(unlocked) == raw_private
    assert crypto.key_fingerprint(keys.load_public_key(folder)) == new_keys.key_id
    assert crypto.private_key_bytes(keys.unlock_with_recovery_code(folder, new_keys.recovery_code.lower())) == raw_private


def test_default_scrypt_cost_is_used_when_not_lowered(folder, monkeypatch) -> None:
    monkeypatch.setattr(keys, "DEFAULT_SCRYPT_PARAMS", ScryptParams())
    keys.setup_keys(folder, PASSPHRASE)
    kdf = json.loads(keys.keys_path(folder).read_text(encoding="utf-8"))["wraps"]["passphrase"]["kdf"]
    assert (kdf["n"], kdf["r"], kdf["p"]) == (2**15, 8, 1)
    assert len(base64.b64decode(kdf["salt"])) == 16


def test_wrong_passphrase_and_wrong_recovery_code(folder) -> None:
    keys.setup_keys(folder, PASSPHRASE)
    with pytest.raises(WrongSecretError, match="passphrase sbagliata"):
        keys.unlock_with_passphrase(folder, PASSPHRASE + "!")
    other_code = crypto.recovery_code_from_bytes(bytes(15))
    with pytest.raises(WrongSecretError, match="codice di recupero sbagliato"):
        keys.unlock_with_recovery_code(folder, other_code)
    with pytest.raises(RecoveryCodeError):
        keys.unlock_with_recovery_code(folder, "ABCD-EFGH")


def test_setup_refuses_weak_passphrase_and_second_setup(folder) -> None:
    with pytest.raises(KeysError, match="almeno 10 caratteri"):
        keys.setup_keys(folder, "corta")
    assert not keys.is_configured(folder)
    keys.setup_keys(folder, PASSPHRASE)
    with pytest.raises(KeysError, match="già attiva"):
        keys.setup_keys(folder, PASSPHRASE)


def test_create_keys_saves_nothing_until_asked(folder) -> None:
    new_keys = keys.create_keys(PASSPHRASE)
    assert not folder.exists()
    keys.save_new_keys(folder, new_keys)
    assert keys.key_id(folder) == new_keys.key_id


def test_change_and_reset_passphrase(folder) -> None:
    new_keys = keys.setup_keys(folder, PASSPHRASE)
    keys.change_passphrase(folder, PASSPHRASE, "un'altra passphrase")
    with pytest.raises(WrongSecretError):
        keys.unlock_with_passphrase(folder, PASSPHRASE)
    with pytest.raises(WrongSecretError):
        keys.change_passphrase(folder, PASSPHRASE, "non dovrebbe funzionare")
    keys.unlock_with_passphrase(folder, "un'altra passphrase")
    keys.reset_passphrase(folder, new_keys.recovery_code, "passphrase ritrovata")
    unlocked = keys.unlock_with_passphrase(folder, "passphrase ritrovata")
    assert crypto.key_fingerprint(unlocked.public_key()) == new_keys.key_id
    assert keys.key_id(folder) == new_keys.key_id  # same key: old snapshots still open


def test_passphrase_unicode_normalization(folder) -> None:
    composed, decomposed = "perché la notte è lunga", "perché la notte è lunga"
    keys.setup_keys(folder, composed)
    keys.unlock_with_passphrase(folder, decomposed)


def test_secret_wraps(folder) -> None:
    new_keys = keys.setup_keys(folder, PASSPHRASE)
    secret = bytes(range(32))
    keys.add_secret_wrap(folder, new_keys.private_key, "google", secret)
    assert keys.secret_names(folder) == ["google"]
    assert crypto.key_fingerprint(keys.unlock_with_secret(folder, "google", secret).public_key()) == new_keys.key_id
    with pytest.raises(WrongSecretError, match="non è quello giusto"):
        keys.unlock_with_secret(folder, "google", bytes(32))
    with pytest.raises(KeysError, match="32 byte"):
        keys.unlock_with_secret(folder, "google", b"short")
    with pytest.raises(KeysError, match="non valido"):
        keys.add_secret_wrap(folder, new_keys.private_key, "Google Drive", secret)
    with pytest.raises(KeysError, match="non è quella dei backup"):
        keys.add_secret_wrap(folder, crypto.generate_private_key(), "altro", secret)
    assert keys.remove_secret_wrap(folder, "google") is True
    assert keys.remove_secret_wrap(folder, "google") is False
    with pytest.raises(KeysError, match="non esiste"):
        keys.unlock_with_secret(folder, "google", secret)
    keys.unlock_with_passphrase(folder, PASSPHRASE)


def test_wrap_cannot_be_moved_to_another_slot(folder) -> None:
    new_keys = keys.setup_keys(folder, PASSPHRASE)
    secret = bytes(range(32))
    keys.add_secret_wrap(folder, new_keys.private_key, "uno", secret)
    document = json.loads(keys.keys_path(folder).read_text(encoding="utf-8"))
    document["wraps"]["secret:due"] = document["wraps"]["secret:uno"]
    keys.keys_path(folder).write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(WrongSecretError):
        keys.unlock_with_secret(folder, "due", secret)


def test_broken_or_tampered_keys_file(folder) -> None:
    with pytest.raises(KeysError, match="non è ancora attiva"):
        keys.load_public_key(folder)
    keys.setup_keys(folder, PASSPHRASE)
    path = keys.keys_path(folder)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["public_key"] = crypto.b64encode(crypto.public_key_bytes(crypto.generate_private_key().public_key()))
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(KeysError, match="non corrisponde"):
        keys.load_public_key(folder)
    path.write_text("{ rotto", encoding="utf-8")
    with pytest.raises(KeysError, match="non riesco a leggere"):
        keys.unlock_with_passphrase(folder, PASSPHRASE)
