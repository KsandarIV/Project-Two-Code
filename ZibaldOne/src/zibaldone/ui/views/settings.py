"""Organon: privacy (Parresia), reminders (Daimon), backups (Mnemosyne),
account and cloud (Le Nuvole) and the about page."""

from datetime import timedelta
from typing import Any, List, Optional

import flet as ft

from zibaldone import __version__
from zibaldone.core.brand import APP_MOTTO, APP_NAME, APP_TAGLINE, NOMENCLATURE
from zibaldone.core.privacy import notice_text
from zibaldone.core.reminders import MOMENT_LABELS, ReminderConfig, keep_frequency, thin_out
from zibaldone.storage.paths import folder_usage, human_size
from zibaldone.storage.settings import SettingsError, consent_status
from zibaldone.ui import cloud_model as cm
from zibaldone.ui import services
from zibaldone.ui import theme as T
from zibaldone.ui import viewmodels as vm
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import SETTINGS_PARTS, Route, section, settings_part
from zibaldone.ui.views import anonymizer
from zibaldone.ui.views.cloud import CloudScreen
from zibaldone.ui.views.common import not_found


def build_index(ctx: AppContext, route: Route) -> ft.Control:
    info = section("organon")
    cards = []
    for part in SETTINGS_PARTS:
        cards.append(
            W.panel(
                ft.Row(
                    [
                        ft.Container(ft.Icon(W.icon_of(part.icon), color=T.ACCENT, size=22), width=40, height=40, bgcolor=W.fade(T.ACCENT, 0.12), border_radius=T.RADIUS_SMALL, alignment=ft.Alignment.CENTER),
                        ft.Column(
                            [W.title_with_nickname(part.nickname, part.label, size=16), W.caption(part.description)],
                            spacing=2,
                            expand=True,
                        ),
                        ft.Icon(ft.Icons.CHEVRON_RIGHT, color=T.TEXT_DIM),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                on_click=lambda _, key=part.key: ctx.go(f"/organon/{key}"),
                col={"xs": 12, "md": 6},
            )
        )
    return W.screen(
        [
            W.screen_header(info.label, info.nickname, "gli strumenti del pensiero, come l'Organon di Aristotele"),
            ft.ResponsiveRow(cards, spacing=12, run_spacing=12),
        ],
        ctx.wide,
    )


def build_part(ctx: AppContext, route: Route) -> ft.Control:
    builders = {"parresia": parresia, "daimon": lambda c: DaimonScreen(c).build(), "mnemosyne": lambda c: MnemosyneScreen(c).build(), "nuvole": lambda c: CloudScreen(c).build(), "velo": anonymizer.build, "info": about}
    builder = builders.get(route.arg)
    if builder is None:
        return not_found(ctx, "Questa parte delle impostazioni non esiste.")
    return builder(ctx)


def _header(ctx: AppContext, key: str, subtitle: str = "") -> ft.Control:
    part = settings_part(key)
    return W.screen_header(part.nickname, part.label, subtitle or part.description, on_back=ctx.back)


# * — Parresia —


def parresia(ctx: AppContext) -> ft.Control:
    files, size = folder_usage(ctx.folder)
    try:
        consent = vm.consent_label(consent_status(ctx.folder))
    except SettingsError as problem:
        consent = f"non leggibile: {problem}"
    return W.screen(
        [
            _header(ctx, "parresia", NOMENCLATURE["privacy"].source),
            W.panel(
                ft.Column(
                    [
                        W.info_row("Cartella dei dati", str(ctx.folder), selectable=True),
                        W.info_row("Contenuto", f"{files} file, {human_size(size)}"),
                        W.info_row("Consenso", consent),
                    ],
                    spacing=12,
                )
            ),
            W.section_label("L'informativa"),
            W.panel(W.body(cm.app_hint(notice_text(ctx.folder)), selectable=True)),
        ],
        ctx.wide,
    )


# * — Daimon —


class DaimonScreen:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self.error = W.error_text()

    def build(self) -> ft.Control:
        config, problem = services.reminder_config(self.ctx.folder)
        controls: List[ft.Control] = [_header(self.ctx, "daimon", "una voce gentile che ricorda, mai che rimprovera")]
        if config is None:
            controls.append(
                W.panel(
                    ft.Column(
                        [
                            W.body("Le impostazioni dei promemoria non si leggono:"),
                            W.body(problem, dim=True, selectable=True),
                            W.primary_button("Torna ai valori di base", self.reset_defaults, icon="RESTART_ALT"),
                        ],
                        spacing=10,
                    ),
                    border_color=W.fade(T.ERROR, 0.5),
                )
            )
            return W.screen(controls, self.ctx.wide)
        self.config = config
        self.form = vm.reminder_form(config)
        controls.append(self._overview())
        controls.append(
            W.panel(
                ft.Switch(
                    label="Promemoria accesi",
                    value=self.form.enabled,
                    active_color=T.ACCENT,
                    on_change=lambda e: setattr(self.form, "enabled", bool(e.control.value)),
                    label_text_style=ft.TextStyle(color=T.TEXT, size=15),
                ),
                padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            )
        )
        controls.append(W.section_label("I tre momenti"))
        for moment in self.form.moments:
            controls.append(self._moment_panel(moment))
        controls.append(W.section_label("Ore di silenzio"))
        controls.append(self._quiet_panel())
        controls.append(self.error)
        controls.append(ft.Row([W.primary_button("Salva i promemoria", self.save, icon="CHECK")], alignment=ft.MainAxisAlignment.END))
        controls.append(W.caption("Mentre ZibaldOne è aperta, il Daimon ti avvisa con un messaggio qui dentro. Ad app chiusa, per ora, i promemoria arrivano solo sul computer, dopo `zbone remind install`."))
        return W.screen(controls, self.ctx.wide)

    def _overview(self) -> ft.Control:
        overview, problem = services.reminder_overview(self.ctx.folder, self.ctx.now())
        if overview is None:
            return W.panel(W.body(f"Stato non disponibile: {problem}", dim=True))
        lines: List[ft.Control] = []
        if overview.streak_days:
            lines.append(ft.Row([ft.Icon(ft.Icons.LOCAL_FIRE_DEPARTMENT, color=T.ACCENT_2, size=18), W.body(f"{overview.streak_days} giorni di fila con il tuo zibaldone")], spacing=6))
        if overview.upcoming is not None:
            at = overview.upcoming.at
            today = overview.now.date()
            when = "oggi" if at.date() == today else ("domani" if at.date() == today + timedelta(days=1) else vm.italian_date(at.date()))
            lines.append(W.body(f"Il prossimo: {MOMENT_LABELS[overview.upcoming.moment].lower()}, {when} alle {at:%H:%M}."))
        for check in overview.checks:
            lines.append(W.caption(f"{MOMENT_LABELS[check.moment]}: {check.reason}"))
        for warning in overview.warnings:
            lines.append(ft.Row([ft.Icon(ft.Icons.INFO_OUTLINE, color=T.ACCENT_2, size=16), W.body(warning, size=13, expand=True)], spacing=6))
        for suggestion in overview.suggestions:
            lines.append(
                W.panel(
                    ft.Column(
                        [
                            W.body(suggestion.message, size=14),
                            ft.Row(
                                [
                                    W.text_button("Va bene così", lambda _, key=suggestion.moment: self.backoff(key, False), color=T.TEXT),
                                    W.primary_button("Sì, meno spesso", lambda _, key=suggestion.moment: self.backoff(key, True)),
                                ],
                                alignment=ft.MainAxisAlignment.END,
                                wrap=True,
                            ),
                        ],
                        spacing=8,
                    ),
                    bgcolor=T.BG,
                    padding=12,
                )
            )
        if overview.missing_templates:
            lines.append(W.caption("Manca il modello per: " + ", ".join(MOMENT_LABELS[key] for key in overview.missing_templates) + " (Scuole · Stoa)."))
        return W.panel(ft.Column(lines or [W.body("Tutto tranquillo.", dim=True)], spacing=6))

    def _moment_panel(self, moment: vm.MomentForm) -> ft.Control:
        days_row = ft.Row(spacing=6, run_spacing=6, wrap=True)

        def draw_days() -> None:
            days_row.controls = [
                ft.Container(
                    ft.Text(name, size=13, color=T.BG if day in moment.weekdays else T.TEXT_DIM, weight=ft.FontWeight.W_600),
                    width=44,
                    height=32,
                    alignment=ft.Alignment.CENTER,
                    border_radius=16,
                    bgcolor=T.ACCENT if day in moment.weekdays else None,
                    border=ft.Border.all(1, T.ACCENT if day in moment.weekdays else T.BORDER),
                    on_click=lambda _, day=day: toggle(day),
                )
                for day, name in enumerate(vm.WEEKDAY_SHORT)
            ]

        def toggle(day: int) -> None:
            moment.weekdays = vm.toggle_weekday(moment.weekdays, day)
            draw_days()
            self.ctx.update(days_row)

        draw_days()
        return W.panel(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Switch(label=moment.label, value=moment.enabled, active_color=T.ACCENT, label_text_style=ft.TextStyle(color=T.TEXT, size=15), on_change=lambda e: setattr(moment, "enabled", bool(e.control.value)), expand=True),
                            W.text_input(moment.time, label="Ora", width=110, on_change=lambda e: setattr(moment, "time", e.control.value or "")),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    days_row,
                ],
                spacing=10,
            ),
            padding=14,
        )

    def _quiet_panel(self) -> ft.Control:
        form = self.form
        return W.panel(
            ft.Row(
                [
                    ft.Switch(label="Silenzio", value=form.quiet_enabled, active_color=T.ACCENT, label_text_style=ft.TextStyle(color=T.TEXT, size=15), on_change=lambda e: setattr(form, "quiet_enabled", bool(e.control.value))),
                    W.text_input(form.quiet_start, label="Dalle", width=110, on_change=lambda e: setattr(form, "quiet_start", e.control.value or "")),
                    W.text_input(form.quiet_end, label="Alle", width=110, on_change=lambda e: setattr(form, "quiet_end", e.control.value or "")),
                ],
                spacing=12,
                wrap=True,
                run_spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=14,
        )

    def _store_config(self, config: ReminderConfig, message: str) -> None:
        from zibaldone.storage.reminder_log import save_reminder_config

        try:
            save_reminder_config(self.ctx.folder, config)
        except (OSError, ValueError, SettingsError) as problem:
            self.ctx.toast(str(problem), error=True)
            return
        self.ctx.toast(message)
        self.ctx.refresh()

    def save(self, _: Any = None) -> None:
        try:
            config = vm.config_from_reminder_form(self.form, self.config)
        except ValueError as problem:
            self.error.value = str(problem)
            self.error.visible = True
            self.ctx.update(self.error)
            return
        self._store_config(config, "Promemoria salvati.")

    def backoff(self, key: str, fewer: bool) -> None:
        today = self.ctx.now().date()
        config = thin_out(self.config, key, today) if fewer else keep_frequency(self.config, key, today)
        self._store_config(config, "Fatto: ti avviserò meno spesso." if fewer else "D'accordo, nessun cambiamento.")

    def reset_defaults(self, _: Any = None) -> None:
        self._store_config(ReminderConfig(), "Promemoria riportati ai valori di base.")


# * — Mnemosyne —


class MnemosyneScreen:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self.list_column = ft.Column(spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.note = W.text_input("", label="Nota (facoltativa)", hint_text="per esempio: prima di riorganizzare i modelli", expand=True)
        self.button = W.primary_button("Crea ora", self.create, icon="ADD_A_PHOTO_OUTLINED")

    def build(self) -> ft.Control:
        controls: List[ft.Control] = [_header(self.ctx, "mnemosyne", "istantanee complete dei tuoi dati, come i commit")]
        api = services.backups_api()
        if api is None:
            controls.append(W.coming_soon("I backup di Mnemosyne arrivano a breve. Intanto i tuoi dati restano nella cartella dati."))
            return W.screen(controls, self.ctx.wide)
        self.api = api
        controls.append(self.encryption_panel())
        if services.encryption_on(self.ctx.folder):
            from zibaldone.ui.views.vault import secrets_panel

            controls.append(secrets_panel(self.ctx))
        if self.ctx.wide:
            maker = ft.Row([self.note, self.button], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        else:
            maker = ft.Column([self.note, ft.Row([self.button], alignment=ft.MainAxisAlignment.END)], spacing=10)
        controls.append(W.panel(maker, padding=14))
        controls.append(W.section_label("Le istantanee"))
        controls.append(self.list_column)
        self.reload(update=False)
        return W.screen(controls, self.ctx.wide)

    def encryption_panel(self) -> ft.Control:
        keys = services.keys_api()
        if keys is None:
            return W.coming_soon("La cifratura delle istantanee è in arrivo.")
        if services.encryption_on(self.ctx.folder):
            try:
                key = keys.format_key_id(keys.key_id(self.ctx.folder))
            except Exception:
                key = ""
            text = "Cifratura attiva: le istantanee si aprono solo con la tua passphrase o con il codice di recupero."
            return W.panel(
                ft.Row(
                    [ft.Icon(ft.Icons.LOCK_OUTLINE, color=T.SUCCESS, size=22), ft.Column([W.body(text), W.caption(f"chiave {key}" if key else "")], spacing=2, expand=True)],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=14,
            )
        from zibaldone.ui.views.encryption import setup_encryption

        return W.panel(
            ft.Column(
                [
                    ft.Row(
                        [ft.Icon(ft.Icons.LOCK_OPEN, color=T.ACCENT_2, size=22), W.body("Le istantanee non sono cifrate: chi ha i file può leggerle. Per le copie nelle Nuvole la cifratura serve.", expand=True)],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row([W.primary_button("Attiva la cifratura", lambda _: setup_encryption(self.ctx, self.ctx.refresh), icon="LOCK_OUTLINE")], alignment=ft.MainAxisAlignment.END),
                ],
                spacing=10,
            ),
            border_color=W.fade(T.ACCENT_2, 0.4),
            padding=14,
        )

    def reload(self, update: bool = True) -> None:
        try:
            rows = vm.snapshot_rows(self.api.list_snapshots(self.ctx.folder))
        except Exception as problem:
            self.list_column.controls = [W.coming_soon(f"Mnemosyne non ha risposto: {problem}")]
        else:
            if not rows:
                self.list_column.controls = [W.empty_state("Ancora nessuna istantanea. «Crea ora» ne salva una completa.", "HISTORY")]
            else:
                self.list_column.controls = [self._row(row) for row in rows]
        if update:
            self.ctx.update(self.list_column)

    def _row(self, row: vm.SnapshotRow) -> ft.Control:
        details = f"{row.reason} · {row.size}" + (" · cifrata" if row.encrypted else "")
        texts: List[ft.Control] = [W.body(row.when, size=15), W.caption(details)]
        if row.note:
            texts.append(W.body(row.note, dim=True, size=13))
        if row.problem:
            texts.append(ft.Text(row.problem, size=12, color=T.ERROR))
        return W.panel(
            ft.Row(
                [ft.Icon(ft.Icons.LOCK_OUTLINE if row.encrypted else ft.Icons.HISTORY, color=T.ACCENT, size=22), ft.Column(texts, spacing=2, expand=True), W.caption(row.id[-6:])],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        )

    def create(self, _: Any = None) -> None:
        folder, note = self.ctx.folder, (self.note.value or "").strip()
        self.button.disabled = True
        self.ctx.update(self.button)

        def work() -> Any:
            self.api.create_snapshot(folder, reason="manual", note=note)
            return services.sync_quietly(folder)

        def done(warning: Any) -> None:
            self.button.disabled = False
            self.note.value = ""
            self.ctx.toast("Istantanea creata: Mnemosyne ricorda.")
            if warning:
                self.ctx.toast(warning, error=True)
            self.reload()

        def failed(problem: Exception) -> None:
            self.button.disabled = False
            self.ctx.toast(f"Istantanea non creata: {cm.error_text(problem)}", error=True)

        self.ctx.run_blocking(work, done, failed)


# * — Informazioni —


class UpdatesPanel:
    """Is there a newer ZibaldOne? The daily check and a button to ask now (0.1.1)."""

    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self.result = ft.Column([], spacing=8)

    def build(self) -> ft.Control:
        try:
            enabled = services.update_check_enabled(self.ctx.folder)
        except Exception:
            enabled = False
        switch = ft.Switch(
            label="Controlla da sola una volta al giorno",
            value=enabled,
            active_color=T.ACCENT,
            label_text_style=ft.TextStyle(color=T.TEXT, size=15),
            on_change=self.toggle,
        )
        return W.panel(
            ft.Column(
                [
                    W.body("Aggiornamenti", size=16, weight=ft.FontWeight.W_600),
                    W.caption("L'app chiede a GitHub se c'è una versione nuova: GitHub vede l'indirizzo IP del dispositivo e la versione dell'app, nient'altro."),
                    switch,
                    W.secondary_button("Controlla adesso", self.check, icon="SYSTEM_UPDATE"),
                    self.result,
                ],
                spacing=10,
            )
        )

    def toggle(self, event: Any) -> None:
        enabled = bool(event.control.value)
        try:
            services.set_update_check(self.ctx.folder, enabled)
        except Exception as error:
            self.ctx.toast(str(error), error=True)
            return
        self.ctx.toast("Controllo automatico acceso." if enabled else "Controllo automatico spento: controlla tu da qui.")

    def check(self, _: Any = None) -> None:
        self.result.controls = [W.caption("Chiedo a GitHub…")]
        self.ctx.update()

        def done(release: Any) -> None:
            if release is None:
                self.result.controls = [W.body(f"Hai la versione più recente ({__version__}).", dim=True)]
                return
            url = release.apk_url if services.running_on_android() and release.apk_url else release.page_url
            self.result.controls = [
                W.body(f"È uscita ZibaldOne {release.version} (tu hai la {__version__}).", size=14),
                W.primary_button("Scarica", lambda _: self.ctx.open_url(url), icon="DOWNLOAD"),
            ]

        def failed(problem: Exception) -> None:
            self.result.controls = [W.body(str(problem), dim=True)]
            self.ctx.update()

        self.ctx.run_blocking(lambda: services.check_updates_now(self.ctx.folder), done, failed)


def about(ctx: AppContext) -> ft.Control:
    cards = []
    for mascot in vm.mascot_cards():
        badge = W.pill("proposta: la mascotte dell'app" if mascot.is_app else mascot.area, mascot.color)
        cards.append(
            W.panel(
                ft.Row(
                    [
                        ft.Container(
                            ft.Text(mascot.name[0], size=22, weight=ft.FontWeight.W_700, color=T.readable_on(mascot.color)),
                            width=48,
                            height=48,
                            bgcolor=mascot.color,
                            border_radius=24,
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Column(
                            [
                                ft.Row([ft.Text(mascot.name, size=16, weight=ft.FontWeight.W_600, color=T.TEXT), badge], spacing=8, wrap=True),
                                W.caption(f"{mascot.animal} · {mascot.philosopher}"),
                                W.body(mascot.story, dim=True, size=13),
                            ],
                            spacing=4,
                            expand=True,
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                col={"xs": 12, "md": 6},
                border_color=W.fade(mascot.color, 0.6) if mascot.is_app else T.BORDER,
            )
        )
    names = [
        ft.Row([ft.Container(W.body(item.name, size=14, weight=ft.FontWeight.W_600), width=150), ft.Column([W.body(item.meaning, size=13), W.caption(item.source)], spacing=0, expand=True)], vertical_alignment=ft.CrossAxisAlignment.START)
        for item in NOMENCLATURE.values()
    ]
    return W.screen(
        [
            _header(ctx, "info", f"versione {__version__}"),
            UpdatesPanel(ctx).build(),
            W.panel(
                ft.Column(
                    [
                        W.title_with_nickname(APP_NAME, APP_TAGLINE, size=24),
                        W.body(APP_MOTTO, italic=True),
                        W.body(
                            "Il nome viene dallo Zibaldone di pensieri di Giacomo Leopardi (1817–1832), un quaderno di migliaia di pagine "
                            "dove ogni cosa trovava posto. «One» sta per tutto in uno.",
                            dim=True,
                        ),
                    ],
                    spacing=8,
                )
            ),
            W.section_label("Le mascotte", "una per area della vita"),
            ft.ResponsiveRow(cards, spacing=12, run_spacing=12),
            W.section_label("I nomi"),
            W.panel(ft.Column(names, spacing=10)),
        ],
        ctx.wide,
    )
