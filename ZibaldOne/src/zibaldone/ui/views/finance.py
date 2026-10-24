"""Oikonomia (0.2.6): the household accounts. The amounts are sealed; this screen opens them with the PIN and adds them up in memory."""

from datetime import date
from typing import Any, Callable, Dict, List, Optional, Tuple

import flet as ft

from zibaldone.core import finance as F
from zibaldone.core import secrets
from zibaldone.core.people import load_people
from zibaldone.storage.database import StoreError
from zibaldone.ui import services
from zibaldone.ui import theme as T
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import Route
from zibaldone.ui.views.vault import unlock_secrets, vault_of

MONTHS = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")
NEW_BUTTONS = (
    ("Conto", F.ACCOUNT, "ACCOUNT_BALANCE_WALLET_OUTLINED"),
    ("Budget", F.BUDGET, "DONUT_SMALL"),
    ("Obiettivo", F.GOAL, "SAVINGS_OUTLINED"),
    ("Debito o credito", F.LOAN, "HANDSHAKE_OUTLINED"),
    ("Spesa ricorrente", F.RECURRING, "AUTORENEW"),
    ("Lista della spesa", F.SHOPPING, "SHOPPING_CART_OUTLINED"),
)


def month_of(arg: str, today: date) -> Tuple[int, int]:
    """(year, month) of a route argument 'AAAA-MM', else of today."""
    if arg:
        year, month = arg.split("-")
        return int(year), int(month)
    return today.year, today.month


def shift_month(year: int, month: int, step: int) -> str:
    year, month = divmod(year * 12 + month - 1 + step, 12)
    return f"{year}-{month + 1:02d}"


def _install(ctx: AppContext) -> Callable[[Any], None]:
    def install(_: Any) -> None:
        from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install

        try:
            with ctx.store() as store:
                for name in ("persone", F.PACK_NAME):
                    pack = find_builtin_pack(name)
                    if pack is not None:
                        apply_install(plan_install(pack, store), store)
        except (StoreError, ValueError) as problem:
            ctx.toast(str(problem), error=True)
            return
        ctx.data_changed()
        ctx.toast("Oikonomia · Finanze installato.")
        ctx.refresh()

    return install


def _titled(title: str, rows: List[ft.Control], note: str = "") -> ft.Control:
    head: List[ft.Control] = [W.body(title, size=16, weight=ft.FontWeight.W_600)]
    if note:
        head.append(W.caption(note))
    return W.panel(ft.Column(head + rows, spacing=10))


def build(ctx: AppContext, route: Route) -> ft.Control:
    today = ctx.now().date()
    year, month = month_of(route.arg, today)
    with ctx.store() as store:
        installed = F.installed(store)
        sealed = F.sealed_values(store) if installed else []
        names = {person.entry.id: person.name for person in load_people(store)} if installed else {}
    header = W.screen_header("Finanze", "Oikonomia", "conti, spese, budget, obiettivi e debiti: gli importi sono cifrati", on_back=ctx.back)
    if not installed:
        return W.screen(
            [
                header,
                W.panel(
                    ft.Column(
                        [
                            W.body("Conti, spese ed entrate, budget, obiettivi di risparmio, debiti e crediti con le persone, spese condivise e lista della spesa arrivano con la Scuola «Oikonomia · Finanze»."),
                            ft.Row([W.primary_button("Installa «Oikonomia · Finanze»", _install(ctx), icon="DOWNLOAD")], alignment=ft.MainAxisAlignment.END),
                        ],
                        spacing=10,
                    ),
                    border_color=W.fade(T.ACCENT, 0.45),
                ),
            ],
            ctx.wide,
        )
    controls: List[ft.Control] = [header]
    if not services.encryption_on(ctx.folder):
        controls.append(
            W.panel(
                ft.Column(
                    [
                        W.body("Gli importi si cifrano con la chiave dei backup, che non è ancora attiva."),
                        W.caption("Attivala in Impostazioni · Mnemosyne: poi potrai scrivere e leggere i conti."),
                        ft.Row([W.primary_button("Apri Mnemosyne", lambda _: ctx.go("/organon/mnemosyne"), icon="HISTORY")], alignment=ft.MainAxisAlignment.END),
                    ],
                    spacing=10,
                ),
                border_color=W.fade(T.ACCENT_2, 0.6),
            )
        )
        return W.screen(controls, ctx.wide)
    vault = vault_of(ctx)
    now = ctx.now()
    if sealed and not (vault.is_open(now) and all(vault.can_open(value, now) for value in sealed)):
        return W.screen(controls + [_locked(ctx, sealed)], ctx.wide)
    try:
        with ctx.store() as store:
            ledger = F.load(store, lambda value: vault.reveal(value, ctx.now()))
    except secrets.SecretsError:
        return W.screen(controls + [_locked(ctx, sealed)], ctx.wide)
    return W.screen(controls + _open(ctx, ledger, names, year, month, today), ctx.wide)


