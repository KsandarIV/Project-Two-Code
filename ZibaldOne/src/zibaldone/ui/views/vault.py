"""Opening the secrets in the app (0.2.3): the vault, the PIN or passphrase dialog, the PIN in Mnemosyne.

The vault lives in `ctx.memory` while the app is open and closes by itself
after a few minutes without use (`core.secrets.Vault`). Writing a secret needs
nothing: only reading asks the PIN (protected level) or the passphrase.
"""

from typing import Any, Callable, List

import flet as ft

from zibaldone.core import secrets
from zibaldone.ui import cloud_model as cm
from zibaldone.ui import services
from zibaldone.ui import theme as T
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext

VAULT_KEY = "vault"


def vault_of(ctx: AppContext) -> secrets.Vault:
    return ctx.memory.setdefault(VAULT_KEY, secrets.Vault())


def _keys() -> Any:
    from zibaldone.storage import keys

    return keys


def _secret_input(label: str, pin: bool) -> ft.TextField:
    extra = {"keyboard_type": ft.KeyboardType.NUMBER, "max_length": 12} if pin else {}
    return W.text_input("", label=label, password=True, can_reveal_password=True, autofocus=True, **extra)


def _uses_pin(folder: Any, values: List[str]) -> bool:
    try:
        only_protected = bool(values) and all(secrets.value_level(value) == secrets.PROTECTED for value in values)
    except secrets.SecretsError:
        return False
    return only_protected and _keys().has_pin(folder)


