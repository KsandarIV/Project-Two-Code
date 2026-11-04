import json
import string

import pytest

from zibaldone.core import crypto, password
from zibaldone.core.crypto import ScryptParams
from zibaldone.core.password import PasswordRules
from zibaldone.storage import keys
from zibaldone.storage.keys import KeysError, WrongSecretError

FAST_SCRYPT = ScryptParams(n=2**10)
OLD = "cavallo batteria graffetta"


@pytest.fixture(autouse=True)
def fast_scrypt(monkeypatch):
    monkeypatch.setattr(keys, "DEFAULT_SCRYPT_PARAMS", FAST_SCRYPT)


@pytest.fixture
def folder(tmp_path):
    return tmp_path / "data"


# * — the generator —


def test_default_password_follows_the_rules() -> None:
    for _ in range(50):
        made = password.generate()
        assert len(made) == 20
        assert any(c in password.LOWER for c in made) and any(c in password.UPPER for c in made)
        assert sum(c in password.DIGITS for c in made) >= 2 and sum(c in password.SYMBOLS for c in made) >= 2
        assert not set(made) & set("lIO01")  # no look-alikes
    assert len({password.generate() for _ in range(20)}) == 20


def test_kinds_left_out_never_appear() -> None:
    rules = PasswordRules(length=24, symbols=False, upper=False, min_symbols=0, min_digits=5)
    for _ in range(30):
        made = password.generate(rules)
        assert set(made) <= set(password.LOWER + password.DIGITS)
        assert sum(c in password.DIGITS for c in made) >= 5


@pytest.mark.parametrize(
    "rules, reason",
    [
        (PasswordRules(lower=False, upper=False, digits=False, symbols=False, min_digits=0, min_symbols=0), "almeno un tipo"),
        (PasswordRules(length=15), "da 16 a 64"),
        (PasswordRules(length=65), "da 16 a 64"),
        (PasswordRules(min_digits=-1), "negativi"),
        (PasswordRules(digits=False), "numeri"),
        (PasswordRules(symbols=False), "simboli"),
        (PasswordRules(length=16, min_digits=8, min_symbols=8), "non entrano"),
        (PasswordRules(length=20, lower=False, upper=False, symbols=False, min_symbols=0), "troppo debole"),
    ],
)
def test_weak_or_impossible_rules_are_refused(rules, reason) -> None:
    assert reason in rules.problem()
    with pytest.raises(ValueError, match=reason):
        password.generate(rules)


def test_strength_is_counted_on_the_alphabet() -> None:
    assert PasswordRules().bits() > 120
    lower_and_digits = dict(upper=False, symbols=False, min_symbols=0)  # 33 characters, about 5 bits each
    assert "troppo debole" in PasswordRules(length=17, **lower_and_digits).problem()
    assert PasswordRules(length=18, **lower_and_digits).problem() == ""
    assert set(PasswordRules().alphabet()) <= set(string.printable)


# * — keys moved to the main password —


def test_new_keys_made_with_a_generated_password_say_so(folder) -> None:
    made = password.generate()
    keys.save_new_keys(folder, keys.create_keys(made, generated=True))
    assert keys.uses_generated_password(folder)
    assert made not in keys.keys_path(folder).read_text(encoding="utf-8")
    keys.unlock_with_passphrase(folder, made)


def test_renew_gives_a_new_password_and_code_on_the_same_key(folder) -> None:
    first = keys.setup_keys(folder, OLD)
    assert not keys.uses_generated_password(folder)
    old_recovery_wrap = keys.recovery_wrap(folder)
    private = keys.unlock_with_passphrase(folder, OLD)
    made = password.generate()
    code = keys.renew(folder, private, made)
    assert keys.uses_generated_password(folder)
    assert keys.key_id(folder) == first.key_id  # every snapshot made before still opens
    assert code != first.recovery_code
    with pytest.raises(WrongSecretError):
        keys.unlock_with_passphrase(folder, OLD)
    with pytest.raises(WrongSecretError):
        keys.unlock_with_recovery_code(folder, first.recovery_code)
    keys.unlock_with_passphrase(folder, made)
    keys.unlock_with_recovery_code(folder, code)
    keys.unlock_recovery_wrap(old_recovery_wrap, first.key_id, first.recovery_code)  # old snapshots keep their own wrap
    slots = keys.opaque_slots(folder)
    assert crypto.key_fingerprint(keys.unlock_opaque(slots, passphrase=made).public_key()) == first.key_id
    assert crypto.key_fingerprint(keys.unlock_opaque(slots, recovery_code=code).public_key()) == first.key_id


def test_renew_adds_opaque_slots_to_old_keys_and_refuses_another_key(folder) -> None:
    keys.setup_keys(folder, OLD)
    document = json.loads(keys.keys_path(folder).read_text(encoding="utf-8"))
    document.pop(keys.OPAQUE_FIELD)
    keys.keys_path(folder).write_text(json.dumps(document), encoding="utf-8")
    assert keys.opaque_slots(folder) is None
    keys.renew(folder, keys.unlock_with_passphrase(folder, OLD), password.generate())
    assert keys.opaque_slots(folder) is not None
    with pytest.raises(KeysError, match="non è quella dei backup"):
        keys.renew(folder, crypto.generate_private_key(), password.generate())


def test_retire_puts_the_keys_aside_for_new_ones(folder) -> None:
    first = keys.setup_keys(folder, OLD)
    aside = keys.retire(folder)
    assert not keys.is_configured(folder) and aside.exists() and aside.parent == folder
    second = keys.setup_keys(folder, password.generate())
    assert second.key_id != first.key_id