def _locked(ctx: AppContext, sealed: List[str]) -> ft.Control:
    return W.panel(
        ft.Column(
            [
                W.body("I conti sono chiusi: gli importi si leggono solo dopo aver inserito il PIN."),
                W.caption(f"Si richiudono da soli dopo {secrets.VAULT_MINUTES} minuti senza usarli."),
                ft.Row([W.primary_button("Apri i conti", lambda _: unlock_secrets(ctx, sealed, ctx.refresh), icon="LOCK_OPEN")], alignment=ft.MainAxisAlignment.END),
            ],
            spacing=10,
        ),
        border_color=W.fade(T.ACCENT, 0.45),
    )


def _open(ctx: AppContext, ledger: F.Ledger, names: Dict[str, str], year: int, month: int, today: date) -> List[ft.Control]:
    def close(_: Any) -> None:
        vault_of(ctx).lock()
        ctx.toast("Conti chiusi.")
        ctx.refresh()

    actions = ft.Row(
        [
            W.primary_button("Spesa", lambda _: movement_dialog(ctx, F.SPENT), icon="REMOVE"),
            W.primary_button("Entrata", lambda _: movement_dialog(ctx, F.EARNED), icon="ADD"),
            W.secondary_button("Richiudi", close, icon="LOCK"),
        ],
        wrap=True,
        spacing=8,
        run_spacing=8,
    )
    controls: List[ft.Control] = [actions, _balance(ledger), _month(ctx, ledger, year, month)]
    if ledger.goals:
        controls.append(_goals(ctx, ledger))
    controls += [panel for panel in (_loans(ctx, ledger, names), _recurring(ctx, ledger, names, today), _lists(ctx, ledger)) if panel is not None]
    if ledger.problems:
        controls.append(W.caption(f"{len(ledger.problems)} voci non lette: " + "; ".join(ledger.problems[:2]), color=T.ERROR))
    controls.append(
        ft.Column(
            [W.section_label("Aggiungi")]
            + [
                ft.Row(
                    [W.secondary_button(label, lambda _, slug=slug: ctx.go(f"/scrivi/{slug}/finanze"), icon=icon) for label, slug, icon in NEW_BUTTONS],
                    wrap=True,
                    spacing=8,
                    run_spacing=8,
                )
            ],
            spacing=6,
        )
    )
    controls.append(W.caption("Le somme si fanno qui, in memoria: gli importi restano cifrati e non escono dal dispositivo."))
    return controls


