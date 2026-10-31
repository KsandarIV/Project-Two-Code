from dataclasses import replace
from datetime import date, datetime, time, timedelta
from xml.etree import ElementTree

import pytest

from zibaldone.core.reminders import (
    MESSAGES,
    MILESTONE_MESSAGES,
    MOMENTS,
    OUTCOME_IGNORED,
    OUTCOME_PENDING,
    OUTCOME_WRITTEN,
    MomentConfig,
    QuietHours,
    ReminderConfig,
    ReminderLog,
    SentReminder,
    backoff_suggestions,
    check_moment,
    compose_reminder,
    config_from_settings,
    config_warnings,
    due_reminders,
    format_weekdays,
    ignored_in_a_row,
    in_app_prompt,
    is_milestone,
    keep_frequency,
    next_reminder,
    parse_clock,
    parse_moment,
    parse_weekdays,
    prune_log,
    record_sent,
    reminder_body,
    night_prompt,
    NIGHT_MESSAGES,
    resolve_outcomes,
    settings_with_config,
    streak,
    thin_out,
    thinned_weekdays,
    window_of,
)
from zibaldone.notify import FallbackNotifier, TerminalNotifier, get_notifier, running_on_android
from zibaldone.notify.android import AndroidNotifier
from zibaldone.notify.desktop import DesktopNotifierAdapter
from zibaldone.notify.windows_tasks import (
    TaskSchedulerError,
    all_task_names,
    delete_args,
    install_tasks,
    launcher_command,
    plan_install,
    task_name,
    uninstall_tasks,
)
from zibaldone.storage.reminder_log import load_log, load_reminder_config, log_path, save_log, save_reminder_config
from zibaldone.storage.settings import load_settings, save_settings

MONDAY = date(2026, 10, 19)
SATURDAY = date(2026, 10, 17)
NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
GUILT_WORDS = ("ancora", "dimentica", "pers", "peccato", "devi", "non hai", "interrott", "male", "colpa")


def at(day: date, clock: str) -> datetime:
    hours, minutes = clock.split(":")
    return datetime.combine(day, time(int(hours), int(minutes)))


def due_keys(config: ReminderConfig, now: datetime, written=(), log=ReminderLog()) -> list:
    return [reminder.moment for reminder in due_reminders(config, now, set(written), log)]


def sent(moment: str, day: date, outcome: str = OUTCOME_PENDING) -> SentReminder:
    return SentReminder(moment=moment, day=day, sent_at=at(day, "09:00"), via="test", outcome=outcome)


# * — configuration —


def test_defaults_follow_the_adr() -> None:
    config = ReminderConfig()
    assert [moment.time for moment in config.moments] == ["08:30", "13:30", "21:30"]
    assert config.quiet_hours.label == "22:30–08:00"
    assert config.enabled and all(moment.enabled and len(moment.weekdays) == 7 for moment in config.moments)


def test_config_round_trip_through_settings() -> None:
    config = ReminderConfig(window_minutes=90).with_moment(MomentConfig("sera", time="21:00", weekdays=(0, 2, 4)))
    settings = settings_with_config({"privacy": {"accepted": True}}, config)
    assert settings["privacy"] == {"accepted": True}
    assert settings["reminders"]["moments"]["sera"]["weekdays"] == ["lun", "mer", "ven"]
    assert config_from_settings(settings) == config
    assert config_from_settings({}) == ReminderConfig()


def test_config_load_and_save_keep_other_settings(isolated_data_dir) -> None:
    save_settings(isolated_data_dir, {"privacy": {"accepted": True}})
    assert load_reminder_config(isolated_data_dir) == ReminderConfig()
    config = replace(ReminderConfig(), enabled=False)
    save_reminder_config(isolated_data_dir, config)
    assert load_reminder_config(isolated_data_dir) == config
    assert load_settings(isolated_data_dir)["privacy"] == {"accepted": True}


