"""Oikonomia (0.2.6): amounts sealed on disk, added up only in memory, shared recurring expenses and loans."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from zibaldone.core import finance as F
from zibaldone.core import secrets as A
from zibaldone.core.blocks import BLOCK_TYPES
from zibaldone.core.crypto import ScryptParams
from zibaldone.core.templates import Template
from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install
from zibaldone.storage import keys
from zibaldone.storage.database import Store

PASSPHRASE = "cavallo batteria graffetta"
NOW = datetime(2026, 10, 24, 10, 0)
D = Decimal


@pytest.fixture(autouse=True)
def fast_scrypt(monkeypatch):
    monkeypatch.setattr(keys, "DEFAULT_SCRYPT_PARAMS", ScryptParams(n=2**10))
    monkeypatch.setattr(keys, "PIN_SCRYPT_PARAMS", ScryptParams(n=2**10))


@pytest.fixture
def store(isolated_data_dir):
    with Store.open(isolated_data_dir) as opened:
        for name in ("persone", "finanze"):
            apply_install(plan_install(find_builtin_pack(name), opened), opened)
        yield opened


@pytest.fixture
def vault(store):
    new_keys = keys.setup_keys(store.path.parent, PASSPHRASE)
    opened = A.Vault()
    opened.unlock([A.everyday_key(new_keys.private_key)], NOW)
    return opened


def ledger_of(store, vault):
    return F.load(store, lambda value: vault.reveal(value, NOW))


def test_amounts_read_italian_and_plain_numbers() -> None:
    for text, expected in (("12", "12.00"), ("12,5", "12.50"), ("€ 1.234,50", "1234.50"), ("12.50", "12.50"), ("1.500", "1500.00"), ("1,234,567", "1234567.00"), ("0,05", "0.05")):
        assert F.canonical_amount(text) == expected, text
    assert F.canonical_amount("-20,00", negative=True) == "-20.00"
    for wrong in ("", "abc", "12,345", "-5", "1e3", "12,50,5 €x"):
        with pytest.raises(ValueError):
            F.parse_amount(wrong)
    assert F.format_amount(D("1234.5")) == "1.234,50 €" and F.format_amount(D("-0.5")) == "-0,50 €" and F.format_amount(D("1234567")) == "1.234.567,00 €"
    assert F.split_share(D("100.00"), 2) == (D("33.33"), D("33.34"))  # the remainder goes to me


def test_the_block_normalizes_amounts_and_the_option_is_checked() -> None:
    block = BLOCK_TYPES["secret"]
    assert block.normalize("1.250,5", {"format": "importo"}) == "1250.50"
    with pytest.raises(ValueError):
        block.normalize("-3", {"format": "importo"})
    assert block.normalize("-3", {"format": "saldo"}) == "-3.00"
    with pytest.raises(ValueError, match="uno tra"):
        Template.from_dict({"slug": "x", "name": "X", "blocks": [{"key": "s", "type": "secret", "label": "S", "options": {"format": "euro"}}]})


def test_amounts_are_sealed_on_disk_and_out_of_search(store, vault) -> None:
    entry = store.add_entry("movimento", {"descrizione": "Spesa al mercato", "tipo": "Spesa", "importo": "47,80", "categoria": "Cibo"})
    raw = store.connection.execute("SELECT data FROM entries WHERE id = ?", (entry.id,)).fetchone()["data"]
    assert "47,80" not in raw and "47.80" not in raw and A.SECRET_PREFIX in raw
    assert A.is_sealed_value(entry.values["importo"]) and store.search("47,80").total == 0 and store.search("4780").total == 0
    assert vault.reveal(entry.values["importo"], NOW) == "47.80"
    assert F.sealed_values(store) == [entry.values["importo"]]


def test_balance_month_budgets_and_goals(store, vault) -> None:
    cash = store.add_entry("conto", {"nome": "Contanti", "saldo": "100"})
    store.add_entry("conto", {"nome": "Carta", "saldo": "-20,50"})
    for day, kind, amount, category, text in (
        ("2026-10-03", "Entrata", "1.500,00", "Stipendio", "Stipendio"),
        ("2026-10-05", "Spesa", "60,25", "Cibo", "Spesa"),
        ("2026-10-12", "Spesa", "20", "Cibo", "Pizza"),
        ("2026-10-20", "Spesa", "300", "Casa", "Bolletta"),
        ("2026-09-30", "Spesa", "10", "Svago", "Cinema"),
    ):
        store.add_entry("movimento", {"descrizione": text, "tipo": kind, "importo": amount, "categoria": category, "conto": [cash.id] if text == "Pizza" else []}, day=day)
    store.add_entry("budget", {"categoria": "Cibo", "importo": "100"})
    store.add_entry("budget", {"categoria": "Salute", "importo": "30"})
    goal = store.add_entry("obiettivo_risparmio", {"nome": "Viaggio", "obiettivo": "1000", "messo_da_parte": "250"})
    ledger = ledger_of(store, vault)
    assert F.balance(ledger) == D("100") + D("-20.50") + D("1500") - D("60.25") - D("20") - D("300") - D("10")
    assert F.account_balance(ledger, ledger.accounts[0]) == D("80.00")  # 100 − the pizza
    month = F.month_summary(ledger, 2026, 10)
    assert (month.income, month.spent, month.net) == (D("1500.00"), D("380.25"), D("1119.75"))
    lines = {line.category: line for line in month.lines}
    assert [line.category for line in month.lines][:2] == ["Casa", "Cibo"]  # biggest first
    assert lines["Cibo"].left == D("19.75") and round(lines["Cibo"].fraction, 2) == 0.8
    assert lines["Salute"].spent == 0 and lines["Salute"].left == D("30.00") and lines["Casa"].budget is None
    assert ledger.goals[0].id == goal.id and ledger.goals[0].fraction == 0.25 and ledger.goals[0].left == D("750.00")
    empty = F.month_summary(ledger, 2026, 8)  # no movements: only the budgets, nothing spent
    assert empty.spent == 0 and sorted(line.category for line in empty.lines) == ["Cibo", "Salute"] and all(line.spent == 0 for line in empty.lines)


def test_a_closed_vault_cannot_add_up(store, vault) -> None:
    store.add_entry("conto", {"nome": "Contanti", "saldo": "10"})
    with pytest.raises(A.SecretsError):
        F.load(store, lambda value: A.Vault().reveal(value, NOW))


def test_recurring_days_clamp_to_the_month_and_resume_after_the_last() -> None:
    item = lambda **kw: F.Recurring("r", "Affitto", D("900"), kw.pop("frequency", F.MONTHLY), kw.pop("start", date(2026, 1, 31)), [], "", kw.pop("last", None))
    assert [F.occurrence(date(2026, 1, 31), F.MONTHLY, i) for i in range(4)] == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]
    assert F.occurrence(date(2024, 2, 29), F.YEARLY, 1) == date(2025, 2, 28) and F.occurrence(date(2026, 10, 1), F.WEEKLY, 2) == date(2026, 10, 15)
    assert F.due_dates(item(), date(2026, 3, 30)) == [date(2026, 1, 31), date(2026, 2, 28)]
    assert F.due_dates(item(last=date(2026, 2, 28)), date(2026, 4, 30)) == [date(2026, 3, 31), date(2026, 4, 30)]
    assert F.due_dates(item(start=date(2026, 11, 1)), date(2026, 10, 24)) == []
    assert len(F.due_dates(item(frequency=F.WEEKLY, start=date(2020, 1, 1)), date(2026, 10, 24))) == F.MAX_DUE


def test_registering_a_shared_expense_writes_my_share_and_what_the_others_owe(store, vault) -> None:
    marco, anna = store.add_entry("persona", {"nome": "Marco"}), store.add_entry("persona", {"nome": "Anna"})
    store.add_entry("spesa_ricorrente", {"descrizione": "Internet", "importo": "100", "frequenza": "Ogni mese", "dal": "2026-09-15", "con": [marco.id, anna.id], "categoria": "Casa"})
    item = ledger_of(store, vault).recurring[0]
    due = F.due_dates(item, date(2026, 10, 24))
    assert due == [date(2026, 9, 15), date(2026, 10, 15)]
    F.register_recurring(store, item, due[0])
    ledger = ledger_of(store, vault)
    assert ledger.recurring[0].last == date(2026, 9, 15) and F.due_dates(ledger.recurring[0], date(2026, 10, 24)) == [date(2026, 10, 15)]
    (mine,) = ledger.movements
    assert (mine.kind, mine.amount, mine.category, mine.day) == (F.SPENT, D("33.34"), "Casa", date(2026, 9, 15))
    assert sorted((loan.person_id, loan.amount, loan.direction) for loan in ledger.loans) == sorted([(marco.id, D("33.33"), F.OWED_TO_ME), (anna.id, D("33.33"), F.OWED_TO_ME)])
    assert F.loan_balances(ledger) == {marco.id: D("33.33"), anna.id: D("33.33")}
    owed = next(loan for loan in ledger.loans if loan.person_id == marco.id)
    store.add_entry("prestito", {"motivo": "Cena", "con": [marco.id], "direzione": "Gli devo", "importo": "10"})
    assert F.loan_balances(ledger_of(store, vault))[marco.id] == D("23.33")
    F.settle_loan(store, owed.id)
    assert F.loan_balances(ledger_of(store, vault)) == {anna.id: D("33.33"), marco.id: D("-10.00")}
    assert store.backlinks(marco.id)  # the loans show on the person's page


def test_quick_add_needs_the_pack_and_checks_the_amount(store, vault, isolated_data_dir) -> None:
    entry = F.add_movement(store, F.EARNED, "1.000", "  Regalo   di zia ", "Regali", day="2026-10-01")
    assert entry.values["descrizione"] == "Regalo di zia" and vault.reveal(entry.values["importo"], NOW) == "1000.00"
    with pytest.raises(ValueError):
        F.add_movement(store, F.SPENT, "tanto", "x")
    with pytest.raises(F.FinanceError, match="scegli"):
        F.add_movement(store, "Boh", "1", "x")
    assert F.installed(store)


def test_without_the_pack_nothing_is_written(isolated_data_dir) -> None:
    with Store.open(isolated_data_dir) as bare:
        assert not F.installed(bare) and F.sealed_values(bare) == []
        with pytest.raises(F.FinanceError, match="installa"):
            F.add_movement(bare, F.SPENT, "1", "x")
