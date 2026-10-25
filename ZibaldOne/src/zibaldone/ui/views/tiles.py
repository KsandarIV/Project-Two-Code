"""The 0.2.8 tiles of Oggi: Ricorrenze, Obiettivi, Bilancio and a saved view. Each returns a control, or None when it has nothing to show."""

from datetime import date, datetime
from typing import Any, List, Optional

import flet as ft

from zibaldone.core import finance as F
from zibaldone.core import secrets
from zibaldone.core.areas import area_label, goals_overview
from zibaldone.core.people import load_people, occasions
from zibaldone.core.views import ViewError, load_views, run_view
from zibaldone.ui import services
from zibaldone.ui import theme as T
from zibaldone.ui import viewmodels as vm
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.views.vault import unlock_secrets, vault_of

LIMIT = 5


def in_days_label(days: int) -> str:
    return "oggi" if days == 0 else "domani" if days == 1 else f"tra {days} giorni"


def _tile(title: str, nickname: str, rows: List[ft.Control], footer: Optional[ft.Control] = None) -> ft.Control:
    parts: List[ft.Control] = [W.section_label(title, nickname), W.panel(ft.Column(rows, spacing=6))]
    if footer is not None:
        parts.append(ft.Row([footer], alignment=ft.MainAxisAlignment.END))
    return ft.Column(parts, spacing=8)


def _line(title: str, note: str, on_click: Any, trailing: Optional[ft.Control] = None, meter: Optional[ft.Control] = None) -> ft.Control:
    text: List[ft.Control] = [W.body(title, size=15, weight=ft.FontWeight.W_600), W.caption(note)]
    if meter is not None:
        text.append(meter)
    row: List[ft.Control] = [ft.Column(text, spacing=3, expand=True)]
    if trailing is not None:
        row.append(trailing)
    return ft.Container(ft.Row(row, vertical_alignment=ft.CrossAxisAlignment.CENTER), padding=ft.Padding.symmetric(vertical=6, horizontal=2), on_click=on_click, ink=True, border_radius=T.RADIUS_SMALL)


def shortcuts_row(ctx: AppContext, store: Any) -> Optional[ft.Control]:
    """The templates pinned from Modelli: one tap opens a new entry. A template that is gone is skipped."""
    chips = []
    for slug in services.shortcuts(ctx.folder):
        template = store.find_template(slug)
        if template is not None:
            chips.append(
                ft.Container(
                    ft.Row([W.template_badge(template.icon, T.color_or(template.color), 28), W.body(template.name, size=13)], spacing=8, tight=True),
                    padding=ft.Padding.only(left=4, right=12, top=4, bottom=4),
                    border=ft.Border.all(1, T.BORDER),
                    border_radius=T.RADIUS_SMALL,
                    on_click=lambda _, slug=slug: ctx.go(f"/scrivi/{slug}"),
                    ink=True,
                    tooltip=f"Nuova voce: {template.name}",
                )
            )
    return ft.Row(chips, wrap=True, spacing=8, run_spacing=8) if chips else None


def occasions_tile(ctx: AppContext, store: Any, today: date) -> Optional[ft.Control]:
    found = occasions(load_people(store), today)
    if not found:
        return None
    rows = []
    for item in found[:LIMIT]:
        note = f"{item.kind} · {in_days_label(item.in_days)}" + (f" · {item.turning} anni" if item.turning else "")
        rows.append(_line(item.name, note, lambda _, person_id=item.person_id: ctx.go(f"/persone/{person_id}")))
    return _tile("Ricorrenze", "Kairos", rows)


def goals_tile(ctx: AppContext, store: Any, today: date) -> Optional[ft.Control]:
    found = goals_overview(store, today)
    if not found:
        return None
    rows = []
    for line in found[:LIMIT]:
        goal = line.goal
        if line.days_left is None:
            when = "senza scadenza"
        elif line.days_left < 0:
            when = f"la scadenza era il {goal.deadline.day:02d}/{goal.deadline.month:02d}"
        else:
            when = in_days_label(line.days_left)
        percent = goal.percent if goal.percent is not None else 0
        rows.append(
            _line(goal.title, f"{area_label(line.area)} · {when} · {percent}%", lambda _, area=line.area: ctx.go(f"/aree/{area}"), meter=W.meter(percent / 100, T.ACCENT))
        )
    return _tile("Obiettivi", "Telos", rows)


def balance_tile(ctx: AppContext, store: Any, now: datetime) -> Optional[ft.Control]:
    """Balance and month with the vault open; with the accounts closed only the way to open them."""
    if not F.installed(store):
        return None
    sealed = F.sealed_values(store)
    vault = vault_of(ctx)
    ledger = None
    if not sealed or (vault.is_open(now) and all(vault.can_open(value, now) for value in sealed)):
        try:
            ledger = F.load(store, lambda value: vault.reveal(value, now))
        except secrets.SecretsError:
            ledger = None
    if ledger is None:
        button = W.primary_button("Apri con il PIN", lambda _: unlock_secrets(ctx, sealed, ctx.refresh), icon="LOCK_OPEN")
        return _tile("Bilancio", "Oikonomia", [W.body("I conti sono chiusi: gli importi si leggono solo dopo aver inserito il PIN.", dim=True)], button)
    if ledger.is_empty:
        return None
    month = F.month_summary(ledger, now.year, now.month)
    rows = [
        _line(f"Saldo {F.format_amount(F.balance(ledger))}", f"Questo mese: entrate {F.format_amount(month.income)}, spese {F.format_amount(month.spent)}", lambda _: ctx.go("/finanze")),
    ]
    return _tile("Bilancio", "Oikonomia", rows)


def view_tile(ctx: AppContext, store: Any, view_id: str, today: date) -> Optional[ft.Control]:
    """«Vista: NOME»: the first results of a saved view; None when the view is gone."""
    view = next((item for item in load_views(store) if item.id == view_id), None)
    if view is None:
        return None
    try:
        found = run_view(store, view)
    except ViewError as problem:
        return _tile(f"Vista: {view.name}", "Lente", [W.caption(str(problem))])
    templates = {template.slug: template for template in store.list_templates()}
    rows: List[ft.Control] = []
    for entry in found[:LIMIT]:
        template = templates.get(entry.template)
        if template is not None:
            row = vm.entry_row(entry, template, today)
            rows.append(W.entry_tile(row.title, row.template_name, row.summary, row.icon, row.color, lambda _, entry_id=row.id: ctx.go(f"/voci/{entry_id}")))
    if not rows:
        rows = [W.caption("Nessuna voce corrisponde, per ora.")]
    footer = W.text_button(f"Vedi tutti ({len(found)})" if len(found) > LIMIT else "Apri la vista", lambda _: ctx.go(f"/viste/{view.id}"), icon="ARROW_FORWARD")
    return _tile(f"Vista: {view.name}", "Lente", rows, footer)