@pytest.mark.parametrize(
    "build, message",
    [
        (lambda: MomentConfig("mattina", time="25:00"), "orario non valido"),
        (lambda: MomentConfig("mattina", time="8h"), "usa HH:MM"),
        (lambda: MomentConfig("pranzo"), "momento sconosciuto"),
        (lambda: MomentConfig("sera", weekdays=()), "almeno un giorno"),
        (lambda: MomentConfig("sera", weekdays=(7,)), "da 0 \\(lunedì\\) a 6"),
        (lambda: MomentConfig("sera", enabled="sì"), "true o false"),
        (lambda: QuietHours(start="22:00", end="22:00"), "orari diversi"),
        (lambda: ReminderConfig(window_minutes=5), "tra 15 e 720"),
        (lambda: ReminderConfig(window_minutes=True), "tra 15 e 720"),
        (lambda: ReminderConfig().with_moment(MomentConfig("sera", time="13:30")), "stesso orario"),
    ],
)
def test_invalid_config_is_refused_in_italian(build, message) -> None:
    with pytest.raises(ValueError, match=message):
        build()


@pytest.mark.parametrize(
    "data, message",
    [
        ({"reminders": {"colore": "blu"}}, "campi sconosciuti colore"),
        ({"reminders": {"moments": {"pranzo": {}}}}, "campi sconosciuti pranzo"),
        ({"reminders": {"moments": {"sera": {"weekdays": ["lun", "xyz"]}}}}, "giorno non valido: 'xyz'"),
        ({"reminders": {"moments": {"sera": {"weekdays": [1, 2]}}}}, "deve essere una lista"),
        ({"reminders": {"quiet_hours": {"start": "tardi"}}}, "inizio delle ore di silenzio non valido"),
        ({"reminders": "sì"}, "oggetto JSON"),
    ],
)
def test_invalid_settings_file_is_explained(data, message) -> None:
    with pytest.raises(ValueError, match="settings.json") as error:
        config_from_settings(data)
    assert message in str(error.value)


def test_same_time_is_fine_when_one_moment_is_off() -> None:
    config = ReminderConfig().with_moment(MomentConfig("meta_giornata", enabled=False))
    config = config.with_moment(MomentConfig("sera", time="13:30"))
    assert config.moment("sera").time == "13:30"


def test_parse_clock_weekdays_and_moments() -> None:
    assert parse_clock("8:30") == "08:30"
    assert parse_clock("21.15") == "21:15"
    assert parse_weekdays("lun,mar,mer") == (0, 1, 2)
    assert parse_weekdays("lun-ven") == (0, 1, 2, 3, 4)
    assert parse_weekdays("ven-lun") == (0, 4, 5, 6)
    assert parse_weekdays("feriali") == (0, 1, 2, 3, 4)
    assert parse_weekdays("weekend") == (5, 6)
    assert parse_weekdays("Lunedì, mercoledi, VEN") == (0, 2, 4)
    assert parse_weekdays("tutti") == tuple(range(7))
    with pytest.raises(ValueError, match="giorno non valido: 'lunes'"):
        parse_weekdays("lunes")
    with pytest.raises(ValueError, match="almeno un giorno"):
        parse_weekdays(" , ")
    assert format_weekdays(range(7)) == "tutti i giorni"
    assert format_weekdays((0, 1, 2, 3, 4)) == "lun–ven"
    assert format_weekdays((0, 2, 4, 5, 6)) == "lun, mer, ven–dom"
    assert parse_moment("Metà giornata") == "meta_giornata"
    with pytest.raises(ValueError, match="scegli tra mattina, meta_giornata, sera"):
        parse_moment("notte")


# * — quiet hours —


def test_quiet_hours_across_midnight() -> None:
    quiet = QuietHours(start="22:30", end="08:00")
    assert quiet.contains(time(22, 30)) and quiet.contains(time(23, 59)) and quiet.contains(time(0, 0)) and quiet.contains(time(7, 59))
    assert not quiet.contains(time(8, 0)) and not quiet.contains(time(12, 0)) and not quiet.contains(time(22, 29))
    assert quiet.ends_after(at(MONDAY, "23:00")) == at(MONDAY + timedelta(days=1), "08:00")
    assert quiet.ends_after(at(MONDAY, "06:00")) == at(MONDAY, "08:00")


def test_quiet_hours_within_one_day_and_switched_off() -> None:
    quiet = QuietHours(start="13:00", end="15:00")
    assert quiet.contains(time(14, 0)) and not quiet.contains(time(15, 0)) and not quiet.contains(time(23, 0))
    assert not replace(quiet, enabled=False).contains(time(14, 0))


# * — what is due —


