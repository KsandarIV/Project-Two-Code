"""Oikonomia (0.2.6): the household accounts, kept as sealed amounts and added up only in memory.

Every amount of the `finanze` pack is a `secret` block (`core/secrets.py`) with
the option `format`: `importo` (zero or more) or `saldo` (may be negative). So
the numbers are sealed on disk and never reach the search, the exports, the
statistics or an AI: only the words around them (what, when, which category)
are in clear. To add them up the app opens the vault with the PIN, loads the
entries, and the sums live only in memory (`load` → `Ledger`).

Money is a `Decimal` with two decimals; the stored form is `1234.50`, shown as
`1.234,50 €`. Nothing here talks to a bank: the user types the movements.
"""

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from zibaldone.core.secrets import SecretsError

CENT = Decimal("0.01")
MAX_AMOUNT = Decimal("999999999999.99")
FORMATS = ("importo", "saldo")

ACCOUNT, MOVEMENT, BUDGET, GOAL, LOAN, RECURRING, SHOPPING = "conto", "movimento", "budget", "obiettivo_risparmio", "prestito", "spesa_ricorrente", "lista_spesa"
SLUGS = (ACCOUNT, MOVEMENT, BUDGET, GOAL, LOAN, RECURRING, SHOPPING)
PACK_NAME = "finanze"

SPENT, EARNED = "Spesa", "Entrata"
OWED_TO_ME, I_OWE = "Mi deve", "Gli devo"
OPEN, SETTLED = "Aperto", "Saldato"
WEEKLY, MONTHLY, YEARLY = "Ogni settimana", "Ogni mese", "Ogni anno"
CATEGORIES = ("Casa", "Cibo", "Trasporti", "Salute", "Svago", "Studio", "Lavoro", "Regali", "Stipendio", "Altro")
MAX_DUE = 24  # occurrences proposed at once for a recurring expense that was not registered for a long time


class FinanceError(ValueError):
    """A finance action cannot run. Messages are for the user."""


# * — amounts —


def parse_amount(text: Any, negative: bool = False) -> Decimal:
    """'12', '12,5', '1.234,50', '€ 12.50', '1.500' → Decimal with two decimals; ValueError otherwise.

    With both separators the last one is the decimal point; a lone comma is the decimal point;
    a lone dot is the decimal point unless exactly three digits follow it («1.500» = 1500).
    """
    if not isinstance(text, str):
        raise ValueError("l'importo è un numero")
    clean = text.replace("€", "").replace(" ", "").replace(" ", "")
    sign = -1 if clean.startswith("-") else 1
    clean = clean.lstrip("+-")
    if sign < 0 and not negative:
        raise ValueError("l'importo non può essere negativo (per le spese usa «Spesa»)")
    if not clean or not all(char.isdigit() or char in ".," for char in clean):
        raise ValueError(f"non è un importo: «{text.strip()}»")
    comma, dot = clean.rfind(","), clean.rfind(".")
    if comma >= 0 and dot >= 0:
        decimal_at = max(comma, dot)
    elif comma >= 0:
        decimal_at = comma if clean.count(",") == 1 else -1
    elif dot >= 0:
        lone = clean.count(".") == 1
        decimal_at = dot if lone and len(clean) - dot - 1 != 3 else -1
    else:
        decimal_at = -1
    whole, fraction = (clean[:decimal_at], clean[decimal_at + 1 :]) if decimal_at >= 0 else (clean, "")
    whole = whole.replace(".", "").replace(",", "")
    if (fraction and not fraction.isdigit()) or len(fraction) > 2:
        raise ValueError(f"non è un importo: «{text.strip()}» (al massimo due decimali)")
    try:
        value = Decimal(f"{whole or '0'}.{fraction or '0'}") * sign
    except InvalidOperation:
        raise ValueError(f"non è un importo: «{text.strip()}»") from None
    value = value.quantize(CENT)
    if abs(value) > MAX_AMOUNT:
        raise ValueError("importo troppo grande")
    return value


