"""`zbone finanze …`: Oikonomia (0.2.6), the household accounts. Amounts are sealed: reading asks the PIN or the passphrase."""

from datetime import date, datetime
from typing import Dict, Optional

import typer

from zibaldone.cli.common import fail, open_store
from zibaldone.cli.secret_cmd import unlock
from zibaldone.core import finance as F
from zibaldone.core import secrets
from zibaldone.core.people import load_people
from zibaldone.storage import keys
from zibaldone.storage.database import StoreError
from zibaldone.storage.paths import data_dir

finance_app = typer.Typer(help="Oikonomia: conti, spese, budget, obiettivi, debiti e spese condivise (gli importi sono cifrati).", no_args_is_help=False)
MONTHS = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")


def _opened() -> tuple:
    """(ledger, names of the people): asks the PIN when it is enough for the amounts."""
    folder = data_dir()
    with open_store() as store:
        if not F.installed(store):
            fail(f"manca la Scuola «Oikonomia · Finanze»: zbone pack install {F.PACK_NAME}")
        sealed = F.sealed_values(store)
        if sealed and not keys.is_configured(folder):
            fail("manca keys.json: senza la chiave gli importi non si aprono")
        vault = unlock(folder, sealed) if sealed else secrets.Vault()
        try:
            ledger = F.load(store, lambda value: vault.reveal(value, datetime.now()))
        except secrets.SecretsError as error:
            fail(str(error))
        names: Dict[str, str] = {person.entry.id: person.name for person in load_people(store)}
    return ledger, names


@finance_app.callback(invoke_without_command=True)
def summary(ctx: typer.Context, month: Optional[str] = typer.Option(None, "--mese", help="AAAA-MM; di base il mese in corso")) -> None:
    """Saldo, mese per categoria con i budget, obiettivi."""
    if ctx.invoked_subcommand is not None:
        return
    today = date.today()
    try:
        year, number = (int(part) for part in month.split("-")) if month else (today.year, today.month)
        if not 1 <= number <= 12:
            raise ValueError
    except ValueError:
        fail("il mese si scrive AAAA-MM, per esempio 2026-10")
    ledger, _ = _opened()
    typer.echo(f"Saldo: {F.format_amount(F.balance(ledger))}")
    for account in ledger.accounts:
        typer.echo(f"  {account.name}: {F.format_amount(F.account_balance(ledger, account))}")
    result = F.month_summary(ledger, year, number)
    typer.echo(f"\n{MONTHS[number - 1].capitalize()} {year}: entrate {F.format_amount(result.income)}, spese {F.format_amount(result.spent)}, resta {F.format_amount(result.net)}")
    for line in result.lines:
        budget = f" su {F.format_amount(line.budget)}" + (" · SFORATO" if line.spent > line.budget else "") if line.budget is not None else ""
        typer.echo(f"  {line.category}: {F.format_amount(line.spent)}{budget}")
    for goal in ledger.goals:
        typer.echo(f"\nObiettivo «{goal.name}»: {F.format_amount(goal.saved)} su {F.format_amount(goal.target)} ({round(goal.fraction * 100)}%)")
    for problem in ledger.problems:
        typer.echo(f"Non letto: {problem}", err=True)


def _quick(kind: str, amount: str, text: str, category: str, day: Optional[str]) -> None:
    try:
        with open_store() as store:
            entry = F.add_movement(store, kind, amount, text, category, day=day)
    except (F.FinanceError, StoreError, ValueError) as error:
        fail(str(error))
    typer.echo(f"{'Spesa' if kind == F.SPENT else 'Entrata'} registrata ({entry.day}): {text.strip()}. L'importo è cifrato.")


@finance_app.command("spesa")
def spent(amount: str = typer.Argument(..., metavar="IMPORTO"), text: str = typer.Argument(..., metavar="CHE_COSA"), category: str = typer.Option("", "--categoria", help=", ".join(F.CATEGORIES)), day: Optional[str] = typer.Option(None, "--giorno", help="AAAA-MM-GG")) -> None:
    """Registra una spesa (non serve il PIN)."""
    _quick(F.SPENT, amount, text, category, day)


@finance_app.command("entrata")
def earned(amount: str = typer.Argument(..., metavar="IMPORTO"), text: str = typer.Argument(..., metavar="CHE_COSA"), category: str = typer.Option("", "--categoria", help=", ".join(F.CATEGORIES)), day: Optional[str] = typer.Option(None, "--giorno", help="AAAA-MM-GG")) -> None:
    """Registra un'entrata (non serve il PIN)."""
    _quick(F.EARNED, amount, text, category, day)


@finance_app.command("debiti")
def debts() -> None:
    """Chi deve cosa a chi, con i debiti e i crediti ancora aperti."""
    ledger, names = _opened()
    totals = F.loan_balances(ledger)
    if not totals:
        typer.echo("Nessun debito o credito aperto.")
        return
    for person, total in totals.items():
        name = names.get(person, "una persona")
        typer.echo(f"{name} ti deve {F.format_amount(total)}" if total > 0 else f"Devi {F.format_amount(-total)} a {name}")
    typer.echo("")
    for loan in (loan for loan in ledger.loans if loan.open):
        who = names.get(loan.person_id, "una persona")
        typer.echo(f"  {loan.id[:8]}  {loan.reason} · {who} · {'mi deve' if loan.direction == F.OWED_TO_ME else 'gli devo'} {F.format_amount(loan.amount)}")


@finance_app.command("salda")
def settle(reference: str = typer.Argument(..., metavar="ID")) -> None:
    """Segna come saldato un debito o un credito (ID dalla lista di `zbone finanze debiti`)."""
    try:
        with open_store() as store:
            entry = store.get_entry(reference)
            if entry.template != F.LOAN:
                fail("questa voce non è un debito o un credito")
            F.settle_loan(store, entry.id)
    except (F.FinanceError, StoreError) as error:
        fail(str(error))
    typer.echo("Segnato come saldato.")


@finance_app.command("ricorrenti")
def recurring(register: bool = typer.Option(False, "--registra", help="scrivi le scadenze arrivate: la tua quota e quello che devono gli altri")) -> None:
    """Le spese ricorrenti e le scadenze ancora da registrare."""
    ledger, names = _opened()
    today = date.today()
    if not ledger.recurring:
        typer.echo("Nessuna spesa ricorrente.")
        return
    done = 0
    for item in ledger.recurring:
        due = F.due_dates(item, today)
        with_whom = ", ".join(names.get(person, "?") for person in item.people)
        typer.echo(f"{item.text} · {item.frequency.lower()} · {F.format_amount(item.total)}" + (f" con {with_whom}" if with_whom else "") + (f" · da registrare: {', '.join(day.strftime('%d/%m/%Y') for day in due)}" if due else " · in regola"))
        if register:
            current = item
            for day in due:
                try:
                    with open_store() as store:
                        F.register_recurring(store, current, day)
                except (F.FinanceError, StoreError) as error:
                    fail(str(error))
                current = F.Recurring(item.id, item.text, item.total, item.frequency, item.start, item.people, item.category, day)
                done += 1
    if register:
        typer.echo(f"Registrate {done} scadenze.")