def test_reminder_is_due_inside_its_window_only() -> None:
    config = ReminderConfig()
    assert due_keys(config, at(MONDAY, "08:29")) == []
    assert due_keys(config, at(MONDAY, "08:30")) == ["mattina"]
    assert due_keys(config, at(MONDAY, "11:29")) == ["mattina"]
    assert due_keys(config, at(MONDAY, "11:30")) == []
    assert check_moment(config, "mattina", at(MONDAY, "12:00"), set(), ReminderLog()).reason == "finestra chiusa alle 11:30"
    assert check_moment(config, "sera", at(MONDAY, "12:00"), set(), ReminderLog()).reason == "arriverà dalle 21:30"


def test_window_stops_at_the_next_moment_and_at_midnight() -> None:
    config = ReminderConfig(window_minutes=600)
    assert window_of(config, "mattina", MONDAY) == (at(MONDAY, "08:30"), at(MONDAY, "13:30"))
    assert due_keys(config, at(MONDAY, "13:31")) == ["meta_giornata"]
    quiet_off = replace(config, quiet_hours=replace(config.quiet_hours, enabled=False))
    assert window_of(quiet_off, "sera", MONDAY)[1] == datetime.combine(MONDAY + timedelta(days=1), time(0))
    # with metà giornata off, the morning window runs until its own end
    no_noon = config.with_moment(replace(config.moment("meta_giornata"), enabled=False))
    assert window_of(no_noon, "mattina", MONDAY)[1] == at(MONDAY, "18:30")


def test_late_check_still_fires_once() -> None:
    config = ReminderConfig()
    log = ReminderLog()
    first = due_reminders(config, at(MONDAY, "10:47"), set(), log)
    assert [reminder.moment for reminder in first] == ["mattina"]
    log = record_sent(log, first[0], at(MONDAY, "10:47"))
    assert due_keys(config, at(MONDAY, "11:15"), log=log) == []
    assert check_moment(config, "mattina", at(MONDAY, "11:15"), set(), log).reason == "promemoria già inviato oggi"
    assert due_keys(config, at(MONDAY + timedelta(days=1), "08:45"), log=log) == ["mattina"]


def test_already_written_today_is_skipped() -> None:
    config = ReminderConfig()
    assert due_keys(config, at(MONDAY, "08:45"), written={"mattina"}) == []
    assert due_keys(config, at(MONDAY, "08:45"), written={"sera", "libro"}) == ["mattina"]
    assert check_moment(config, "mattina", at(MONDAY, "08:45"), {"mattina"}, ReminderLog()).reason == "voce già scritta oggi"


def test_quiet_hours_win_over_the_window() -> None:
    config = ReminderConfig()
    assert due_keys(config, at(MONDAY, "22:00")) == ["sera"]
    assert due_keys(config, at(MONDAY, "22:40")) == []
    assert check_moment(config, "sera", at(MONDAY, "22:40"), set(), ReminderLog()).reason == "ore di silenzio (22:30–08:00)"
    early = ReminderConfig().with_moment(MomentConfig("mattina", time="07:30"))
    assert due_keys(early, at(MONDAY, "07:45")) == []
    assert due_keys(early, at(MONDAY, "08:05")) == ["mattina"]


def test_weekdays_and_switches() -> None:
    weekdays_only = ReminderConfig().with_moment(MomentConfig("mattina", weekdays=parse_weekdays("lun-ven")))
    assert due_keys(weekdays_only, at(MONDAY, "08:45")) == ["mattina"]
    assert due_keys(weekdays_only, at(SATURDAY, "08:45")) == []
    assert check_moment(weekdays_only, "mattina", at(SATURDAY, "08:45"), set(), ReminderLog()).reason == "oggi non è tra i giorni scelti"
    moment_off = ReminderConfig().with_moment(MomentConfig("mattina", enabled=False))
    assert check_moment(moment_off, "mattina", at(MONDAY, "08:45"), set(), ReminderLog()).reason == "momento spento"
    all_off = replace(ReminderConfig(), enabled=False)
    assert due_keys(all_off, at(MONDAY, "08:45")) == []
    assert check_moment(all_off, "mattina", at(MONDAY, "08:45"), set(), ReminderLog()).reason == "promemoria spenti"


def test_timezone_aware_now_is_read_as_wall_clock() -> None:
    from datetime import timezone

    aware = at(MONDAY, "08:45").replace(tzinfo=timezone(timedelta(hours=2)))
    assert due_keys(ReminderConfig(), aware) == ["mattina"]