def canonical_amount(text: Any, negative: bool = False) -> str:
    """The stored form: '1234.50'."""
    return f"{parse_amount(text, negative):.2f}"


def format_amount(value: Decimal) -> str:
    """'1.234,50 €' (and '-12,00 €')."""
    sign = "-" if value < 0 else ""
    whole, fraction = f"{abs(value.quantize(CENT)):.2f}".split(".")
    groups: List[str] = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    return f"{sign}{'.'.join([whole, *groups])},{fraction} €"


def split_share(total: Decimal, others: int) -> tuple:
    """(share of each of the others, my share): the total split in `others + 1` equal parts to the cent, my part takes the remainder."""
    share = (total / (others + 1)).quantize(CENT, rounding=ROUND_HALF_UP)
    return share, total - share * others


# * — what the entries hold, once the amounts are opened —


@dataclass(frozen=True)
class Account:
    id: str
    name: str
    start: Decimal


@dataclass(frozen=True)
class Movement:
    id: str
    day: date
    text: str
    kind: str  # SPENT or EARNED
    amount: Decimal
    category: str
    account_id: str

    @property
    def signed(self) -> Decimal:
        return self.amount if self.kind == EARNED else -self.amount


@dataclass(frozen=True)
class Budget:
    id: str
    category: str
    amount: Decimal


@dataclass(frozen=True)
class Goal:
    id: str
    name: str
    target: Decimal
    saved: Decimal
    due: Optional[date]

    @property
    def fraction(self) -> float:
        return min(1.0, float(self.saved / self.target)) if self.target > 0 else 0.0

    @property
    def left(self) -> Decimal:
        return max(Decimal("0.00"), self.target - self.saved)


@dataclass(frozen=True)
class Loan:
    id: str
    reason: str
    person_id: str
    direction: str  # OWED_TO_ME or I_OWE
    amount: Decimal
    open: bool

    @property
    def signed(self) -> Decimal:
        """Positive: they owe me."""
        return self.amount if self.direction == OWED_TO_ME else -self.amount


@dataclass(frozen=True)
class Recurring:
    id: str
    text: str
    total: Decimal
    frequency: str
    start: date
    people: Sequence[str]
    category: str
    last: Optional[date]


@dataclass(frozen=True)
class ShoppingList:
    id: str
    title: str
    open_items: List[str]
    done_items: int


@dataclass
class Ledger:
    accounts: List[Account] = field(default_factory=list)
    movements: List[Movement] = field(default_factory=list)
    budgets: List[Budget] = field(default_factory=list)
    goals: List[Goal] = field(default_factory=list)
    loans: List[Loan] = field(default_factory=list)
    recurring: List[Recurring] = field(default_factory=list)
    lists: List[ShoppingList] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.accounts or self.movements or self.budgets or self.goals or self.loans or self.recurring or self.lists)


def _text(values: Mapping[str, Any], key: str) -> str:
    value = values.get(key)
    return value.strip() if isinstance(value, str) else ""


def _day(values: Mapping[str, Any], key: str) -> Optional[date]:
    try:
        return date.fromisoformat(_text(values, key))
    except ValueError:
        return None


def installed(store: Any) -> bool:
    return all(store.find_template(slug) is not None for slug in SLUGS)


def sealed_values(store: Any) -> List[str]:
    """Every sealed amount of the finance entries: what the vault has to be able to open."""
    found: List[str] = []
    for slug in SLUGS:
        template = store.find_template(slug)
        if template is None:
            continue
        keys = [spec.key for spec in template.blocks if spec.type == "secret"]
        for entry in store.list_entries(template=slug):
            found += [entry.values[key] for key in keys if isinstance(entry.values.get(key), str) and entry.values[key]]
    return found


