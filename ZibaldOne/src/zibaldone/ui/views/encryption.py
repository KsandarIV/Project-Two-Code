"""Turning on the encryption of Mnemosyne's snapshots, like `zbone backup setup`.

Two dialogs: the passphrase (twice), then the recovery code shown once and
confirmed by copying its last group. Nothing is saved before that
confirmation. Afterwards the old plain snapshots are sealed, and when copies
go to the cloud the Google recovery is offered and the first copy is sent.
"""

from typing import Any, Callable, Optional

import flet as ft

from zibaldone.ui import cloud_model as cm
from zibaldone.ui import services
from zibaldone.ui import theme as T
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext

SETUP_INTRO_FALLBACK = (
    "Da ora ogni istantanea sarà cifrata su questo dispositivo. I backup automatici non ti chiedono nulla: "
    "la passphrase serve solo per verificarli o ripristinarli. Riceverai anche un codice di recupero da scrivere "
    "su carta: serve se dimentichi la passphrase. Senza passphrase e senza codice di recupero i backup non si "
    "possono aprire, da nessuno. Il database su questo dispositivo resta in chiaro: la cifratura riguarda le istantanee."
)


def setup_intro() -> str:
    module = services.optional_module("zibaldone.cli.backup_cmd")
    text = getattr(module, "SETUP_INTRO", "") if module is not None else ""
    return " ".join(text.split()) if text else SETUP_INTRO_FALLBACK


def password_input(label: str, **kwargs: Any) -> ft.TextField:
    return W.text_input("", label=label, password=True, can_reveal_password=True, **kwargs)


def setup_encryption(ctx: AppContext, on_done: Optional[Callable[[], Any]] = None) -> None:
    keys = services.keys_api()
    if keys is None:
        ctx.toast("La cifratura dei backup è in arrivo.", error=True)
        return
    if services.encryption_on(ctx.folder):
        ctx.toast("La cifratura dei backup è già attiva.")
        return
    first = password_input("Passphrase dei backup", autofocus=True)
    second = password_input("Ripetila")
    error = W.error_text()
    go_on = W.primary_button("Avanti", None, icon="ARROW_FORWARD")

    def proceed(_: Any = None) -> None:
        problem = cm.check_new_passphrase(first.value or "", second.value or "")
        if problem:
            error.value, error.visible = problem, True
            ctx.update(error)
            return
        go_on.disabled = True
        ctx.update(go_on)
        passphrase = first.value or ""

        def created(new_keys: Any) -> None:
            ctx.close_dialog()
            show_recovery_code(ctx, keys, new_keys, passphrase, on_done)

        def failed(problem: Exception) -> None:
            go_on.disabled = False
            error.value, error.visible = cm.error_text(problem), True

        ctx.run_blocking(lambda: keys.create_keys(passphrase), created, failed)

    go_on.on_click = proceed
    second.on_submit = proceed
    dialog = ft.AlertDialog(
        modal=True,
        scrollable=True,
        title="Attiva la cifratura",
        content=ft.Container(
            ft.Column(
                [W.body(setup_intro(), dim=True, size=13), W.wide(first), W.wide(second), W.caption("Almeno 10 caratteri: meglio tre o quattro parole a caso."), error],
                spacing=12,
                tight=True,
            ),
            width=460,
        ),
        actions=[W.text_button("Annulla", ctx.close_dialog, color=T.TEXT), go_on],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.show_dialog(dialog)


def show_recovery_code(ctx: AppContext, keys: Any, new_keys: Any, passphrase: str, on_done: Optional[Callable[[], Any]]) -> None:
    code = new_keys.recovery_code
    answer = W.text_input("", label="Per conferma, scrivi l'ultimo gruppo del codice", autofocus=True, capitalization=ft.TextCapitalization.CHARACTERS)
    error = W.error_text()
    attempts = {"left": cm.CONFIRM_ATTEMPTS}
    confirm = W.primary_button("Ho scritto il codice", None, icon="CHECK")

    def check(_: Any = None) -> None:
        if not cm.recovery_answer_ok(code, answer.value or ""):
            attempts["left"] -= 1
            if attempts["left"] <= 0:
                ctx.close_dialog()
                ctx.toast("Configurazione annullata: non ho salvato nulla. Puoi riprovare quando vuoi.", error=True)
                return
            error.value, error.visible = "Non corrisponde: ricontrolla quello che hai scritto.", True
            ctx.update(error)
            return
        confirm.disabled = True
        ctx.update(confirm)
        save(ctx, keys, new_keys, passphrase, on_done)

    confirm.on_click = check
    answer.on_submit = check
    dialog = ft.AlertDialog(
        modal=True,
        scrollable=True,
        title="Il codice di recupero",
        content=ft.Container(
            ft.Column(
                [
                    W.body("Te lo mostro solo adesso. Scrivilo su carta e conservalo lontano da questo dispositivo: non salvarlo qui e non fotografarlo.", size=14),
                    W.panel(
                        ft.Text(code, size=18, weight=ft.FontWeight.W_600, color=T.ACCENT, font_family="monospace", selectable=True, text_align=ft.TextAlign.CENTER),
                        padding=14,
                        bgcolor=T.BG,
                    ),
                    W.caption("Serve se dimentichi la passphrase. Senza l'una e senza l'altro i backup non si aprono, da nessuno."),
                    W.wide(answer),
                    error,
                ],
                spacing=12,
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            width=460,
        ),
        actions=[W.text_button("Annulla", lambda _: (ctx.close_dialog(), ctx.toast("Non ho salvato nulla.")), color=T.TEXT), confirm],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.show_dialog(dialog)


def save(ctx: AppContext, keys: Any, new_keys: Any, passphrase: str, on_done: Optional[Callable[[], Any]]) -> None:
    folder = ctx.folder

    def work() -> Any:
        keys.save_new_keys(folder, new_keys)
        backups = services.backups_api()
        if backups is not None and hasattr(backups, "encrypt_existing_snapshots"):
            return backups.encrypt_existing_snapshots(folder, new_keys.private_key)
        return None

    def done(result: Any) -> None:
        ctx.close_dialog()
        message = f"Cifratura attiva (chiave {keys.format_key_id(new_keys.key_id)})."
        sealed = list(getattr(result, "encrypted", []) or [])
        failed = list(getattr(result, "failed", []) or [])
        if sealed:
            message += f" Istantanee che c'erano già, ora cifrate: {len(sealed)}."
        if failed:
            message += f" {len(failed)} sono rimaste in chiaro perché rovinate."
        ctx.toast(message, error=bool(failed))
        from zibaldone.ui.views.cloud import after_encryption_setup

        after_encryption_setup(ctx, passphrase, on_done)

    def failed(problem: Exception) -> None:
        ctx.close_dialog()
        ctx.toast(f"Cifratura non attivata: {cm.error_text(problem)}", error=True)

    ctx.run_blocking(work, done, failed)