def test_next_reminder() -> None:
    config = ReminderConfig()
    assert next_reminder(config, at(MONDAY, "08:45")).at == at(MONDAY, "08:45")
    upcoming = next_reminder(config, at(MONDAY, "09:00"), {"mattina"})
    assert (upcoming.moment, upcoming.at) == ("meta_giornata", at(MONDAY, "13:30"))
    upcoming = next_reminder(config, at(MONDAY, "23:00"))
    assert (upcoming.moment, upcoming.at) == ("mattina", at(MONDAY + timedelta(days=1), "08:30"))
    early = config.with_moment(MomentConfig("mattina", time="07:00"))
    assert next_reminder(early, at(MONDAY, "06:00")).at == at(MONDAY, "08:00")
    weekdays = ReminderConfig().with_moment(MomentConfig("mattina", weekdays=(0,)))
    weekdays = weekdays.with_moment(MomentConfig("meta_giornata", enabled=False)).with_moment(MomentConfig("sera", enabled=False))
    assert next_reminder(weekdays, at(SATURDAY, "09:00")).at == at(MONDAY, "08:30")
    assert next_reminder(replace(config, enabled=False), at(MONDAY, "09:00")) is None


def test_in_app_prompt_ignores_quiet_hours_but_not_entries() -> None:
    config = ReminderConfig()
    assert in_app_prompt(config, at(MONDAY, "07:00"), set()) is None
    assert in_app_prompt(config, at(MONDAY, "18:00"), set()).moment == "meta_giornata"
    assert in_app_prompt(config, at(MONDAY, "23:30"), {"sera"}).moment == "meta_giornata"
    assert in_app_prompt(config, at(MONDAY, "23:30"), set(MOMENTS)) is None
    assert in_app_prompt(replace(config, enabled=False), at(MONDAY, "18:00"), set()) is None


def test_config_warnings() -> None:
    late = ReminderConfig().with_moment(MomentConfig("sera", time="23:00"))
    assert any("non arriverà mai" in warning for warning in config_warnings(late))
    early = ReminderConfig().with_moment(MomentConfig("mattina", time="07:30"))
    assert any("arriverà dalle 08:00" in warning for warning in config_warnings(early))
    assert config_warnings(ReminderConfig()) == []


# * — messages and streaks —


def test_streak_counts_up_to_today_or_yesterday() -> None:
    days = {MONDAY - timedelta(days=offset) for offset in range(5)}
    assert streak(days, MONDAY) == 5
    assert streak(days, MONDAY + timedelta(days=1)) == 5
    assert streak(days, MONDAY + timedelta(days=2)) == 0
    assert streak(set(), MONDAY) == 0
    assert streak({MONDAY, MONDAY - timedelta(days=2)}, MONDAY) == 1


@pytest.mark.parametrize("days", [3, 7, 14, 30, 100, 365, 500, 730])
def test_milestones_are_celebrated(days) -> None:
    assert is_milestone(days)
    reminder = compose_reminder("sera", MONDAY, days)
    assert reminder.milestone and f"{days} giorni di fila" in reminder.body


@pytest.mark.parametrize("days", [0, 1, 2, 4, 8, 101, 366])
def test_other_streaks_get_the_usual_message(days) -> None:
    assert not is_milestone(days)
    assert reminder_body("sera", MONDAY, days) in MESSAGES["sera"]


def test_messages_rotate_deterministically() -> None:
    week = [MONDAY + timedelta(days=offset) for offset in range(7)]
    for moment in MOMENTS:
        bodies = [reminder_body(moment, day) for day in week]
        assert bodies == [reminder_body(moment, day) for day in week]
        assert len(set(bodies)) == len(MESSAGES[moment])
    assert compose_reminder("meta_giornata", MONDAY).title == "ZibaldOne · Metà giornata"


def test_messages_are_short_and_never_guilt_inducing() -> None:
    texts = [text for variants in MESSAGES.values() for text in variants]
    texts += [text.format(days=7) for text in MILESTONE_MESSAGES]
    for text in texts:
        assert len(text) <= 80, text
        assert not any(word in text.lower() for word in GUILT_WORDS), text
    lost = reminder_body("mattina", MONDAY, streak({MONDAY - timedelta(days=offset) for offset in range(3, 40)}, MONDAY))
    assert lost in MESSAGES["mattina"]


