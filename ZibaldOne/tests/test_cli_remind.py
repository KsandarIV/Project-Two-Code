import json
from datetime import datetime

import pytest
from typer.testing import CliRunner

from zibaldone.cli import remind_cmd
from zibaldone.cli.app import app
from zibaldone.cli.remind_cmd import remind_app
from zibaldone.core.reminders import MESSAGES, MILESTONE_MESSAGES
from zibaldone.notify.service import fire_due_reminders, in_app_reminder
from zibaldone.notify.windows_tasks import TaskResult, task_name
from zibaldone.storage.database import Store
from zibaldone.storage.reminder_log import load_log, log_path

runner = CliRunner()
SECRET = "SEGRETO-Marco-mi-ha-detto-XYZ"


class FakeNotifier:
    name = "finta"

    def __init__(self, works: bool = True) -> None:
        self.works, self.sent = works, []

    def send(self, title: str, body: str) -> bool:
        self.sent.append((title, body))
        return self.works


@pytest.fixture
def notifier(monkeypatch) -> FakeNotifier:
    fake = FakeNotifier()
    monkeypatch.setattr(remind_cmd, "get_notifier", lambda: fake)
    return fake


@pytest.fixture
def clock(monkeypatch):
    """Set the time the remind commands see: clock("2026-10-19 08:45")."""

    def set_time(text: str) -> None:
        moment = datetime.fromisoformat(text)
        monkeypatch.setattr(remind_cmd, "current_time", lambda: moment)

    set_time("2026-10-19 08:45")  # a Monday
    return set_time


@pytest.fixture
def journal() -> None:
    assert runner.invoke(app, ["privacy", "accept"]).exit_code == 0
    assert runner.invoke(app, ["pack", "install", "diario", "--yes"]).exit_code == 0


def remind(*args: str):
    return runner.invoke(remind_app, list(args))


def write(template: str, day: str, text: str = "una giornata qualunque") -> None:
    block = {"mattina": "intenzione", "meta_giornata": "nota", "sera": "fatto"}[template]
    result = runner.invoke(app, ["entry", "add", template, "--day", day, "--set", f"{block}={text}"])
    assert result.exit_code == 0, result.output


def test_status_shows_config_today_and_streak(journal, clock) -> None:
    write("mattina", "2026-10-19")
    write("sera", "2026-10-18")
    write("sera", "2026-10-17")
    result = remind("status")
    assert result.exit_code == 0, result.output
    assert "Mattina        08:30  tutti i giorni" in result.output
    assert "Oggi, lunedì 19/10:" in result.output
    assert "✓ Mattina" in result.output
    assert "○ Metà giornata  da scrivere · arriverà dalle 13:30" in result.output
    assert "Prossimo promemoria: oggi alle 13:30 (Metà giornata)" in result.output
    assert "Serie: 3 giorni di fila — bel traguardo!" in result.output


def test_status_without_the_diario_pack_says_what_to_install(clock) -> None:
    assert runner.invoke(app, ["privacy", "accept"]).exit_code == 0
    result = remind("status")
    assert result.exit_code == 0
    assert "manca il modello 'mattina'" in result.output and "zbone pack install diario" in result.output
    assert "modello 'mattina' non installato" in result.output


def test_config_changes_are_saved_and_validated(journal, clock, isolated_data_dir) -> None:
    result = remind("config", "--moment", "sera", "--time", "21:00", "--days", "lun,mer,ven")
    assert result.exit_code == 0, result.output
    assert "Impostazioni dei promemoria salvate." in result.output
    assert "Sera           21:00  lun, mer, ven" in result.output
    settings = json.loads((isolated_data_dir / "settings.json").read_text(encoding="utf-8"))
    assert settings["reminders"]["moments"]["sera"] == {"enabled": True, "time": "21:00", "weekdays": ["lun", "mer", "ven"], "backoff_dismissed_on": None}
    assert settings["privacy"]["accepted"] is True

    result = remind("config", "--quiet-start", "23:00", "--quiet-end", "07:00", "--window", "90", "--days", "feriali")
    assert result.exit_code == 0, result.output
    assert "Ore di silenzio: 23:00–07:00" in result.output and "fino a 90 minuti" in result.output
    assert result.output.count("lun–ven") == 3

    result = remind("config", "--moment", "mattina", "--off")
    assert "Mattina        08:30  lun–ven            spento" in result.output
    result = remind("config", "--off")
    assert "Promemoria: spenti" in result.output
    assert "Promemoria: accesi" in remind("config", "--reset").output


