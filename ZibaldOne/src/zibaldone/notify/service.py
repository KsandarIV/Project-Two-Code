"""The reminder workflow shared by the CLI and the Flet interface.

Reads the entries, the settings and the log; asks `core.reminders` what is due;
hands the reminders to a `Notifier`; logs what was delivered. The caller passes
`now`, so the UI and the tests choose the clock.

Flet, in short:
- at start: `in_app_reminder(store, folder, now)` for a banner (logs nothing);
- every few minutes while open: `fire_due_reminders(store, folder, now, notifier)`,
  with `get_notifier()` in the background, or with a notifier of your own whose
  `send` shows an in-app banner (then the system notification is not repeated).
"""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, FrozenSet, Optional, Set, Tuple

from zibaldone.core.reminders import (
    MOMENTS,
    BackoffSuggestion,
    MomentCheck,
    Reminder,
    ReminderConfig,
    ReminderLog,
    UpcomingReminder,
    backoff_suggestions,
    check_all,
    compose_reminder,
    config_warnings,
    in_app_prompt,
    next_reminder,
    record_sent,
    resolve_outcomes,
    streak,
)
from zibaldone.notify import Notifier, get_notifier
from zibaldone.storage.database import Store
from zibaldone.storage.reminder_log import load_log, load_reminder_config, save_log

REASON_NO_TEMPLATE = "modello '{moment}' non installato (zbone pack install diario)"


@dataclass(frozen=True)
class WritingHistory:
    """Which templates have entries on which day (the day an entry is about)."""

    written_by_day: Dict[date, FrozenSet[str]]

    @property
    def days(self) -> FrozenSet[date]:
        return frozenset(self.written_by_day)

    def written_on(self, day: date) -> FrozenSet[str]:
        return self.written_by_day.get(day, frozenset())


def writing_history(store: Store) -> WritingHistory:
    by_day: Dict[date, Set[str]] = {}
    for entry in store.list_entries(newest_first=False):
        by_day.setdefault(date.fromisoformat(entry.day), set()).add(entry.template)
    return WritingHistory({day: frozenset(templates) for day, templates in by_day.items()})


@dataclass(frozen=True)
class ReminderOverview:
    now: datetime
    config: ReminderConfig
    log: ReminderLog  # outcomes resolved against the entries
    written_today: FrozenSet[str]
    streak_days: int
    checks: Tuple[MomentCheck, ...]
    due: Tuple[Reminder, ...]
    upcoming: Optional[UpcomingReminder]
    suggestions: Tuple[BackoffSuggestion, ...]
    missing_templates: Tuple[str, ...]
    warnings: Tuple[str, ...]


def reminder_overview(store: Store, folder: Path, now: datetime) -> ReminderOverview:
    """Everything `zbone remind status` shows. Reads only; writes nothing."""
    now = now.replace(tzinfo=None)
    today = now.date()
    config = load_reminder_config(folder)
    history = writing_history(store)
    log = resolve_outcomes(load_log(folder), history.written_by_day, today)
    written_today = history.written_on(today)
    streak_days = streak(history.days, today)
    installed = {template.slug for template in store.list_templates()}
    missing = tuple(moment.key for moment in config.moments if moment.enabled and moment.key not in installed)
    checks = tuple(
        MomentCheck(check.moment, False, REASON_NO_TEMPLATE.format(moment=check.moment), check.window_start, check.window_end)
        if check.due and check.moment in missing
        else check
        for check in check_all(config, now, written_today, log)
    )
    return ReminderOverview(
        now=now,
        config=config,
        log=log,
        written_today=written_today,
        streak_days=streak_days,
        checks=checks,
        due=tuple(compose_reminder(check.moment, today, streak_days) for check in checks if check.due),
        upcoming=next_reminder(config, now, written_today, log),
        suggestions=tuple(backoff_suggestions(config, log)),
        missing_templates=missing,
        warnings=tuple(config_warnings(config)),
    )


@dataclass(frozen=True)
class FireResult:
    overview: ReminderOverview
    due: Tuple[Reminder, ...]
    sent: Tuple[Reminder, ...]
    failed: Tuple[Reminder, ...]
    via: str = ""


def fire_due_reminders(
    store: Store,
    folder: Path,
    now: datetime,
    notifier: Optional[Notifier] = None,
    moment: Optional[str] = None,
    dry_run: bool = False,
) -> FireResult:
    """Send the reminders due now (only `moment`'s, if given) and log the delivered ones.

    With `dry_run` nothing is sent or written. A reminder the notifier could not
    deliver is not logged, so a later check tries again inside its window.
    """
    if moment is not None and moment not in MOMENTS:
        raise ValueError(f"momento sconosciuto '{moment}': scegli tra {', '.join(MOMENTS)}")
    overview = reminder_overview(store, folder, now)
    due = tuple(reminder for reminder in overview.due if moment is None or reminder.moment == moment)
    if dry_run or not due:
        return FireResult(overview, due, (), ())
    notifier = notifier or get_notifier()
    log, sent, failed = overview.log, [], []
    for reminder in due:
        if notifier.send(reminder.title, reminder.body):
            log = record_sent(log, reminder, overview.now, via=notifier.name)
            sent.append(reminder)
        else:
            failed.append(reminder)
    save_log(folder, log, overview.now.date())
    return FireResult(overview, due, tuple(sent), tuple(failed), via=notifier.name if sent else "")


def in_app_reminder(store: Store, folder: Path, now: datetime) -> Optional[Reminder]:
    """A gentle banner for the app's home: the latest moment started today and not yet written.

    Ignores quiet hours and the log (the user is already in the app) and logs nothing.
    """
    now = now.replace(tzinfo=None)
    config = load_reminder_config(folder)
    history = writing_history(store)
    installed = {template.slug for template in store.list_templates()}
    reminder = in_app_prompt(config, now, history.written_on(now.date()), streak(history.days, now.date()))
    return reminder if reminder and reminder.moment in installed else None


__all__ = [
    "FireResult",
    "ReminderOverview",
    "WritingHistory",
    "fire_due_reminders",
    "in_app_reminder",
    "reminder_overview",
    "writing_history",
]