# * — the log and back-off —


def test_resolve_outcomes_and_prune() -> None:
    log = ReminderLog((sent("sera", MONDAY - timedelta(days=2)), sent("sera", MONDAY - timedelta(days=1)), sent("sera", MONDAY)))
    resolved = resolve_outcomes(log, {MONDAY - timedelta(days=1): {"sera"}}, MONDAY)
    assert [record.outcome for record in resolved.records] == [OUTCOME_IGNORED, OUTCOME_WRITTEN, OUTCOME_PENDING]
    old = ReminderLog((sent("sera", MONDAY - timedelta(days=61)), sent("sera", MONDAY - timedelta(days=60))))
    assert [record.day for record in prune_log(old, MONDAY).records] == [MONDAY - timedelta(days=60)]


def test_log_file_round_trip_and_errors(isolated_data_dir) -> None:
    assert load_log(isolated_data_dir) == ReminderLog()
    log = ReminderLog((sent("mattina", MONDAY - timedelta(days=90)), sent("mattina", MONDAY, OUTCOME_WRITTEN)))
    saved = save_log(isolated_data_dir, log, MONDAY)
    assert load_log(isolated_data_dir) == saved == ReminderLog((log.records[1],))
    assert not list(isolated_data_dir.glob("*.tmp"))
    log_path(isolated_data_dir).write_text("{non è json", encoding="utf-8")
    with pytest.raises(ValueError, match="registro dei promemoria"):
        load_log(isolated_data_dir)
    log_path(isolated_data_dir).write_text('{"format": 1, "records": [{"moment": "notte"}]}', encoding="utf-8")
    with pytest.raises(ValueError, match="momento sconosciuto 'notte'"):
        load_log(isolated_data_dir)


def ignored_days(count: int, moment: str = "sera") -> ReminderLog:
    return ReminderLog(tuple(sent(moment, MONDAY - timedelta(days=offset), OUTCOME_IGNORED) for offset in range(1, count + 1)))


def test_backoff_after_three_ignored_in_a_row() -> None:
    config = ReminderConfig()
    assert backoff_suggestions(config, ignored_days(2)) == []
    [suggestion] = backoff_suggestions(config, ignored_days(3))
    assert suggestion.moment == "sera" and suggestion.ignored_in_a_row == 3
    assert suggestion.proposed_weekdays == (0, 2, 4, 6)
    assert "va benissimo" in suggestion.message and "meno spesso" in suggestion.message
    assert not any(word in suggestion.message.lower() for word in ("devi", "peccato", "colpa"))
    # suggest only, never switch off
    assert due_keys(config, at(MONDAY, "21:45"), log=ignored_days(5)) == ["sera"]


def test_backoff_counts_only_the_latest_streak() -> None:
    log = ReminderLog(ignored_days(2).records + (sent("sera", MONDAY - timedelta(days=3), OUTCOME_WRITTEN),) + ignored_days(9).records[3:])
    assert ignored_in_a_row(log, "sera") == 2
    pending_today = ReminderLog(ignored_days(3).records + (sent("sera", MONDAY),))
    assert ignored_in_a_row(pending_today, "sera") == 3


def test_thin_out_and_keep_reset_the_suggestion() -> None:
    config = ReminderConfig()
    log = ignored_days(4)
    thinned = thin_out(config, "sera", MONDAY)
    assert thinned.moment("sera").weekdays == (0, 2, 4, 6)
    assert backoff_suggestions(thinned, log) == []
    kept = keep_frequency(config, "sera", MONDAY)
    assert kept.moment("sera").weekdays == tuple(range(7)) and backoff_suggestions(kept, log) == []
    later = ReminderLog(log.records + tuple(sent("sera", MONDAY + timedelta(days=offset), OUTCOME_IGNORED) for offset in (1, 2, 3)))
    assert [suggestion.ignored_in_a_row for suggestion in backoff_suggestions(kept, later)] == [3]
    assert thinned_weekdays((0, 1, 2, 3, 4)) == (0, 2, 4)
    single = config.with_moment(MomentConfig("sera", weekdays=(3,)))
    assert "spegnerli" in backoff_suggestions(single, log)[0].message


# * — delivery adapters —