def _balance(ledger: F.Ledger) -> ft.Control:
    total = F.balance(ledger)
    rows: List[ft.Control] = [ft.Text(F.format_amount(total), size=28, weight=ft.FontWeight.W_600, color=T.ERROR if total < 0 else T.TEXT)]
    if not ledger.accounts and not ledger.movements:
        rows.append(W.caption("Scrivi una spesa o un'entrata, o aggiungi un conto con il suo saldo iniziale."))
    for account in ledger.accounts:
        rows.append(ft.Row([W.body(account.name, size=13), W.caption(F.format_amount(F.account_balance(ledger, account)))], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
    return _titled("Saldo", rows)


def _month(ctx: AppContext, ledger: F.Ledger, year: int, month: int) -> ft.Control:
    summary = F.month_summary(ledger, year, month)
    now = ctx.now()
    at_now = (year, month) == (now.year, now.month)
    nav = ft.Row(
        [
            W.icon_button("CHEVRON_LEFT", lambda _: ctx.go(f"/finanze/{shift_month(year, month, -1)}"), "Mese prima", color=T.TEXT),
            W.body(f"{MONTHS[month - 1].capitalize()} {year}", size=15, weight=ft.FontWeight.W_600),
            W.icon_button("CHEVRON_RIGHT", lambda _: ctx.go(f"/finanze/{shift_month(year, month, 1)}"), "Mese dopo", color=T.TEXT, disabled=at_now),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )
    rows: List[ft.Control] = [
        nav,
        ft.Row([W.pill(f"Entrate {F.format_amount(summary.income)}"), W.pill(f"Spese {F.format_amount(summary.spent)}"), W.pill(f"Resta {F.format_amount(summary.net)}", T.ACCENT)], wrap=True, spacing=6, run_spacing=6),
    ]
    for line in summary.lines:
        if line.budget is None:
            rows.append(W.labelled_meter(line.category, None, F.format_amount(line.spent)))
            continue
        over = line.spent > line.budget
        rows.append(W.labelled_meter(line.category, line.fraction, f"{F.format_amount(line.spent)} su {F.format_amount(line.budget)}", T.ERROR if over else T.ACCENT))
    if not summary.lines:
        rows.append(W.caption("Nessun movimento in questo mese."))
    return _titled("Mese", rows)


def _goals(ctx: AppContext, ledger: F.Ledger) -> ft.Control:
    rows: List[ft.Control] = []
    for goal in ledger.goals:
        rows.append(W.labelled_meter(goal.name, goal.fraction, f"{F.format_amount(goal.saved)} su {F.format_amount(goal.target)}", T.ACCENT_2))
        if goal.due:
            rows.append(W.caption(f"entro il {goal.due.strftime('%d/%m/%Y')}"))
        if goal.left > 0:
            rows.append(ft.Row([W.text_button("Metti da parte", lambda _, goal=goal: save_dialog(ctx, goal), icon="ADD")], alignment=ft.MainAxisAlignment.END))
    return _titled("Obiettivi di risparmio", rows)


def _loans(ctx: AppContext, ledger: F.Ledger, names: Dict[str, str]) -> Optional[ft.Control]:
    open_loans = [loan for loan in ledger.loans if loan.open]
    if not open_loans:
        return None

    def settle(loan_id: str) -> Callable[[Any], None]:
        def handler(_: Any) -> None:
            with ctx.store() as store:
                F.settle_loan(store, loan_id)
            ctx.data_changed()
            ctx.toast("Segnato come saldato.")
            ctx.refresh()

        return handler

    rows: List[ft.Control] = []
    for person_id, total in F.loan_balances(ledger).items():
        name = names.get(person_id, "una persona")
        words = f"{name} ti deve {F.format_amount(total)}" if total > 0 else f"Devi {F.format_amount(-total)} a {name}"
        rows.append(ft.Container(W.body(words, size=15, weight=ft.FontWeight.W_600), on_click=lambda _, pid=person_id: ctx.go(f"/persone/{pid}")))
    for loan in open_loans:
        who = names.get(loan.person_id, "una persona")
        direction = "ti deve" if loan.direction == F.OWED_TO_ME else "tu devi a"
        rows.append(
            ft.Row(
                [ft.Column([W.body(loan.reason, size=13), W.caption(f"{who} {direction} {F.format_amount(loan.amount)}" if loan.direction == F.OWED_TO_ME else f"{direction} {who} {F.format_amount(loan.amount)}")], spacing=0, expand=True), W.text_button("Saldato", settle(loan.id), icon="CHECK")],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
    return _titled("Debiti e crediti", rows)


def _recurring(ctx: AppContext, ledger: F.Ledger, names: Dict[str, str], today: date) -> Optional[ft.Control]:
    if not ledger.recurring:
        return None

    def register(item: F.Recurring, day: date) -> Callable[[Any], None]:
        def handler(_: Any) -> None:
            try:
                with ctx.store() as store:
                    F.register_recurring(store, item, day)
            except (StoreError, F.FinanceError, ValueError) as problem:
                ctx.toast(str(problem), error=True)
                return
            ctx.data_changed()
            ctx.toast(f"Registrata: {item.text} del {day.strftime('%d/%m/%Y')}.")
            ctx.refresh()

        return handler

    rows: List[ft.Control] = []
    for item in ledger.recurring:
        share, mine = F.split_share(item.total, len(item.people))
        with_whom = ", ".join(names.get(person, "?") for person in item.people)
        line = f"{item.frequency.lower()} · {F.format_amount(item.total)}" + (f" con {with_whom}: {F.format_amount(share)} a testa" if item.people else "")
        due = F.due_dates(item, today)
        controls: List[ft.Control] = [ft.Column([W.body(item.text, size=14), W.caption(line)], spacing=0, expand=True)]
        if due:
            more = f" (+{len(due) - 1})" if len(due) > 1 else ""
            controls.append(W.primary_button(f"Registra {due[0].strftime('%d/%m')}{more}", register(item, due[0]), icon="CHECK"))
        else:
            controls.append(W.caption("in regola"))
        rows.append(ft.Row(controls, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8))
        if due and item.people:
            rows.append(W.caption(f"Tua quota {F.format_amount(mine)}; gli altri restano tra i debiti."))
    return _titled("Spese condivise e ricorrenti", rows)


def _lists(ctx: AppContext, ledger: F.Ledger) -> Optional[ft.Control]:
    if not ledger.lists:
        return None
    rows: List[ft.Control] = []
    for shopping in ledger.lists:
        left = f"{len(shopping.open_items)} da comprare" if shopping.open_items else "tutto preso"
        rows.append(
            ft.Container(
                ft.Column([W.body(shopping.title or "Lista", size=14), W.caption(left + (": " + ", ".join(shopping.open_items[:4]) + ("…" if len(shopping.open_items) > 4 else "") if shopping.open_items else ""))], spacing=0),
                on_click=lambda _, entry_id=shopping.id: ctx.go(f"/voci/{entry_id}"),
            )
        )
    return _titled("Liste della spesa", rows)


# * — quick dialogs —


def _amount_field(label: str = "Importo") -> ft.TextField:
    return W.text_input("", label=label, hint_text="es. 12,50", autofocus=True, keyboard_type=ft.KeyboardType.NUMBER)


def movement_dialog(ctx: AppContext, kind: str) -> None:
    """A spesa or entrata in a few taps. Writing needs no PIN: the amount is sealed with the public key."""
    amount = _amount_field()
    text = W.text_input("", label="Che cosa")
    categories = [(name, name) for name in F.CATEGORIES]
    category = W.dropdown(categories, "Stipendio" if kind == F.EARNED else "Cibo", label="Categoria", expand=True)
    error = W.error_text()

    def save(_: Any = None) -> None:
        try:
            canonical = F.canonical_amount(amount.value or "")
            if not (text.value or "").strip():
                raise ValueError("scrivi che cosa è")
            with ctx.store() as store:
                F.add_movement(store, kind, canonical, text.value or "", category.value or "", day=ctx.now().date().isoformat())
        except (ValueError, StoreError) as problem:
            error.value, error.visible = str(problem), True
            ctx.update(error)
            return
        ctx.close_dialog()
        ctx.data_changed()
        ctx.toast("Spesa registrata." if kind == F.SPENT else "Entrata registrata.")
        ctx.refresh()

    text.on_submit = save
    amount.on_submit = save
    ctx.show_dialog(
        ft.AlertDialog(
            modal=True,
            title="Nuova spesa" if kind == F.SPENT else "Nuova entrata",
            content=ft.Container(ft.Column([W.wide(amount), W.wide(text), ft.Row([category]), error], spacing=12, tight=True), width=380),
            actions=[W.text_button("Annulla", ctx.close_dialog, color=T.TEXT), W.primary_button("Salva", save, icon="CHECK")],
        )
    )


def save_dialog(ctx: AppContext, goal: F.Goal) -> None:
    amount = _amount_field("Quanto metti da parte")
    error = W.error_text()

    def save(_: Any = None) -> None:
        try:
            with ctx.store() as store:
                F.add_to_goal(store, goal, amount.value or "")
        except (ValueError, StoreError) as problem:
            error.value, error.visible = str(problem), True
            ctx.update(error)
            return
        ctx.close_dialog()
        ctx.data_changed()
        ctx.toast(f"Messo da parte per «{goal.name}».")
        ctx.refresh()

    amount.on_submit = save
    ctx.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=goal.name,
            content=ft.Container(ft.Column([W.body(f"Mancano {F.format_amount(goal.left)}.", dim=True), W.wide(amount), error], spacing=12, tight=True), width=360),
            actions=[W.text_button("Annulla", ctx.close_dialog, color=T.TEXT), W.primary_button("Aggiungi", save, icon="CHECK")],
        )
    )