@pytest.mark.parametrize(
    "args, message",
    [
        (["--moment", "sera", "--time", "25:00"], "Sera: orario non valido: '25:00'"),
        (["--time", "21:00"], "aggiungi --moment"),
        (["--moment", "pranzo", "--on"], "momento sconosciuto 'pranzo'"),
        (["--days", "lunes"], "giorno non valido: 'lunes'"),
        (["--window", "5"], "tra 15 e 720"),
        (["--quiet-start", "08:00"], "orari diversi"),
        (["--moment", "sera", "--time", "13:30"], "stesso orario"),
        (["--moment", "sera", "--thin-out", "--keep"], "non tutti e due"),
    ],
)
def test_config_errors_are_clear(journal, clock, args, message) -> None:
    result = remind("config", *args)
    assert result.exit_code == 1
    assert message in result.output


def test_fire_sends_once_and_logs(journal, clock, notifier, isolated_data_dir) -> None:
    result = remind("fire")
    assert result.exit_code == 0, result.output
    assert "Promemoria inviato (finta): Mattina" in result.output
    assert len(notifier.sent) == 1 and notifier.sent[0][0] == "ZibaldOne · Mattina"
    [record] = load_log(isolated_data_dir).records
    assert (record.moment, record.day.isoformat(), record.via) == ("mattina", "2026-10-19", "finta")

    clock("2026-10-19 09:15")
    again = remind("fire")
    assert "Nessun promemoria da inviare adesso." in again.output
    assert "Mattina: promemoria già inviato oggi" in again.output
    assert len(notifier.sent) == 1


def test_fire_skips_moments_already_written(journal, clock, notifier) -> None:
    write("mattina", "2026-10-19")
    result = remind("fire")
    assert "Mattina: voce già scritta oggi" in result.output
    assert notifier.sent == []


def test_fire_dry_run_neither_sends_nor_logs(journal, clock, notifier, isolated_data_dir) -> None:
    result = remind("fire", "--dry-run")
    assert result.exit_code == 0
    assert "Prova, non invio nulla: «ZibaldOne · Mattina" in result.output
    assert notifier.sent == [] and not log_path(isolated_data_dir).exists()


def test_fire_with_moment_and_quiet_hours(journal, clock, notifier) -> None:
    result = remind("fire", "--moment", "sera")
    assert "Sera: arriverà dalle 21:30" in result.output and "Mattina" not in result.output
    clock("2026-10-19 22:45")
    result = remind("fire", "--moment", "sera")
    assert "Sera: ore di silenzio (22:30–08:00)" in result.output
    assert notifier.sent == []
    assert remind("fire", "--moment", "notte").exit_code == 1


def test_failed_delivery_is_not_logged_and_retried(journal, clock, monkeypatch, isolated_data_dir) -> None:
    broken = FakeNotifier(works=False)
    monkeypatch.setattr(remind_cmd, "get_notifier", lambda: broken)
    result = remind("fire")
    assert result.exit_code == 1
    assert "non sono riuscito a mostrare il promemoria (Mattina)" in result.output
    assert load_log(isolated_data_dir).records == ()
    working = FakeNotifier()
    monkeypatch.setattr(remind_cmd, "get_notifier", lambda: working)
    clock("2026-10-19 09:15")
    assert remind("fire").exit_code == 0 and len(working.sent) == 1


def test_notification_never_contains_entry_text(journal, clock, notifier) -> None:
    for day in ("2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18"):
        write("sera", day, SECRET)
    write("mattina", "2026-10-19", SECRET)
    write("meta_giornata", "2026-10-19", SECRET)
    clock("2026-10-19 21:40")
    assert remind("fire").exit_code == 0
    [(title, body)] = notifier.sent
    assert SECRET not in title and SECRET not in body and "Marco" not in body
    assert body in MESSAGES["sera"] or any(body == text.format(days=5) for text in MILESTONE_MESSAGES)