class FakeDesktopBackend:
    def __init__(self, dispatch: bool = True, error: bool = False) -> None:
        self.dispatch, self.error, self.calls = dispatch, error, []

    def send(self, title, message, on_dispatched=None):
        self.calls.append((title, message))
        if self.error:
            raise RuntimeError("no bus")
        if self.dispatch and on_dispatched:
            on_dispatched()
        return "id"


def test_desktop_adapter_reports_real_delivery_only() -> None:
    assert DesktopNotifierAdapter(FakeDesktopBackend()).send("T", "B")
    assert not DesktopNotifierAdapter(FakeDesktopBackend(dispatch=False)).send("T", "B")
    assert not DesktopNotifierAdapter(FakeDesktopBackend(error=True)).send("T", "B")


def test_android_detection_and_missing_library(monkeypatch) -> None:
    assert running_on_android({"ANDROID_ROOT": "/system"}, "linux")
    assert running_on_android({"MAIN_ACTIVITY_HOST_CLASS_NAME": "x"}, "linux")
    assert running_on_android({}, "android")
    assert not running_on_android({}, "win32")
    monkeypatch.setenv("ANDROID_DATA", "/data")
    notifier = get_notifier()
    assert isinstance(notifier, AndroidNotifier)
    assert not notifier.send("T", "B")  # android-notify is not installed here