def unlock_secrets(ctx: AppContext, values: List[str], on_open: Callable[[], Any], use_pin: Any = None) -> None:
    """Ask the PIN when it opens all of `values`, the passphrase otherwise; then `on_open()`."""
    if not services.encryption_on(ctx.folder):
        ctx.toast("Senza la chiave dei backup i segreti non si aprono: attiva la cifratura in Impostazioni · Mnemosyne.", error=True)
        return
    keys = _keys()
    pin = _uses_pin(ctx.folder, values) if use_pin is None else bool(use_pin)
    field = _secret_input("PIN" if pin else "Passphrase dei backup", pin)
    error = W.error_text()
    go_on = W.primary_button("Apri", None, icon="LOCK_OPEN")
    folder = ctx.folder

    def proceed(_: Any = None) -> None:
        typed = field.value or ""
        if not typed:
            return
        go_on.disabled = True
        ctx.update(go_on)

        def work() -> List[Any]:
            return [keys.unlock_with_pin(folder, typed)] if pin else keys.unlock_secrets_with_passphrase(folder, typed)

        def opened(private_keys: List[Any]) -> None:
            vault_of(ctx).unlock(private_keys, ctx.now())
            ctx.close_dialog()
            on_open()

        def failed(problem: Exception) -> None:
            go_on.disabled = False
            field.value = ""
            error.value, error.visible = cm.error_text(problem), True

        ctx.run_blocking(work, opened, failed)

    def other_way(_: Any) -> None:
        ctx.close_dialog()
        unlock_secrets(ctx, values, on_open, use_pin=False)

    go_on.on_click = proceed
    field.on_submit = proceed
    intro = (
        "Il PIN apre i segreti protetti di questo dispositivo."
        if pin
        else "La passphrase dei backup apre tutti i segreti, anche quelli di livello massimo."
    )
    actions: List[ft.Control] = [W.text_button("Annulla", ctx.close_dialog, color=T.TEXT)]
    if pin:
        actions.append(W.text_button("Usa la passphrase", other_way, color=T.TEXT))
    actions.append(go_on)
    dialog = ft.AlertDialog(
        modal=True,
        title="Apri i segreti",
        content=ft.Container(
            ft.Column(
                [W.body(intro, size=14), W.wide(field), W.caption(f"Si richiudono da soli dopo {secrets.VAULT_MINUTES} minuti senza usarli."), error],
                spacing=12,
                tight=True,
            ),
            width=420,
        ),
        actions=actions,
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.show_dialog(dialog)


def choose_pin(ctx: AppContext, on_done: Callable[[], Any]) -> None:
    """The passphrase, then the new PIN twice; the PIN opens only the protected level."""
    keys = _keys()
    passphrase = _secret_input("Passphrase dei backup", pin=False)
    first = W.text_input("", label=f"Nuovo PIN ({keys.PIN_MIN}-{keys.PIN_MAX} cifre)", password=True, keyboard_type=ft.KeyboardType.NUMBER, max_length=keys.PIN_MAX)
    second = W.text_input("", label="Ripetilo", password=True, keyboard_type=ft.KeyboardType.NUMBER, max_length=keys.PIN_MAX)
    error = W.error_text()
    go_on = W.primary_button("Scegli il PIN", None, icon="PIN")
    folder = ctx.folder

    def show(message: str) -> None:
        error.value, error.visible = message, True
        ctx.update(error)

    def proceed(_: Any = None) -> None:
        pin = first.value or ""
        try:
            keys.check_pin(pin)
        except keys.KeysError as problem:
            show(cm.error_text(problem))
            return
        if pin != (second.value or ""):
            show("I due PIN non sono uguali.")
            return
        go_on.disabled = True
        ctx.update(go_on)
        typed = passphrase.value or ""

        def work() -> None:
            keys.set_pin(folder, keys.unlock_with_passphrase(folder, typed), pin)

        def done(_: Any) -> None:
            ctx.close_dialog()
            ctx.toast(f"PIN scelto: apre i segreti protetti. Dopo {keys.PIN_ATTEMPTS} errori di fila si toglie da solo.")
            on_done()

        def failed(problem: Exception) -> None:
            go_on.disabled = False
            error.value, error.visible = cm.error_text(problem), True

        ctx.run_blocking(work, done, failed)

    go_on.on_click = proceed
    second.on_submit = proceed
    dialog = ft.AlertDialog(
        modal=True,
        scrollable=True,
        title="Scegli il PIN dei segreti",
        content=ft.Container(
            ft.Column(
                [
                    W.body("Il PIN apre i segreti protetti (il diario segreto, gli indirizzi), mai quelli di livello massimo né i backup.", size=14),
                    W.wide(passphrase),
                    W.wide(first),
                    W.wide(second),
                    error,
                ],
                spacing=12,
                tight=True,
            ),
            width=440,
        ),
        actions=[W.text_button("Annulla", ctx.close_dialog, color=T.TEXT), go_on],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.show_dialog(dialog)


def secrets_panel(ctx: AppContext) -> ft.Control:
    """Arcana in Mnemosyne: the PIN, and opening or closing the secrets."""
    keys = _keys()
    folder = ctx.folder
    vault = vault_of(ctx)
    has_pin = keys.has_pin(folder)
    ready = secrets.PROTECTED in keys.secret_public_keys(folder)
    lines = [
        W.body("Segreti · Arcana", size=15, weight=ft.FontWeight.W_600),
        W.caption("I blocchi segreti sono cifrati con la tua chiave e restano fuori da ricerca, esportazioni e IA."),
        W.caption("PIN scelto: apre i segreti protetti." if has_pin else "Nessun PIN: i segreti si aprono con la passphrase."),
    ]
    if not ready:
        lines.append(W.caption("Aprili una volta con la passphrase: poi i segreti protetti si scrivono senza chiedere nulla.", color=T.ACCENT_2))

    def toggle_pin(_: Any) -> None:
        if has_pin:
            keys.remove_pin(folder)
            ctx.toast("PIN tolto: i segreti si aprono con la passphrase.")
            ctx.refresh()
        else:
            choose_pin(ctx, ctx.refresh)

    def opened() -> None:
        ctx.toast("Segreti aperti.")
        ctx.refresh()

    def close(_: Any) -> None:
        vault.lock()
        ctx.toast("Segreti chiusi.")
        ctx.refresh()

    buttons: List[ft.Control] = [W.secondary_button("Togli il PIN" if has_pin else "Scegli il PIN", toggle_pin, icon="PIN")]
    if vault.is_open(ctx.now()):
        buttons.append(W.primary_button("Chiudi i segreti", close, icon="LOCK"))
    else:
        buttons.append(W.primary_button("Apri i segreti", lambda _: unlock_secrets(ctx, [], opened, use_pin=False), icon="LOCK_OPEN"))
    return W.panel(
        ft.Column(
            [
                ft.Row(
                    [ft.Icon(ft.Icons.KEY, color=T.ACCENT, size=22), ft.Column(lines, spacing=4, expand=True)],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                ft.Row(buttons, alignment=ft.MainAxisAlignment.END, wrap=True, spacing=8),
            ],
            spacing=10,
        ),
        padding=14,
    )