def test_backoff_is_suggested_after_three_ignored(journal, clock, notifier) -> None:
    for day in ("2026-10-19", "2026-10-20", "2026-10-21"):
        clock(f"{day} 21:40")
        assert "Promemoria inviato (finta): Sera" in remind("fire").output
    clock("2026-10-22 09:00")
    status = remind("status")
    assert "Gli ultimi 3 promemoria della sera sono passati senza una voce" in status.output
    assert "zbone remind config --moment sera --thin-out" in status.output
    assert "Gli ultimi 3 promemoria della mattina" not in status.output

    thinned = remind("config", "--moment", "sera", "--thin-out")
    assert "Sera           21:30  lun, mer, ven, dom" in thinned.output
    assert "Suggerimento" not in remind("status").output
    # still reminded on the days kept: the app never switches reminders off by itself
    clock("2026-10-23 21:40")  # friday
    assert "Promemoria inviato (finta): Sera" in remind("fire").output


def test_install_and_uninstall_explain_on_other_systems(journal, clock, monkeypatch) -> None:
    monkeypatch.setattr(remind_cmd, "on_windows", lambda: False)
    result = remind("install")
    assert result.exit_code == 0, result.output
    assert r"ZibaldOne\promemoria-mattina  alle 08:30, tutti i giorni" in result.output
    assert "remind fire --moment sera" in result.output
    assert "non creo nulla" in result.output
    result = remind("uninstall")
    assert result.exit_code == 0 and "non c'è niente da togliere" in result.output


def test_install_on_windows_runs_the_plan(journal, clock, monkeypatch) -> None:
    calls = []

    def fake_install(plan):
        calls.append(plan)
        return [TaskResult(task.name, "creata", True) for task in plan.create]

    monkeypatch.setattr(remind_cmd, "on_windows", lambda: True)
    monkeypatch.setattr(remind_cmd, "install_tasks", fake_install)
    result = remind("install")
    assert result.exit_code == 0, result.output
    assert f"{task_name('sera')}: creata" in result.output and "anche ad app chiusa" in result.output
    assert [task.moment for task in calls[0].create] == ["mattina", "meta_giornata", "sera"]

    monkeypatch.setattr(remind_cmd, "install_tasks", lambda plan: [TaskResult(task_name("mattina"), "creata", False, "Accesso negato.")])
    failed = remind("install")
    assert failed.exit_code == 1 and "Accesso negato." in failed.output

    remind("config", "--off")
    assert "i promemoria sono spenti" in remind("install").output


def test_test_command(journal, notifier, monkeypatch) -> None:
    result = remind("test")
    assert result.exit_code == 0 and "Notifica di prova inviata (finta)." in result.output
    assert notifier.sent == [(remind_cmd.TEST_TITLE, remind_cmd.TEST_BODY)]
    monkeypatch.setattr(remind_cmd, "get_notifier", lambda: FakeNotifier(works=False))
    failed = remind("test")
    assert failed.exit_code == 1 and "non sono riuscito" in failed.output


def test_fire_without_consent_stops_instead_of_asking(clock, notifier) -> None:
    result = remind("fire")
    assert result.exit_code == 1
    assert "zbone privacy accept" in result.output
    assert "Continuare?" not in result.output and notifier.sent == []


def test_service_api_for_the_app(journal, isolated_data_dir) -> None:
    """What the Flet interface calls: a banner at start, then notifications while open."""
    with Store.open(isolated_data_dir) as store:
        banner = in_app_reminder(store, isolated_data_dir, datetime(2026, 10, 19, 23, 30))
        assert banner.moment == "sera" and banner.title == "ZibaldOne · Sera"
        assert not load_log(isolated_data_dir).records
        shown = FakeNotifier()
        result = fire_due_reminders(store, isolated_data_dir, datetime(2026, 10, 19, 13, 40), shown)
        assert [reminder.moment for reminder in result.sent] == ["meta_giornata"] and result.via == "finta"
        assert fire_due_reminders(store, isolated_data_dir, datetime(2026, 10, 19, 13, 50), shown).due == ()
