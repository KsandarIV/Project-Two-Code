"""Le Nuvole: the Google account and where the encrypted copies of the backups go.

It follows the terminal flow of `cli/account_cmd.py` (`run_login`,
`choose_destination_at_first_sign_in`, `use_google`, `offer_google_recovery`)
with dialogs instead of prompts. Everything that touches the network or the
disk runs in a thread through `ctx.run_blocking`; errors from the core are
already Italian and are shown as they are (terminal commands become places
in the app, see `cloud_model.app_hint`).
"""

from typing import Any, Callable, List, Optional

import flet as ft

from zibaldone.ui import cloud_model as cm
from zibaldone.ui import services
from zibaldone.ui import theme as T
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import settings_part

Callback = Optional[Callable[[], Any]]


def _later(callback: Callback) -> None:
    if callback is not None:
        callback()


def _offline(error: BaseException) -> bool:
    http = services.optional_module("zibaldone.cloud.http")
    offline = getattr(http, "OfflineError", None) if http is not None else None
    return offline is not None and isinstance(error, offline)


def recovery_tradeoff() -> str:
    module = services.optional_module("zibaldone.cli.account_cmd")
    text = getattr(module, "GOOGLE_RECOVERY_TRADEOFF", "") if module is not None else ""
    return " ".join(text.split()) if text else cm.RECOVERY_TRADEOFF_FALLBACK


# * — signing in —


