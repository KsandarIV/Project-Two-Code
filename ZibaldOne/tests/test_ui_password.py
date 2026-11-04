"""The main password page of the first start (KAN-29)."""

import re
from pathlib import Path

import pytest

ft = pytest.importorskip("flet")

from test_ui_views import FakePage, button, click, folder, texts, walk  # noqa: E402,F401

from zibaldone.core.crypto import ScryptParams  # noqa: E402
from zibaldone.core.privacy import NOTICE_VERSION  # noqa: E402
from zibaldone.storage import database_key, keys, sealed_db  # noqa: E402
from zibaldone.storage.database import Store, database_path  # noqa: E402
from zibaldone.storage.settings import record_consent  # noqa: E402
from zibaldone.ui import cloud_model as cm  # noqa: E402
from zibaldone.ui import services  # noqa: E402
from zibaldone.ui.app import Shell  # noqa: E402
from zibaldone.ui.context import AppContext  # noqa: E402

CODE = re.compile(r"^[0-9A-Z]{4}(-[0-9A-Z]{4}){6}$")
OLD = "cavallo batteria graffetta"


@pytest.fixture(autouse=True)
def fast_scrypt(monkeypatch):
    monkeypatch.setattr(keys, "DEFAULT_SCRYPT_PARAMS", ScryptParams(n=2**10))


@pytest.fixture
def consented(folder: Path, password_step) -> Path:  # noqa: F811 (fixture from test_ui_views)
    record_consent(folder, True, NOTICE_VERSION)
    return folder


def started(where: Path):
    page = FakePage()
    shell = Shell(page, where)
    shell.start("/")
    assert shell.current.screen == "password"
    return shell, page


def shown_password(control) -> str:
    return next(item.value for item in walk(control) if isinstance(item, ft.Text) and getattr(item, "font_family", None) == "monospace")


def dialog_secrets(dialog):
    values = [item.value for item in walk(dialog) if isinstance(item, ft.Text) and getattr(item, "font_family", None) == "monospace"]
    password, code = values
    assert CODE.match(code)
    return password, code


def group_fields(dialog):
    return {int(re.search(r"\d+", item.label).group()): item for item in walk(dialog) if isinstance(item, ft.TextField) and (item.label or "").startswith("Gruppo ")}


def answer(dialog, code: str, right: bool = True) -> None:
    groups = code.split("-")
    for number, field in group_fields(dialog).items():
        field.value = groups[number - 1].lower() if right else "ZZZZ"
    click(button(dialog, "Ho scritto tutto"))


def test_the_first_start_asks_for_the_password_and_saves_nothing_before_the_code(consented: Path) -> None:
    shell, page = started(consented)
    proposed = shown_password(shell.body.content)
    assert len(proposed) == 20
    click(button(shell.body.content, "Usa questa password"))
    dialog = page.dialogs[-1]
    password, code = dialog_secrets(dialog)
    assert password == proposed and len(group_fields(dialog)) == 2
    assert not keys.is_configured(consented)  # nothing saved before the confirmation
    answer(dialog, code, right=False)
    assert not keys.is_configured(consented) and "Non corrisponde" in " ".join(texts(dialog))
    answer(dialog, code)
    assert keys.uses_generated_password(consented)
    keys.unlock_with_passphrase(consented, password)
    keys.unlock_with_recovery_code(consented, code)
    assert shell.current.screen == "cartella"
    assert not services.password_pending(consented)
    assert sealed_db.is_sealed(consented) and not database_path(consented).exists()  # KAN-107: encrypted from the start


def test_three_wrong_answers_save_nothing(consented: Path) -> None:
    shell, page = started(consented)
    click(button(shell.body.content, "Usa questa password"))
    dialog = page.dialogs[-1]
    _, code = dialog_secrets(dialog)
    for _ in range(cm.CONFIRM_ATTEMPTS):
        answer(dialog, code, right=False)
    assert not keys.is_configured(consented) and shell.current.screen == "password"
    assert "Non ho salvato nulla" in shell.ctx.toasts[-1]


