"""Voci · Pensieri: the list of entries with filters, and one entry in detail."""

from datetime import date
from typing import Any, List

import flet as ft

from zibaldone.core import secrets
from zibaldone.core.brand import mascot_for
from zibaldone.core.links import is_person_template
from zibaldone.storage.database import StoreError
from zibaldone.ui import forms
from zibaldone.ui import theme as T
from zibaldone.ui import viewmodels as vm
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import Route, section
from zibaldone.ui.views.common import choose_template, not_found, pick_date
from zibaldone.ui.views.media_view import attachment_list
from zibaldone.ui.views.vault import unlock_secrets, vault_of

ALL = "*"
SEARCH_NOTE = "Cerca in tutti i blocchi. Più parole: le voci che le hanno tutte; «\"frase esatta\"», parol* per l'inizio, -parola per escluderla."


class EntryList:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self.query: vm.EntryQuery = ctx.memory.setdefault("entries_query", vm.EntryQuery())
        self.list_column = ft.Column(spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.count = W.caption("")
        self.from_button = W.secondary_button("", lambda _: self.pick("day_from"), icon="EVENT")
        self.to_button = W.secondary_button("", lambda _: self.pick("day_to"), icon="EVENT")
        self.clear_dates = W.icon_button("CLOSE", self.reset_dates, "Togli le date")

    def build(self) -> ft.Control:
        info = section("voci")
        with self.ctx.store() as store:
            templates = store.list_templates()
        options = [(ALL, "Tutti i modelli")] + [(template.slug, template.name) for template in templates]
        template_menu = W.dropdown(options, self.query.template or ALL, label="Modello", on_select=self.template_changed, expand=True)
        area_menu = W.dropdown(
            [(ALL, "Tutte le aree")] + [(key, label) for key, label in vm.area_options()[1:]],
            self.query.area or ALL,
            label="Area",
            on_select=self.area_changed,
            expand=True,
        )
        search = W.text_input(self.query.text, hint_text="Cerca nelle voci", prefix_icon=ft.Icons.SEARCH, on_change=self.text_changed)
        filters = W.panel(
            ft.Column(
                [
                    ft.ResponsiveRow(
                        [
                            ft.Container(ft.Row([template_menu]), col={"xs": 12, "md": 4}),
                            ft.Container(ft.Row([area_menu]), col={"xs": 12, "md": 3}),
                            ft.Container(search, col={"xs": 12, "md": 5}),
                        ],
                        spacing=12,
                        run_spacing=12,
                    ),
                    ft.Row([self.from_button, self.to_button, self.clear_dates], wrap=True, spacing=8, run_spacing=8),
                    W.caption(SEARCH_NOTE),
                ],
                spacing=12,
            ),
            padding=14,
        )
        self.reload(update=False)
        return W.screen(
            [
                W.screen_header(info.label, info.nickname, "tutto ciò che hai scritto, dal più recente", actions=[W.primary_button("Nuova voce", lambda _: choose_template(self.ctx), icon="ADD"), W.secondary_button("Grafo", lambda _: self.ctx.go("/grafo"), icon="HUB")]),
                filters,
                self.count,
                self.list_column,
            ],
            self.ctx.wide,
        )

    # — filters —

    def template_changed(self, event: Any) -> None:
        value = event.control.value
        self.query.template = "" if value in (None, ALL) else value
        self.reload()

    def area_changed(self, event: Any) -> None:
        value = event.control.value
        self.query.area = "" if value in (None, ALL) else value
        self.reload()

    def text_changed(self, event: Any) -> None:
        self.query.text = event.control.value or ""
        self.reload()

    def pick(self, which: str) -> None:
        def chosen(day: date) -> None:
            setattr(self.query, which, day.isoformat())
            self.reload()

        pick_date(self.ctx, getattr(self.query, which), chosen, "Dal giorno" if which == "day_from" else "Al giorno")

    def reset_dates(self, _: Any) -> None:
        self.query.day_from = self.query.day_to = ""
        self.reload()

    def reload(self, update: bool = True) -> None:
        today = self.ctx.now().date()
        with self.ctx.store() as store:
            rows = vm.list_entry_rows(store, self.query, today)
        self.from_button.content = f"Dal {vm.short_date(self.query.day_from, today)}" if self.query.day_from else "Dal giorno…"
        self.to_button.content = f"Al {vm.short_date(self.query.day_to, today)}" if self.query.day_to else "Al giorno…"
        self.clear_dates.visible = bool(self.query.day_from or self.query.day_to)
        self.count.value = "nessuna voce" if not rows else ("1 voce" if len(rows) == 1 else f"{len(rows)} voci")
        if rows:
            self.list_column.controls = [
                W.entry_tile(row.title, f"{row.template_name} · {row.day_label}", row.summary, row.icon, row.color, lambda _, entry_id=row.id: self.ctx.go(f"/voci/{entry_id}"))
                for row in rows
            ]
        else:
            empty = "Nessuna voce con questi filtri." if (self.query.template or self.query.area or self.query.text or self.query.day_from or self.query.day_to) else "Non hai ancora scritto nulla. Comincia da Oggi, o con «Nuova voce»."
            self.list_column.controls = [W.empty_state(empty, "EDIT_NOTE")]
        if update:
            self.ctx.update()


def build_list(ctx: AppContext, route: Route) -> ft.Control:
    return EntryList(ctx).build()


# * — one entry —


def build_detail(ctx: AppContext, route: Route) -> ft.Control:
    today = ctx.now().date()
    try:
        with ctx.store() as store:
            detail = vm.entry_detail(store, route.arg, today)
    except StoreError:
        return not_found(ctx, "Questa voce non esiste più: forse l'hai cancellata.")

    entry_id = detail.entry.id

    def delete() -> None:
        with ctx.store() as store:
            store.delete_entry(entry_id)
        ctx.data_changed()
        ctx.toast("Voce cancellata.")
        ctx.back()

    def ask_delete(_: Any) -> None:
        ctx.confirm(
            "Cancellare questa voce?",
            f"«{detail.title}» sparirà da questo dispositivo. Le istantanee di Mnemosyne già fatte la conservano.",
            "Cancella",
            delete,
        )

    meta = f"Scritta il {detail.created_label}"
    if detail.updated_label:
        meta += f" · modificata il {detail.updated_label}"
    blocks: List[ft.Control] = []
    for block in detail.blocks:
        blocks.append(ft.Column([W.caption(block.label), _block_view(ctx, block)], spacing=6))
    if not blocks:
        blocks.append(W.body("Questa voce è vuota.", dim=True))
    return W.screen(
        [
            W.screen_header(
                detail.title,
                detail.template.name if detail.has_own_title else "",
                detail.day_label,
                on_back=ctx.back,
                actions=[
                    W.primary_button("Modifica", lambda _: ctx.go(f"/voci/{entry_id}/modifica"), icon="EDIT"),
                    *([W.secondary_button(f"Tutto di {detail.title}", lambda _: ctx.go(f"/persone/{entry_id}"), icon="PERSON_SEARCH")] if is_person_template(detail.template) else []),
                    W.secondary_button("Nel grafo", lambda _: ctx.go(f"/grafo/{entry_id}"), icon="HUB"),
                    W.secondary_button("Cancella", ask_delete, icon="DELETE_OUTLINE"),
                ],
            ),
            *_area_pills(ctx, detail),
            W.panel(ft.Column(blocks, spacing=18)),
            *_related_panels(ctx, detail),
            W.caption(meta),
        ],
        ctx.wide,
    )


def _area_pills(ctx: AppContext, detail: vm.EntryDetail) -> List[ft.Control]:
    """The life areas of the entry (0.2.0); a tap opens the area."""
    if not detail.areas:
        return []
    chips: List[ft.Control] = [
        ft.Container(W.pill(label, color, icon="DONUT_LARGE"), on_click=lambda _, key=key: ctx.go(f"/aree/{key}"), border_radius=999, ink=True)
        for key, label, color in detail.areas
    ]
    return [ft.Row(chips, wrap=True, spacing=6, run_spacing=6)]


def _related_panels(ctx: AppContext, detail: vm.EntryDetail) -> List[ft.Control]:
    """Who links to this entry and who names it without a link (0.1.2)."""
    panels: List[ft.Control] = []
    groups = [
        ("Citata da", detail.backlinks, "LINK", ""),
        ("La nominano senza collegamento", detail.mentions, "FORMAT_QUOTE", f"Per collegarle scrivi [[{detail.title}]] nel loro testo."),
    ]
    for label, related, icon, note in groups:
        if not related:
            continue
        rows: List[ft.Control] = [W.body(f"{label} ({len(related)})", size=16, weight=ft.FontWeight.W_600)]
        for item in related:
            rows.append(W.entry_tile(item.title, item.detail, item.excerpt, icon, T.ACCENT, lambda _, linked=item.id: ctx.go(f"/voci/{linked}")))
        if note:
            rows.append(W.caption(note))
        panels.append(W.panel(ft.Column(rows, spacing=10)))
    return panels


def _secret_view(ctx: AppContext, value: str) -> ft.Control:
    """A secret: closed, with «Apri»; opened, its text until the vault closes again."""
    vault, now = vault_of(ctx), ctx.now()
    try:
        level = secrets.value_level(value)
        text = vault.reveal(value, now) if vault.can_open(value, now) else None
    except secrets.SecretsError as error:
        return W.caption(f"{secrets.LOCKED_TEXT} · {error}", color=T.ERROR)
    if text is not None:
        def close(_: Any) -> None:
            vault.lock()
            ctx.refresh()

        return ft.Column(
            [
                W.body(text, selectable=True),
                ft.Row([W.caption(f"aperto: si richiude da solo dopo {secrets.VAULT_MINUTES} minuti"), W.text_button("Richiudi", close, icon="LOCK", color=T.TEXT_DIM)], wrap=True, spacing=8),
            ],
            spacing=4,
        )
    return ft.Row(
        [W.pill(f"cifrato · {level}", T.ACCENT_2, icon="LOCK_OUTLINE"), W.text_button("Apri", lambda _: unlock_secrets(ctx, [value], ctx.refresh), icon="LOCK_OPEN")],
        wrap=True,
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _block_view(ctx: AppContext, block: vm.DetailBlock) -> ft.Control:
    kind, value, options = block.type, block.value, block.options
    if kind == "secret":
        return _secret_view(ctx, value)
    if kind == "media":
        return attachment_list(ctx, value)
    if kind == "rating":
        return W.stars(value, int(options.get("max", 5)), size=22)
    if kind == "tags":
        return ft.Row([W.tag_chip(tag) for tag in value], wrap=True, spacing=6, run_spacing=6)
    if kind == "date":
        try:
            return W.body(vm.italian_date(date.fromisoformat(value)))
        except ValueError:
            return W.body(str(value))
    if kind == "checklist":
        rows = []
        for item in value:
            done = bool(item.get("done"))
            rows.append(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.CHECK_BOX if done else ft.Icons.CHECK_BOX_OUTLINE_BLANK, color=T.ACCENT if done else T.TEXT_DIM, size=20),
                        ft.Text(item.get("text", ""), color=T.TEXT_DIM if done else T.TEXT, size=14, expand=True),
                    ],
                    spacing=8,
                )
            )
        return ft.Column(rows, spacing=4)
    if kind == "scale":
        low, high = int(options.get("min", 0)), int(options.get("max", 10))
        mascot = mascot_for(block.key)
        color = mascot.color if mascot else T.ACCENT
        low_text, high_text = forms.scale_captions_from(options)
        fraction = (value - low) / (high - low) if high > low else 0
        head: List[ft.Control] = [ft.Text(f"{value}/{high}", size=16, weight=ft.FontWeight.W_600, color=T.TEXT)]
        if mascot:
            head.insert(0, W.mascot_avatar(mascot, 26))
        return ft.Column(
            [
                ft.Row(head, spacing=8),
                W.meter(fraction, color),
                ft.Row([W.caption(low_text), W.caption(high_text)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ],
            spacing=6,
        )
    if kind == "choice":
        return ft.Row([W.pill(str(value), T.ACCENT)], wrap=True)
    if kind == "progress":
        fraction = forms.progress_fraction(value)
        status = vm.PROGRESS_STATUSES.get(value.get("status", ""), "")
        counter = ""
        if "current" in value:
            counter = forms.format_number(value["current"])
            if "total" in value:
                counter += f"/{forms.format_number(value['total'])}"
            if options.get("unit"):
                counter += f" {options['unit']}"
        return W.labelled_meter(status, fraction, counter)
    if kind == "link":
        return ft.Column(
            [W.text_button(title, lambda _, linked=linked_id: ctx.go(f"/voci/{linked}"), icon="LINK") for linked_id, title in block.links],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        )
    return W.body(block.text, selectable=True)