def google_sign_in(ctx: AppContext, on_done: Callable[[Any], Any]) -> None:
    """Open the browser on Google's page and wait in a thread; a dialog shows the link meanwhile."""
    api = services.account_api()
    if api is None:
        ctx.toast("L'accesso con Google è in arrivo.", error=True)
        return
    folder = ctx.folder
    before, _ = services.account_status(folder)
    state = {"cancelled": False}
    link = ft.Text("", size=12, color=T.ACCENT, selectable=True, visible=False)
    waiting = ft.AlertDialog(
        modal=True,
        title="Accesso con Google",
        content=ft.Container(
            ft.Column(
                [
                    ft.Row(
                        [ft.ProgressRing(width=22, height=22, stroke_width=3, color=T.ACCENT), W.body("Si apre il browser sulla pagina di Google: finisci lì l'accesso e torna qui.", expand=True)],
                        spacing=14,
                    ),
                    W.caption("Se il browser non si apre, copia questo indirizzo:"),
                    link,
                ],
                spacing=10,
                tight=True,
            ),
            width=440,
        ),
        actions=[W.text_button("Annulla", lambda _: cancel(), color=T.TEXT)],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def cancel() -> None:
        state["cancelled"] = True
        ctx.close_dialog()
        ctx.toast("Accesso annullato. Puoi riprovare quando vuoi.")

    def show_link(url: str) -> None:  # called from the worker thread
        def put() -> None:
            link.value, link.visible = url, True
            ctx.update(link)

        ctx.call_soon(put)
        ctx.open_url(url)

    def done(status: Any) -> None:
        if not state["cancelled"]:
            ctx.close_dialog()
        for note in cm.sign_in_notes(before, status):
            ctx.toast(note)
        on_done(status)

    def failed(problem: Exception) -> None:
        if state["cancelled"]:
            return
        ctx.close_dialog()
        ctx.toast(f"Accesso non riuscito: {cm.error_text(problem)}", error=True)

    ctx.show_dialog(waiting)
    ctx.run_blocking(lambda: api.sign_in_with_google(folder, open_browser=show_link), done, failed)


# * — sending the copies —


def first_sync(ctx: AppContext, then: Callback = None) -> None:
    """Right after choosing a destination: send what is there, if encryption is on."""
    sync = services.sync_api()
    if sync is None:
        _later(then)
        return
    if not services.encryption_on(ctx.folder):
        ctx.toast("Le copie partono quando attivi la cifratura dei backup in Mnemosyne: nessun dato esce in chiaro.")
        _later(then)
        return
    folder = ctx.folder

    def done(result: Any) -> None:
        ctx.toast(cm.first_sync_text(result))
        _later(then)

    def failed(problem: Exception) -> None:
        if _offline(problem):
            ctx.toast(f"{cm.error_text(problem)}. Riproverò al prossimo backup automatico.", error=True)
        else:
            ctx.toast(f"Prima copia non riuscita: {cm.error_text(problem)}", error=True)
        _later(then)

    ctx.run_blocking(lambda: sync.sync_now(folder), done, failed)


def offer_google_recovery(ctx: AppContext, passphrase: str = "", then: Callback = None) -> None:
    """Explain the trade-off and turn on the recovery through Google if the user wants it."""
    status, _ = services.account_status(ctx.folder)
    sync = services.sync_api()
    if (
        sync is None
        or not hasattr(sync, "enable_google_recovery")
        or status is None
        or status.mode != "google"
        or getattr(status, "google_recovery", False)
        or not services.encryption_on(ctx.folder)
    ):
        _later(then)
        return
    folder = ctx.folder
    secret = W.text_input(passphrase, label="Passphrase dei backup", password=True, can_reveal_password=True, visible=not passphrase)
    error = W.error_text()
    turn_on = W.primary_button("Attiva", None, icon="KEY")

    def decline(_: Any = None) -> None:
        ctx.close_dialog()
        ctx.toast("Va bene: per recuperare i backup serviranno la passphrase o il codice di recupero.")
        _later(then)

    def accept(_: Any = None) -> None:
        value = secret.value or ""
        if not value:
            error.value, error.visible = "Scrivi la passphrase dei backup.", True
            ctx.update(error)
            return
        turn_on.disabled = True
        ctx.update(turn_on)

        def done(_: Any) -> None:
            ctx.close_dialog()
            ctx.toast("Recupero con Google attivo. Puoi toglierlo quando vuoi, qui nelle Nuvole.")
            _later(then)

        def failed(problem: Exception) -> None:
            turn_on.disabled = False
            if _offline(problem):
                ctx.close_dialog()
                ctx.toast(f"{cm.error_text(problem)}. Puoi attivarlo più tardi dalle Nuvole.", error=True)
                _later(then)
                return
            error.value, error.visible = cm.error_text(problem), True
            secret.visible = True

        ctx.run_blocking(lambda: sync.enable_google_recovery(folder, value), done, failed)

    turn_on.on_click = accept
    secret.on_submit = accept
    dialog = ft.AlertDialog(
        modal=True,
        scrollable=True,
        title="Recupero con l'account Google?",
        content=ft.Container(ft.Column([W.body(recovery_tradeoff(), size=14), W.wide(secret), error], spacing=12, tight=True), width=460),
        actions=[W.text_button("No, grazie", decline, color=T.TEXT), turn_on],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.show_dialog(dialog)


def use_google(ctx: AppContext, then: Callback = None) -> None:
    api = services.account_api()
    if api is None:
        _later(then)
        return
    folder = ctx.folder

    def done(status: Any) -> None:
        ctx.toast(f"Copie: {status.mode_label} ({status.email}). Su Drive vanno solo istantanee già cifrate.")
        offer_google_recovery(ctx, then=lambda: first_sync(ctx, then))

    def failed(problem: Exception) -> None:
        ctx.toast(cm.error_text(problem), error=True)
        _later(then)

    ctx.run_blocking(lambda: api.choose_mode(folder, "google"), done, failed)


def after_encryption_setup(ctx: AppContext, passphrase: str, then: Callback = None) -> None:
    """Called once Mnemosyne's encryption is on: offer the Google recovery and send the first copies."""
    status, _ = services.account_status(ctx.folder)
    if status is None or status.mode == "local":
        _later(then)
        return
    offer_google_recovery(ctx, passphrase, then=lambda: first_sync(ctx, then))


# * — the page —


class CloudScreen:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self.mode = "local"
        self.saved_mode = "local"
        self.path_input = W.text_input("", label="Cartella", hint_text="per esempio E:\\Backup o la cartella di OneDrive")
        self.error = W.error_text()
        self.status: Any = None

    def header(self) -> ft.Control:
        part = settings_part("nuvole")
        return W.screen_header(part.nickname, part.label, "come Socrate sospeso tra le nuvole, ma con i piedi per terra: i dati restano anche qui", on_back=self.ctx.back)

    def build(self) -> ft.Control:
        controls: List[ft.Control] = [self.header()]
        api = services.account_api()
        if api is None:
            controls.append(W.coming_soon("Account e copie nel cloud arrivano a breve. Per ora ZibaldOne lavora solo in locale."))
            return W.screen(controls, self.ctx.wide)
        self.api = api
        status, problem = services.account_status(self.ctx.folder)
        if status is None:
            controls.append(W.coming_soon(f"Le Nuvole non rispondono: {cm.app_hint(problem)}"))
            return W.screen(controls, self.ctx.wide)
        self.status = status
        encryption = services.encryption_on(self.ctx.folder)
        controls.append(self.account_panel(status, encryption))
        controls.append(W.section_label("Dove vanno le copie", "istantanee già cifrate, mai il database in chiaro"))
        controls.append(self.destination_panel(status))
        if status.mode != "local":
            controls.append(W.section_label("Le copie fuori", cm.destination_label(status)))
            controls.append(self.copies_panel(status, encryption))
        return W.screen(controls, self.ctx.wide)

    # — panels —

    def account_panel(self, status: Any, encryption: bool) -> ft.Control:
        lines: List[ft.Control] = [W.info_row(label, value, selectable=True) for label, value in cm.cloud_lines(status, encryption)]
        actions: List[ft.Control] = []
        if status.signed_in:
            actions.append(W.secondary_button("Esci", self.ask_sign_out, icon="LOGOUT"))
        elif status.google_configured:
            actions.append(W.primary_button("Entra con Google", lambda _: google_sign_in(self.ctx, lambda _status: self.ctx.refresh()), icon="LOGIN"))
        if actions:
            lines.append(ft.Row(actions, alignment=ft.MainAxisAlignment.END))
        return W.panel(ft.Column(lines, spacing=12))

    def destination_panel(self, status: Any) -> ft.Control:
        self.mode = self.saved_mode = status.mode
        self.path_input.value = status.folder_path or ""
        self.path_input.visible = self.mode == "folder"
        radios = []
        for choice in cm.mode_choices(status):
            radios.append(
                ft.Column(
                    [
                        ft.Radio(value=choice.mode, label=choice.label, active_color=T.ACCENT, disabled=not choice.enabled),
                        ft.Container(W.caption(choice.hint), padding=ft.Padding.only(left=48, bottom=6)),
                    ],
                    spacing=0,
                )
            )
        group = ft.RadioGroup(value=self.mode, on_change=self.mode_changed, content=ft.Column(radios, spacing=0))
        return W.panel(
            ft.Column(
                [group, W.wide(self.path_input), self.error, ft.Row([W.secondary_button("Applica", self.apply_mode, icon="CHECK")], alignment=ft.MainAxisAlignment.END)],
                spacing=10,
            )
        )

    def copies_panel(self, status: Any, encryption: bool) -> ft.Control:
        sync = services.sync_api()
        items: List[ft.Control] = []
        note = cm.needs_encryption_note(status, encryption)
        if note:
            from zibaldone.ui.views.encryption import setup_encryption

            items.append(W.body(note, dim=True))
            items.append(ft.Row([W.primary_button("Attiva la cifratura", lambda _: setup_encryption(self.ctx, self.ctx.refresh), icon="LOCK_OUTLINE")], alignment=ft.MainAxisAlignment.END))
        elif sync is not None:
            items.append(ft.Row([W.primary_button("Sincronizza ora", self.sync, icon="SYNC")], alignment=ft.MainAxisAlignment.END))
        if sync is not None and status.mode == "google" and encryption and hasattr(sync, "enable_google_recovery"):
            items.append(W.divider())
            items.append(
                ft.Row(
                    [
                        ft.Column([W.body("Recupero con l'account Google"), W.caption("su un dispositivo nuovo basta entrare con Google, senza passphrase")], spacing=2, expand=True),
                        ft.Switch(value=bool(status.google_recovery), active_color=T.ACCENT, on_change=self.recovery_switched),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        if sync is not None and hasattr(sync, "recover_from_cloud"):
            items.append(W.divider())
            items.append(
                ft.Row(
                    [
                        W.secondary_button("Riporta i dati qui", self.recover, icon="DOWNLOAD"),
                        W.secondary_button("Cancella le copie fuori", self.ask_forget, icon="DELETE_OUTLINE"),
                    ],
                    wrap=True,
                    spacing=8,
                    run_spacing=8,
                )
            )
            items.append(W.caption("«Riporta i dati qui» serve su un dispositivo nuovo; prima salva lo stato attuale. «Cancella» toglie solo le copie fuori: diario e backup qui restano."))
        return W.panel(ft.Column(items, spacing=10))

    # — destination —

    def mode_changed(self, event: Any) -> None:
        self.mode = event.control.value or "local"
        self.path_input.visible = self.mode == "folder"
        self.error.visible = False
        self.ctx.update(self.path_input, self.error)

    def apply_mode(self, _: Any = None) -> None:
        if self.mode == "google":
            use_google(self.ctx, self.ctx.refresh)
            return
        if self.mode == "local" and self.saved_mode != "local":
            self.ask_back_to_local()
            return
        self.choose(self.mode)

    def choose(self, mode: str, then: Callback = None) -> None:
        folder, path = self.ctx.folder, (self.path_input.value or "").strip() or None

        def failed(problem: Exception) -> None:
            self.error.value, self.error.visible = cm.error_text(problem), True

        def done(status: Any) -> None:
            self.ctx.toast(f"Copie: {status.mode_label}.")
            if mode == "folder":
                first_sync(self.ctx, self.ctx.refresh)
            else:
                _later(then)
                self.ctx.refresh()

        self.ctx.run_blocking(lambda: self.api.choose_mode(folder, mode, folder_path=path if mode == "folder" else None), done, failed)

    def ask_back_to_local(self) -> None:
        where = cm.destination_label(self.status)

        def keep(_: Any = None) -> None:
            self.ctx.close_dialog()
            self.choose("local", lambda: self.ctx.toast("Le copie che c'erano già restano dove sono."))

        def wipe(_: Any = None) -> None:
            self.ctx.close_dialog()
            self.forget()

        dialog = ft.AlertDialog(
            modal=True,
            scrollable=True,
            title="Solo su questo dispositivo",
            content=ft.Container(W.body(f"Le copie già su {where} restano lì, a meno che tu non le voglia cancellare. Diario e backup qui restano comunque.", size=14), width=440),
            actions=[W.text_button("Annulla", self.ctx.close_dialog, color=T.TEXT), W.danger_button("Cancellale", wipe), W.primary_button("Lasciale lì", keep)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.ctx.show_dialog(dialog)

    # — copies —

    def sync(self, _: Any = None) -> None:
        sync = services.sync_api()
        if sync is None:
            return
        folder = self.ctx.folder

        def done(result: Any) -> None:
            self.ctx.toast(cm.first_sync_text(result))
            self.ctx.refresh()

        def failed(problem: Exception) -> None:
            self.ctx.toast(cm.error_text(problem), error=True)
            self.ctx.refresh()

        self.ctx.run_blocking(lambda: sync.sync_now(folder), done, failed)

    def recovery_switched(self, event: Any) -> None:
        switch = event.control
        if switch.value:
            switch.value = False  # turned on only once the user agreed in the dialog
            offer_google_recovery(self.ctx, then=self.ctx.refresh)
            return
        sync, folder = services.sync_api(), self.ctx.folder

        def turn_off() -> None:
            self.ctx.run_blocking(
                lambda: sync.disable_google_recovery(folder),
                lambda _: (self.ctx.toast("Recupero con Google tolto: ora servono la passphrase o il codice di recupero."), self.ctx.refresh()),
                lambda problem: (self.ctx.toast(cm.error_text(problem), error=True), self.ctx.refresh()),
            )

        switch.value = True
        self.ctx.confirm(
            "Togliere il recupero con Google?",
            "Per riavere i backup su un dispositivo nuovo serviranno la passphrase o il codice di recupero.",
            "Togli",
            turn_off,
            danger=False,
        )

    def ask_forget(self, _: Any = None) -> None:
        where = cm.destination_label(self.status)
        self.ctx.confirm(
            "Cancellare le copie fuori?",
            f"Tutte le copie di ZibaldOne su {where} spariranno e le copie resteranno solo qui. Diario e backup su questo dispositivo restano.",
            "Cancella",
            self.forget,
        )

    def forget(self) -> None:
        sync, folder = services.sync_api(), self.ctx.folder

        def work() -> int:
            removed = sync.forget_remote(folder)
            self.api.choose_mode(folder, "local")
            return removed

        def done(removed: int) -> None:
            self.ctx.toast(f"File cancellati fuori: {removed}. Ora le copie restano solo su questo dispositivo.")
            self.ctx.refresh()

        self.ctx.run_blocking(work, done, lambda problem: self.ctx.toast(cm.error_text(problem), error=True))

    def recover(self, _: Any = None) -> None:
        sync, folder = services.sync_api(), self.ctx.folder

        def work() -> Any:
            snapshots = sync.list_remote(folder)
            google = False
            if snapshots and hasattr(sync, "google_recovery_available"):
                try:
                    google = bool(sync.google_recovery_available(folder))
                except Exception:
                    google = False
            return snapshots, google

        def done(found: Any) -> None:
            snapshots, google = found
            if not snapshots:
                self.ctx.toast("Fuori non c'è ancora nessuna istantanea.")
                return
            RecoverDialog(self.ctx, cm.remote_choices(snapshots), google).open()

        self.ctx.run_blocking(work, done, lambda problem: self.ctx.toast(cm.error_text(problem), error=True))

    def ask_sign_out(self, _: Any = None) -> None:
        folder, email = self.ctx.folder, getattr(self.status, "email", "") or ""

        def sign_out() -> None:
            def done(revoked: Any) -> None:
                self.ctx.toast("Sei uscito. Le copie già su Drive restano lì; da ora i backup restano solo qui.")
                if not revoked:
                    self.ctx.toast("Google non ha confermato la revoca (sei offline?): puoi toglierla da myaccount.google.com/permissions.")
                self.ctx.refresh()

            self.ctx.run_blocking(lambda: self.api.sign_out(folder), done, lambda problem: self.ctx.toast(cm.error_text(problem), error=True))

        self.ctx.confirm(f"Uscire da {email}?" if email else "Uscire dall'account?", "Diario e backup restano su questo dispositivo.", "Esci", sign_out, danger=False)


class RecoverDialog:
    """Bring the data back from the copies outside, for example on a new device."""

    def __init__(self, ctx: AppContext, choices: List[cm.RemoteChoice], google: bool) -> None:
        self.ctx = ctx
        self.snapshot = W.dropdown([(choice.id, choice.label) for choice in choices], choices[0].id, label="Istantanea", expand=True)
        methods = cm.recovery_methods(google)
        self.method = methods[0][0]
        self.methods = ft.RadioGroup(
            value=self.method,
            on_change=self.method_changed,
            content=ft.Column([ft.Radio(value=key, label=label, active_color=T.ACCENT) for key, label in methods], spacing=0),
        )
        self.secret = W.text_input("", label=self.secret_label(), password=True, can_reveal_password=True, visible=self.method != "google")
        self.error = W.error_text()
        self.button = W.danger_button("Riporta i dati", self.confirm)

    def secret_label(self) -> str:
        return "Codice di recupero" if self.method == "code" else "Passphrase dei backup"

    def open(self) -> None:
        dialog = ft.AlertDialog(
            modal=True,
            scrollable=True,
            title="Riporta i dati qui",
            content=ft.Container(
                ft.Column(
                    [
                        W.body("Sostituisce modelli e voci di questo dispositivo con quelli dell'istantanea. Lo stato attuale viene salvato prima, così puoi tornare indietro.", size=14),
                        ft.Row([self.snapshot]),
                        self.methods,
                        W.wide(self.secret),
                        self.error,
                    ],
                    spacing=12,
                    tight=True,
                    ),
                width=460,
            ),
            actions=[W.text_button("Annulla", self.ctx.close_dialog, color=T.TEXT), self.button],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.ctx.show_dialog(dialog)

    def method_changed(self, event: Any) -> None:
        self.method = event.control.value or "passphrase"
        self.secret.visible = self.method != "google"
        self.secret.label = self.secret_label()
        self.secret.value = ""
        self.ctx.update(self.secret)

    def confirm(self, _: Any = None) -> None:
        secret = self.secret.value or ""
        if self.method != "google" and not secret:
            self.error.value, self.error.visible = f"Scrivi {self.secret_label().lower()}.", True
            self.ctx.update(self.error)
            return
        sync, folder, reference = services.sync_api(), self.ctx.folder, self.snapshot.value
        passphrase = secret if self.method == "passphrase" else None
        code = secret if self.method == "code" else None
        self.button.disabled = True
        self.ctx.update(self.button)

        def done(result: Any) -> None:
            self.ctx.close_dialog()
            self.ctx.toast(cm.restored_text(result))
            self.ctx.go("/oggi")

        def failed(problem: Exception) -> None:
            self.button.disabled = False
            self.error.value, self.error.visible = cm.error_text(problem), True

        # every Store of this app is opened and closed per operation, so none is open here
        self.ctx.run_blocking(lambda: sync.recover_from_cloud(folder, passphrase=passphrase, recovery_code=code, reference=reference), done, failed)