def test_rules_regenerate_and_refuse_a_weak_password(consented: Path) -> None:
    shell, _ = started(consented)
    first = shown_password(shell.body.content)
    click(button(shell.body.content, "Rigenera"))
    assert shown_password(shell.body.content) != first
    boxes = {item.label: item for item in walk(shell.body.content) if isinstance(item, ft.Checkbox)}
    boxes["Simboli"].value = False
    boxes["Simboli"].on_change(None)
    assert any("simboli ma li hai esclusi" in text for text in texts(shell.body.content))  # the minimum of symbols still asks for 2
    minimum = next(item for item in walk(shell.body.content) if isinstance(item, ft.TextField) and item.label == "Simboli, almeno")
    minimum.value = "0"
    minimum.on_change(None)
    made = shown_password(shell.body.content)
    assert not set(made) & set("!#$%&*+-=?@^_~")


def test_the_recovery_sheet_is_offered_and_holds_both_secrets(consented: Path, monkeypatch) -> None:
    sheets = []
    monkeypatch.setattr(AppContext, "save_file", lambda self, name, data, on_saved=None: (sheets.append((name, data.decode("utf-8"))), on_saved and on_saved("/dove")))
    shell, page = started(consented)
    click(button(shell.body.content, "Usa questa password"))
    dialog = page.dialogs[-1]
    password, code = dialog_secrets(dialog)
    click(button(dialog, "Salva foglio di recupero"))
    name, sheet = sheets[0]
    assert name == cm.RECOVERY_SHEET_NAME and password in sheet and code in sheet
    assert any("Foglio salvato" in text for text in texts(dialog))


def test_keys_from_before_move_to_the_password_and_old_snapshots_still_open(consented: Path) -> None:
    before = keys.setup_keys(consented, OLD)
    assert services.password_pending(consented)
    shell, page = started(consented)
    assert any("vecchia passphrase" in text for text in texts(shell.body.content))
    field = next(item for item in walk(shell.body.content) if isinstance(item, ft.TextField))
    field.value = "non è questa"
    click(button(shell.body.content, "Apri le chiavi"))
    assert any("Non è la vecchia passphrase" in text for text in texts(shell.body.content))
    field.value = OLD
    click(button(shell.body.content, "Apri le chiavi"))
    click(button(shell.body.content, "Usa questa password"))
    dialog = page.dialogs[-1]
    password, code = dialog_secrets(dialog)
    assert keys.unlock_with_passphrase(consented, OLD)  # still the old one until the confirmation
    answer(dialog, code)
    assert keys.uses_generated_password(consented) and keys.key_id(consented) == before.key_id
    keys.unlock_with_passphrase(consented, password)
    assert shell.current.screen == "cartella"


def test_both_old_secrets_lost_start_over_with_new_keys(consented: Path) -> None:
    before = keys.setup_keys(consented, OLD)
    shell, page = started(consented)
    click(button(shell.body.content, "Non ricordo né la passphrase né il codice"))
    click(button(page.dialogs[-1], "Ricomincio con chiavi nuove"))
    assert not keys.is_configured(consented) and list(consented.glob("keys-ritirate-*.json"))
    click(button(shell.body.content, "Usa questa password"))
    dialog = page.dialogs[-1]
    _, code = dialog_secrets(dialog)
    answer(dialog, code)
    assert keys.key_id(consented) != before.key_id and keys.uses_generated_password(consented)


# * — KAN-107: the encrypted database —


def test_a_plain_database_is_encrypted_at_the_next_start(consented: Path) -> None:
    Store.open(consented).close()  # the database exists, plain
    keys.save_new_keys(consented, keys.create_keys("x" * 20, generated=True))
    assert database_path(consented).exists()
    page = FakePage()
    shell = Shell(page, consented)
    shell.start("/")
    assert sealed_db.is_sealed(consented) and not database_path(consented).exists()
    assert shell.current.screen == "cartella"