def load(store: Any, reveal: Callable[[str], str]) -> Ledger:
    """The ledger. `reveal` opens one sealed amount (the vault); an entry that cannot be read goes to `problems`."""
    ledger = Ledger()

    def amount(entry: Any, key: str, negative: bool = False) -> Decimal:
        value = entry.values.get(key)
        if not isinstance(value, str) or not value:
            return Decimal("0.00")
        return parse_amount(reveal(value), negative)

    for slug in SLUGS:
        if store.find_template(slug) is None:
            continue
        template = store.get_template(slug)
        for entry in store.list_entries(template=slug, newest_first=False):
            values = entry.values
            try:
                if slug == ACCOUNT:
                    ledger.accounts.append(Account(entry.id, _text(values, "nome"), amount(entry, "saldo", negative=True)))
                elif slug == MOVEMENT:
                    ledger.movements.append(
                        Movement(entry.id, date.fromisoformat(entry.day), _text(values, "descrizione"), _text(values, "tipo") or SPENT, amount(entry, "importo"), _text(values, "categoria"), (values.get("conto") or [""])[0])
                    )
                elif slug == BUDGET:
                    ledger.budgets.append(Budget(entry.id, _text(values, "categoria"), amount(entry, "importo")))
                elif slug == GOAL:
                    ledger.goals.append(Goal(entry.id, _text(values, "nome"), amount(entry, "obiettivo"), amount(entry, "messo_da_parte"), _day(values, "scadenza")))
                elif slug == LOAN:
                    ledger.loans.append(
                        Loan(entry.id, _text(values, "motivo"), (values.get("con") or [""])[0], _text(values, "direzione") or OWED_TO_ME, amount(entry, "importo"), _text(values, "stato") != SETTLED)
                    )
                elif slug == RECURRING:
                    ledger.recurring.append(
                        Recurring(entry.id, _text(values, "descrizione"), amount(entry, "importo"), _text(values, "frequenza") or MONTHLY, _day(values, "dal") or date.fromisoformat(entry.day), list(values.get("con") or []), _text(values, "categoria"), _day(values, "ultima"))
                    )
                elif slug == SHOPPING:
                    items = values.get("voci") or []
                    ledger.lists.append(ShoppingList(entry.id, entry.title(template), [i["text"] for i in items if not i.get("done")], sum(1 for i in items if i.get("done"))))
            except SecretsError:
                raise  # the vault is closed or cannot open this amount: the screen asks for the PIN
            except (ValueError, KeyError, IndexError) as error:
                ledger.problems.append(f"{template.name} {entry.id[:8]}: {error}")
    return ledger


# * — sums —


def balance(ledger: Ledger) -> Decimal:
    return sum((a.start for a in ledger.accounts), Decimal("0.00")) + sum((m.signed for m in ledger.movements), Decimal("0.00"))


def account_balance(ledger: Ledger, account: Account) -> Decimal:
    return account.start + sum((m.signed for m in ledger.movements if m.account_id == account.id), Decimal("0.00"))


@dataclass(frozen=True)
class CategoryLine:
    category: str
    spent: Decimal
    budget: Optional[Decimal]

    @property
    def left(self) -> Optional[Decimal]:
        return None if self.budget is None else self.budget - self.spent

    @property
    def fraction(self) -> Optional[float]:
        return None if not self.budget else float(self.spent / self.budget)


@dataclass(frozen=True)
class MonthSummary:
    year: int
    month: int
    income: Decimal
    spent: Decimal
    lines: List[CategoryLine]  # biggest first; categories with a budget but no spending included

    @property
    def net(self) -> Decimal:
        return self.income - self.spent