def test_desktop_falls_back_to_terminal(monkeypatch, capsys) -> None:
    for name in ("ANDROID_ROOT", "ANDROID_DATA", "MAIN_ACTIVITY_HOST_CLASS_NAME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(DesktopNotifierAdapter, "create", classmethod(lambda cls: None))
    assert isinstance(get_notifier(), TerminalNotifier)
    monkeypatch.setattr(DesktopNotifierAdapter, "create", classmethod(lambda cls: cls(FakeDesktopBackend(dispatch=False))))
    notifier = get_notifier()
    assert isinstance(notifier, FallbackNotifier)
    assert notifier.send("ZibaldOne · Sera", "Com'è andata?") and notifier.name == "terminale"
    assert "ZibaldOne · Sera — Com'è andata?" in capsys.readouterr().out


# * — Windows scheduled tasks —


def test_launcher_prefers_windowless_python(tmp_path) -> None:
    scripts = tmp_path / "Scripts"
    scripts.mkdir()
    python = scripts / "python.exe"
    python.touch()
    assert launcher_command(str(python), str(scripts)) == [str(python), "-m", "zibaldone"]
    (scripts / "zbone.exe").touch()
    assert launcher_command(str(python), str(scripts)) == [str(scripts / "zbone.exe")]
    (scripts / "pythonw.exe").touch()
    assert launcher_command(str(python), str(scripts)) == [str(scripts / "pythonw.exe"), "-m", "zibaldone"]
    assert launcher_command(str(python), str(scripts), windowless=False) == [str(scripts / "zbone.exe")]


def test_plan_install_builds_one_task_per_moment(tmp_path) -> None:
    config = ReminderConfig().with_moment(MomentConfig("meta_giornata", enabled=False))
    config = config.with_moment(MomentConfig("sera", time="21:00", weekdays=parse_weekdays("lun,mer,ven")))
    launcher = [r"C:\Users\Alex\ZibaldOne\.venv\Scripts\pythonw.exe", "-m", "zibaldone"]
    plan = plan_install(config, launcher, MONDAY)
    assert [task.name for task in plan.create] == [r"ZibaldOne\promemoria-mattina", r"ZibaldOne\promemoria-sera"]
    assert plan.remove == [r"ZibaldOne\promemoria-meta_giornata"]
    sera = plan.create[1]
    assert sera.command == [*launcher, "remind", "fire", "--moment", "sera"]
    assert sera.create_args(tmp_path / "sera.xml") == ["schtasks", "/Create", "/F", "/TN", r"ZibaldOne\promemoria-sera", "/XML", str(tmp_path / "sera.xml")]
    assert delete_args(sera.name) == ["schtasks", "/Delete", "/F", "/TN", r"ZibaldOne\promemoria-sera"]

    root = ElementTree.fromstring(sera.xml.split("\n", 1)[1])
    assert root.find("t:Triggers/t:CalendarTrigger/t:StartBoundary", NS).text == "2026-10-19T21:00:00"
    days = root.find("t:Triggers/t:CalendarTrigger/t:ScheduleByWeek/t:DaysOfWeek", NS)
    assert [child.tag.split("}")[1] for child in days] == ["Monday", "Wednesday", "Friday"]
    assert root.find("t:Triggers/t:CalendarTrigger/t:Repetition/t:Interval", NS).text == "PT30M"
    assert root.find("t:Triggers/t:CalendarTrigger/t:Repetition/t:Duration", NS).text == "PT3H"
    assert root.find("t:Settings/t:DisallowStartIfOnBatteries", NS).text == "false"
    assert root.find("t:Settings/t:StartWhenAvailable", NS).text == "true"
    assert root.find("t:Actions/t:Exec/t:Command", NS).text == launcher[0]
    assert root.find("t:Actions/t:Exec/t:Arguments", NS).text == "-m zibaldone remind fire --moment sera"
    mattina = ElementTree.fromstring(plan.create[0].xml.split("\n", 1)[1])
    assert mattina.find("t:Triggers/t:CalendarTrigger/t:ScheduleByDay/t:DaysInterval", NS).text == "1"


def test_short_window_has_no_repetition() -> None:
    plan = plan_install(ReminderConfig(window_minutes=20), ["zbone.exe"], MONDAY)
    assert plan.create[0].repeat_minutes is None and "<Repetition>" not in plan.create[0].xml


def test_plan_refuses_when_reminders_are_off() -> None:
    with pytest.raises(TaskSchedulerError, match="spenti"):
        plan_install(replace(ReminderConfig(), enabled=False), ["zbone.exe"], MONDAY)


def test_running_schtasks_is_windows_only() -> None:
    plan = plan_install(ReminderConfig(), ["zbone.exe"], MONDAY)
    with pytest.raises(TaskSchedulerError, match="solo su Windows"):
        install_tasks(plan, platform="linux")
    with pytest.raises(TaskSchedulerError, match="solo su Windows"):
        uninstall_tasks(platform="darwin")


class FakeSchtasks:
    def __init__(self, existing=()) -> None:
        self.existing, self.calls, self.xml = set(existing), [], {}

    def __call__(self, args, **kwargs):
        import subprocess
        from pathlib import Path

        self.calls.append(args)
        code = 0
        if args[1] == "/Create":
            self.xml[args[4]] = Path(args[6]).read_text(encoding="utf-16")
        elif args[1] == "/Query":
            code = 0 if args[3] in self.existing else 1
        return subprocess.CompletedProcess(args, code, stdout="", stderr="")


def test_install_and_uninstall_with_a_fake_schtasks() -> None:
    config = ReminderConfig().with_moment(MomentConfig("sera", enabled=False))
    runner = FakeSchtasks(existing={task_name("sera")})
    results = install_tasks(plan_install(config, ["zbone.exe"], MONDAY), runner=runner, platform="win32")
    assert [(result.name, result.action, result.ok) for result in results] == [
        (task_name("mattina"), "creata", True),
        (task_name("meta_giornata"), "creata", True),
        (task_name("sera"), "tolta", True),
    ]
    assert runner.xml[task_name("mattina")].startswith('<?xml version="1.0" encoding="UTF-16"?>')
    runner = FakeSchtasks(existing={task_name("mattina")})
    results = uninstall_tasks(runner=runner, platform="win32")
    assert [result.action for result in results] == ["tolta", "assente", "assente"]
    assert ["schtasks", "/Delete", "/F", "/TN", task_name("mattina")] in runner.calls
    assert all_task_names() == [task_name(moment) for moment in MOMENTS]


def test_night_prompt_shows_between_midnight_and_five_only() -> None:
    assert night_prompt(datetime(2026, 10, 31, 2, 30)).body in NIGHT_MESSAGES
    assert night_prompt(datetime(2026, 10, 31, 0, 0)) is not None
    assert night_prompt(datetime(2026, 10, 31, 4, 59)) is not None
    for hour in (5, 12, 22, 23):
        assert night_prompt(datetime(2026, 10, 31, hour, 0)) is None


def test_night_prompt_rotates_by_date_and_is_not_a_moment() -> None:
    first = night_prompt(datetime(2026, 10, 31, 1, 0))
    assert first == night_prompt(datetime(2026, 10, 31, 4, 0))  # same day, same text
    assert len({night_prompt(datetime(2026, 11, day, 1, 0)).body for day in range(1, 5)}) == len(NIGHT_MESSAGES)
    assert first.title == "Notti insonni" and first.template == "pannychis" and "pannychis" not in MOMENTS