def test_without_the_key_the_app_asks_the_password(consented: Path) -> None:
    made = "y" * 20
    keys.save_new_keys(consented, keys.create_keys(made, generated=True))
    database_key.seal_if_ready(consented)
    sealed_db.forget()  # a new start, and no keystore here
    page = FakePage()
    shell = Shell(page, consented)
    shell.start("/")
    assert shell.current.screen == "sblocca"
    field = next(item for item in walk(shell.body.content) if isinstance(item, ft.TextField))
    field.value = "non è lei"
    click(button(shell.body.content, "Apri"))
    assert any("password sbagliata" in text.lower() for text in texts(shell.body.content))
    field.value = made
    click(button(shell.body.content, "Apri"))
    assert sealed_db.is_unlocked(consented) and shell.current.screen == "cartella"


# * — KAN-108: fingerprint or face, and a new password from this device —


def sealed_with_password(where: Path):
    made = "w" * 20
    new = keys.create_keys(made, generated=True)
    keys.save_new_keys(where, new)
    key = database_key.seal_if_ready(where)
    sealed_db.forget()
    return made, new.recovery_code, key


def test_fingerprint_then_the_keystore_open_the_diary(consented: Path, monkeypatch) -> None:
    from zibaldone.ui import biometrics, keystore

    _, _, key = sealed_with_password(consented)
    asked = []

    async def confirm(ctx, reason=biometrics.REASON):
        asked.append(reason)
        return True

    async def read(ctx, what=keystore.DATABASE_KEY):
        return database_key.stored_form(key) if what == keystore.DATABASE_KEY else None

    monkeypatch.setattr(biometrics, "confirm", confirm)
    monkeypatch.setattr(keystore, "read", read)
    shell = Shell(FakePage(), consented)
    shell.start("/")
    assert asked == ["Apri il tuo diario"] and sealed_db.is_unlocked(consented) and shell.current.screen == "cartella"


def test_a_refused_fingerprint_leaves_the_password_and_a_second_try(consented: Path, monkeypatch) -> None:
    from zibaldone.ui import biometrics, keystore

    made, _, key = sealed_with_password(consented)
    answers = [False, True]

    async def confirm(ctx, reason=biometrics.REASON):
        return answers.pop(0)

    async def read(ctx, what=keystore.DATABASE_KEY):
        return database_key.stored_form(key)

    monkeypatch.setattr(biometrics, "confirm", confirm)
    monkeypatch.setattr(keystore, "read", read)
    shell = Shell(FakePage(), consented)
    shell.start("/")
    assert shell.current.screen == "sblocca" and not sealed_db.is_unlocked(consented)  # the keystore stays shut
    click(button(shell.body.content, "Usa impronta o volto"))
    assert sealed_db.is_unlocked(consented) and shell.current.screen == "cartella"


def test_a_new_password_from_the_settings_keeps_the_recovery_code(consented: Path) -> None:
    from zibaldone.ui.views import encryption

    made, code, _ = sealed_with_password(consented)
    page = FakePage()
    ctx = AppContext(consented, page)
    encryption.change_password(ctx)
    ask = page.dialogs[-1]
    next(item for item in walk(ask) if isinstance(item, ft.TextField)).value = made
    click(button(ask, "Avanti"))
    new_dialog = page.dialogs[-1]
    new_password = shown_password(new_dialog)
    field = next(item for item in walk(new_dialog) if isinstance(item, ft.TextField) and item.label == "Per conferma, gli ultimi 4 caratteri")
    field.value = "nope"
    click(button(new_dialog, "Usa questa password"))
    keys.unlock_with_passphrase(consented, made)  # unchanged until the confirmation
    field.value = new_password[-4:]
    click(button(new_dialog, "Usa questa password"))
    keys.unlock_with_passphrase(consented, new_password)
    with pytest.raises(keys.WrongSecretError):
        keys.unlock_with_passphrase(consented, made)
    keys.unlock_with_recovery_code(consented, code)
    assert "Password principale cambiata" in ctx.toasts[-1]