def month_summary(ledger: Ledger, year: int, month: int) -> MonthSummary:
    spent_by: Dict[str, Decimal] = {}
    income = spent = Decimal("0.00")
    for move in ledger.movements:
        if (move.day.year, move.day.month) != (year, month):
            continue
        if move.kind == EARNED:
            income += move.amount
        else:
            spent += move.amount
            key = move.category or "Altro"
            spent_by[key] = spent_by.get(key, Decimal("0.00")) + move.amount
    budgets = {b.category: b.amount for b in ledger.budgets}
    categories = list(spent_by) + [c for c in budgets if c not in spent_by]
    lines = [CategoryLine(c, spent_by.get(c, Decimal("0.00")), budgets.get(c)) for c in categories]
    return MonthSummary(year, month, income, spent, sorted(lines, key=lambda line: (-line.spent, line.category)))


def loan_balances(ledger: Ledger) -> Dict[str, Decimal]:
    """Person id → what they owe me (positive) or what I owe them (negative), open loans only."""
    totals: Dict[str, Decimal] = {}
    for loan in ledger.loans:
        if loan.open and loan.person_id:
            totals[loan.person_id] = totals.get(loan.person_id, Decimal("0.00")) + loan.signed
    return {person: total for person, total in totals.items() if total != 0}


# * — recurring shared expenses —


def occurrence(start: date, frequency: str, index: int) -> date:
    """The `index`-th day of a recurring expense (0 = `start`); a month shorter than the day takes its last day."""
    if frequency == WEEKLY:
        return start + timedelta(days=7 * index)
    months = index if frequency == MONTHLY else 12 * index
    total = start.year * 12 + start.month - 1 + months
    year, month = divmod(total, 12)
    month += 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def due_dates(item: Recurring, today: date) -> List[date]:
    """The days up to `today` not yet registered, oldest first (at most MAX_DUE, the latest ones)."""
    if item.frequency not in (WEEKLY, MONTHLY, YEARLY):
        return []
    found: List[date] = []
    index = 0
    while True:
        day = occurrence(item.start, item.frequency, index)
        if day > today or index > 5000:
            break
        if item.last is None or day > item.last:
            found.append(day)
        index += 1
    return found[-MAX_DUE:]


def _template_check(store: Any, *slugs: str) -> None:
    for slug in slugs:
        if store.find_template(slug) is None:
            raise FinanceError(f"manca il modello '{slug}': installa la Scuola «Oikonomia · Finanze» (`zbone pack install {PACK_NAME}`)")


def register_recurring(store: Any, item: Recurring, day: date) -> List[str]:
    """Write one occurrence: my share as a spesa, and a «Mi deve» loan for each other person. Returns the new entry ids."""
    _template_check(store, MOVEMENT, LOAN, RECURRING)
    others = list(item.people)
    share, mine = split_share(item.total, len(others))
    made: List[str] = []
    values: Dict[str, Any] = {"descrizione": item.text, "tipo": SPENT, "importo": f"{mine:.2f}"}
    if item.category:
        values["categoria"] = item.category
    made.append(store.add_entry(MOVEMENT, values, day=day.isoformat()).id)
    for person in others:
        loan = {"motivo": f"{item.text} · {day.strftime('%d/%m/%Y')}", "con": [person], "direzione": OWED_TO_ME, "importo": f"{share:.2f}", "stato": OPEN}
        made.append(store.add_entry(LOAN, loan, day=day.isoformat()).id)
    store.update_entry(item.id, {"ultima": day.isoformat()})
    return made


def settle_loan(store: Any, loan_id: str) -> None:
    _template_check(store, LOAN)
    store.update_entry(loan_id, {"stato": SETTLED})


def add_movement(store: Any, kind: str, amount: str, text: str, category: str = "", day: Optional[str] = None) -> Any:
    """A quick spesa or entrata. The amount is sealed by the Store: no vault needed."""
    _template_check(store, MOVEMENT)
    if kind not in (SPENT, EARNED):
        raise FinanceError("scegli Spesa o Entrata")
    values: Dict[str, Any] = {"descrizione": " ".join(text.split()), "tipo": kind, "importo": canonical_amount(amount)}
    if category:
        values["categoria"] = category
    return store.add_entry(MOVEMENT, values, day=day)


def today_of(now: datetime) -> date:
    return now.date()
