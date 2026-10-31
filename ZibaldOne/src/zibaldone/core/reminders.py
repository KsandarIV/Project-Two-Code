"""Reminders that encourage writing: what to notify, and when (ADR-0008).

Pure and deterministic: every function receives `now` (a naive local datetime)
or `today`; nothing here reads the clock, the disk or the network. Delivery
lives in `zibaldone.notify`, the log file in `zibaldone.storage.reminder_log`.

Rules, for each moment of the day (mattina, meta_giornata, sera):
- at most one reminder per moment per day;
- nothing when that moment's entry is already written today;
- nothing during quiet hours, on days not chosen, or when switched off;
- a reminder is due from its time until `window_minutes` later, or until the
  next moment starts, or midnight: a late check still fires it once;
- after 3 ignored reminders in a row the app proposes to thin them out,
  it never switches them off by itself.
"""

import re
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

# * — moments and defaults —

MOMENTS: Tuple[str, ...] = ("mattina", "meta_giornata", "sera")
MOMENT_LABELS: Dict[str, str] = {"mattina": "Mattina", "meta_giornata": "Metà giornata", "sera": "Sera"}
MOMENT_OF: Dict[str, str] = {"mattina": "della mattina", "meta_giornata": "di metà giornata", "sera": "della sera"}
DEFAULT_TIMES: Dict[str, str] = {"mattina": "08:30", "meta_giornata": "13:30", "sera": "21:30"}
DEFAULT_QUIET_START = "22:30"
DEFAULT_QUIET_END = "08:00"
DEFAULT_WINDOW_MINUTES = 180
MIN_WINDOW_MINUTES = 15
MAX_WINDOW_MINUTES = 720
IGNORED_BEFORE_BACKOFF = 3
LOG_KEEP_DAYS = 60
LOG_FORMAT = 1
SETTINGS_KEY = "reminders"
APP_TITLE = "ZibaldOne"

ALL_WEEKDAYS: Tuple[int, ...] = tuple(range(7))
WEEKDAY_NAMES: Tuple[str, ...] = ("lun", "mar", "mer", "gio", "ven", "sab", "dom")
WEEKDAY_FULL_NAMES: Tuple[str, ...] = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")
WEEKDAY_GROUPS: Dict[str, Tuple[int, ...]] = {
    "tutti": ALL_WEEKDAYS,
    "sempre": ALL_WEEKDAYS,
    "feriali": (0, 1, 2, 3, 4),
    "weekend": (5, 6),
}

OUTCOME_PENDING = "pending"
OUTCOME_WRITTEN = "written"
OUTCOME_IGNORED = "ignored"
OUTCOMES: Tuple[str, ...] = (OUTCOME_PENDING, OUTCOME_WRITTEN, OUTCOME_IGNORED)

# * — messages: short, gentle, never about what the user wrote (lock screens) —

MESSAGES: Dict[str, Tuple[str, ...]] = {
    "mattina": (
        "Due righe sulla tua mattina?",
        "Com'è iniziata la giornata? Bastano un paio di minuti.",
        "Un'intenzione per oggi? Il tuo zibaldone è qui.",
        "Buongiorno! Ti va di annotare come ti senti?",
        "Un caffè e due righe: la mattina è un buon momento.",
    ),
    "meta_giornata": (
        "Metà giornata: com'è andata finora?",
        "Una pausa e due righe a metà giornata?",
        "Un appunto veloce su come procede la giornata?",
        "Un respiro, e un pensiero per il tuo zibaldone.",
    ),
    "sera": (
        "Com'è andata oggi? Due righe prima di chiudere la giornata.",
        "Una cosa bella di oggi? Il tuo zibaldone ti ascolta.",
        "La giornata si chiude: ti va di fissarla in poche righe?",
        "Un momento per te, prima di dormire: com'è andata?",
    ),
}
MILESTONE_MESSAGES: Tuple[str, ...] = (
    "{days} giorni di fila con il tuo zibaldone: che bella costanza!",
    "Sei a {days} giorni di fila. Festeggiamo con due righe?",
    "{days} giorni di fila! Il tuo zibaldone cresce con te.",
)
# 0.3.3: the night banner (Pannychis). Not a fourth moment: no notification, only the banner in Oggi.
NIGHT_START = time(0, 0)
NIGHT_END = time(5, 0)
NIGHT_LABEL = "Notti insonni"
NIGHT_TEMPLATE = "pannychis"
NIGHT_MESSAGES: Tuple[str, ...] = (
    "Non riesci a dormire? Cosa ti tiene sveglio? Scriverlo potrebbe aiutarti a riconciliare il sonno.",
    "Sveglio a quest'ora? Metti sulla pagina quello che ti gira in testa: domani sarà più leggero.",
    "Una notte lunga? Scrivi cosa ti pesa, poi lascialo qui fino a domattina.",
    "Il sonno non arriva? Due righe su ciò che hai in mente possono aiutare a fare spazio.",
)
STREAK_MILESTONES: Tuple[int, ...] = (3, 7, 14, 21, 30, 50, 75, 100, 150, 200, 250, 300, 365)

# * — reasons shown by `zbone remind status` and `fire` —

REASON_DUE = "da inviare adesso"
REASON_GLOBAL_OFF = "promemoria spenti"
REASON_MOMENT_OFF = "momento spento"
REASON_NOT_TODAY = "oggi non è tra i giorni scelti"
REASON_WRITTEN = "voce già scritta oggi"
REASON_SENT = "promemoria già inviato oggi"
REASON_QUIET = "ore di silenzio ({hours})"
REASON_EARLY = "arriverà dalle {time}"
REASON_LATE = "finestra chiusa alle {time}"

TIME_PATTERN = re.compile(r"^(\d{1,2})[:.](\d{2})$")


# * — parsing and formatting —


def parse_clock(raw: Any, what: str = "orario") -> str:
    """Accept 'HH:MM' (or 'H:MM', 'H.MM') and return 'HH:MM'."""
    match = TIME_PATTERN.match(raw.strip()) if isinstance(raw, str) else None
    if match:
        hours, minutes = int(match.group(1)), int(match.group(2))
        if hours <= 23 and minutes <= 59:
            return f"{hours:02d}:{minutes:02d}"
    raise ValueError(f"{what} non valido: '{raw}' (usa HH:MM, per esempio 08:30)")


def clock_of(text: str) -> time:
    hours, minutes = text.split(":")
    return time(int(hours), int(minutes))


def _plain(text: str) -> str:
    """Lowercase without accents: 'Lunedì' -> 'lunedi'."""
    decomposed = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _weekday_number(token: str) -> int:
    plain = _plain(token)
    for number, (short, full) in enumerate(zip(WEEKDAY_NAMES, WEEKDAY_FULL_NAMES)):
        if plain in (short, _plain(full)):
            return number
    raise ValueError(
        f"giorno non valido: '{token.strip()}' (usa lun, mar, mer, gio, ven, sab, dom, "
        "un intervallo come lun-ven, oppure tutti, feriali, weekend)"
    )


def parse_weekdays(raw: str) -> Tuple[int, ...]:
    """Turn 'lun,mar,mer', 'lun-ven', 'feriali', 'weekend' or 'tutti' into weekday numbers (0 = Monday)."""
    days: Set[int] = set()
    for token in re.split(r"[,;]", raw):
        if not token.strip():
            continue
        plain = _plain(token)
        if plain in WEEKDAY_GROUPS:
            days.update(WEEKDAY_GROUPS[plain])
            continue
        if "-" in plain or "–" in token:
            first, _, last = token.replace("–", "-").partition("-")
            start, end = _weekday_number(first), _weekday_number(last)
            days.update((start + step) % 7 for step in range((end - start) % 7 + 1))
            continue
        days.add(_weekday_number(token))
    if not days:
        raise ValueError("scegli almeno un giorno (oppure spegni il momento)")
    return tuple(sorted(days))


def format_weekdays(weekdays: Sequence[int]) -> str:
    """'tutti i giorni', 'lun–ven', 'lun, mer, ven'… Runs of 3 or more days become ranges."""
    days = sorted(set(weekdays))
    if days == list(ALL_WEEKDAYS):
        return "tutti i giorni"
    parts: List[str] = []
    index = 0
    while index < len(days):
        end = index
        while end + 1 < len(days) and days[end + 1] == days[end] + 1:
            end += 1
        if end - index >= 2:
            parts.append(f"{WEEKDAY_NAMES[days[index]]}–{WEEKDAY_NAMES[days[end]]}")
        else:
            parts.extend(WEEKDAY_NAMES[day] for day in days[index : end + 1])
        index = end + 1
    return ", ".join(parts)


def parse_moment(raw: str) -> str:
    """Accept a moment key or its label ('Metà giornata') and return the key."""
    plain = _plain(raw).replace(" ", "_")
    for key in MOMENTS:
        if plain in (key, _plain(MOMENT_LABELS[key]).replace(" ", "_")):
            return key
    raise ValueError(f"momento sconosciuto '{raw}': scegli tra {', '.join(MOMENTS)}")


def _require_bool(value: Any, what: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{what} deve essere true o false, non '{value}'")
    return value


def _require_keys(data: Mapping[str, Any], allowed: Iterable[str], where: str) -> None:
    if not isinstance(data, Mapping):
        raise ValueError(f"{where}: mi aspettavo un oggetto JSON")
    unknown = sorted(set(data) - set(allowed))
    if unknown:
        raise ValueError(f"{where}: campi sconosciuti {', '.join(unknown)}")


# * — configuration —


@dataclass(frozen=True)
class MomentConfig:
    """One moment of the day: on or off, at what time, on which weekdays."""

    key: str
    enabled: bool = True
    time: str = ""
    weekdays: Tuple[int, ...] = ALL_WEEKDAYS
    backoff_dismissed_on: Optional[date] = None

    def __post_init__(self) -> None:
        if self.key not in MOMENTS:
            raise ValueError(f"momento sconosciuto '{self.key}': scegli tra {', '.join(MOMENTS)}")
        label = MOMENT_LABELS[self.key]
        _require_bool(self.enabled, f"{label}: 'enabled'")
        object.__setattr__(self, "time", parse_clock(self.time or DEFAULT_TIMES[self.key], f"{label}: orario"))
        if not isinstance(self.weekdays, (tuple, list)) or not self.weekdays:
            raise ValueError(f"{label}: scegli almeno un giorno (oppure spegni il momento)")
        if any(isinstance(day, bool) or not isinstance(day, int) or not 0 <= day <= 6 for day in self.weekdays):
            raise ValueError(f"{label}: i giorni vanno da 0 (lunedì) a 6 (domenica)")
        object.__setattr__(self, "weekdays", tuple(sorted(set(self.weekdays))))

    @property
    def label(self) -> str:
        return MOMENT_LABELS[self.key]

    @property
    def clock(self) -> time:
        return clock_of(self.time)

    def runs_on(self, day: date) -> bool:
        return self.enabled and day.weekday() in self.weekdays

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "time": self.time,
            "weekdays": [WEEKDAY_NAMES[day] for day in self.weekdays],
            "backoff_dismissed_on": self.backoff_dismissed_on.isoformat() if self.backoff_dismissed_on else None,
        }

    @classmethod
    def from_dict(cls, key: str, data: Mapping[str, Any]) -> "MomentConfig":
        where = MOMENT_LABELS.get(key, key)
        _require_keys(data, ("enabled", "time", "weekdays", "backoff_dismissed_on"), where)
        weekdays = data.get("weekdays", list(WEEKDAY_NAMES))
        if not isinstance(weekdays, list) or not all(isinstance(day, str) for day in weekdays):
            raise ValueError(f"{where}: 'weekdays' deve essere una lista come [\"lun\", \"mer\"]")
        dismissed = data.get("backoff_dismissed_on")
        try:
            dismissed_day = date.fromisoformat(dismissed) if dismissed else None
        except (TypeError, ValueError):
            raise ValueError(f"{where}: data non valida in 'backoff_dismissed_on': '{dismissed}'") from None
        return cls(
            key=key,
            enabled=data.get("enabled", True),
            time=data.get("time", DEFAULT_TIMES[key]),
            weekdays=parse_weekdays(",".join(weekdays)) if weekdays else (),
            backoff_dismissed_on=dismissed_day,
        )


@dataclass(frozen=True)
class QuietHours:
    """No reminder in this range. `start` after `end` means the range crosses midnight."""

    enabled: bool = True
    start: str = DEFAULT_QUIET_START
    end: str = DEFAULT_QUIET_END

    def __post_init__(self) -> None:
        _require_bool(self.enabled, "ore di silenzio: 'enabled'")
        object.__setattr__(self, "start", parse_clock(self.start, "inizio delle ore di silenzio"))
        object.__setattr__(self, "end", parse_clock(self.end, "fine delle ore di silenzio"))
        if self.start == self.end:
            raise ValueError("le ore di silenzio devono iniziare e finire a orari diversi (oppure spegnile)")

    @property
    def label(self) -> str:
        return f"{self.start}–{self.end}"

    def contains(self, clock: time) -> bool:
        if not self.enabled:
            return False
        start, end = clock_of(self.start), clock_of(self.end)
        if start < end:
            return start <= clock < end
        return clock >= start or clock < end

    def ends_after(self, moment: datetime) -> datetime:
        """The first end of quiet hours after `moment` (today or tomorrow)."""
        end = datetime.combine(moment.date(), clock_of(self.end))
        return end if end > moment else end + timedelta(days=1)

    def to_dict(self) -> Dict[str, Any]:
        return {"enabled": self.enabled, "start": self.start, "end": self.end}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "QuietHours":
        _require_keys(data, ("enabled", "start", "end"), "ore di silenzio")
        return cls(
            enabled=data.get("enabled", True),
            start=data.get("start", DEFAULT_QUIET_START),
            end=data.get("end", DEFAULT_QUIET_END),
        )


def default_moments() -> Tuple[MomentConfig, ...]:
    return tuple(MomentConfig(key=key) for key in MOMENTS)


@dataclass(frozen=True)
class ReminderConfig:
    """Every reminder setting, saved under `reminders` in settings.json."""

    enabled: bool = True
    moments: Tuple[MomentConfig, ...] = field(default_factory=default_moments)
    quiet_hours: QuietHours = field(default_factory=QuietHours)
    window_minutes: int = DEFAULT_WINDOW_MINUTES

    def __post_init__(self) -> None:
        _require_bool(self.enabled, "promemoria: 'enabled'")
        window = self.window_minutes
        if isinstance(window, bool) or not isinstance(window, int) or not MIN_WINDOW_MINUTES <= window <= MAX_WINDOW_MINUTES:
            raise ValueError(f"la finestra deve essere un numero di minuti tra {MIN_WINDOW_MINUTES} e {MAX_WINDOW_MINUTES}, non '{window}'")
        if tuple(moment.key for moment in self.moments) != MOMENTS:
            raise ValueError(f"servono i 3 momenti, in quest'ordine: {', '.join(MOMENTS)}")
        times: Dict[str, str] = {}
        for moment in self.moments:
            if moment.enabled and moment.time in times:
                raise ValueError(
                    f"{MOMENT_LABELS[times[moment.time]]} e {moment.label} hanno lo stesso orario ({moment.time}): cambiane uno"
                )
            if moment.enabled:
                times[moment.time] = moment.key

    def moment(self, key: str) -> MomentConfig:
        return self.moments[MOMENTS.index(parse_moment(key))]

    def with_moment(self, updated: MomentConfig) -> "ReminderConfig":
        return replace(self, moments=tuple(updated if moment.key == updated.key else moment for moment in self.moments))

    def active_moments(self, day: date) -> List[MomentConfig]:
        """Moments switched on and scheduled on `day`, by time."""
        if not self.enabled:
            return []
        return sorted((moment for moment in self.moments if moment.runs_on(day)), key=lambda moment: moment.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "window_minutes": self.window_minutes,
            "quiet_hours": self.quiet_hours.to_dict(),
            "moments": {moment.key: moment.to_dict() for moment in self.moments},
        }

    @classmethod
    def from_dict(cls, data: Optional[Mapping[str, Any]]) -> "ReminderConfig":
        if data is None:
            return cls()
        _require_keys(data, ("enabled", "window_minutes", "quiet_hours", "moments"), "promemoria")
        moments_data = data.get("moments", {})
        _require_keys(moments_data, MOMENTS, "promemoria, momenti")
        return cls(
            enabled=data.get("enabled", True),
            moments=tuple(MomentConfig.from_dict(key, moments_data.get(key, {})) for key in MOMENTS),
            quiet_hours=QuietHours.from_dict(data.get("quiet_hours", {})),
            window_minutes=data.get("window_minutes", DEFAULT_WINDOW_MINUTES),
        )


def config_from_settings(settings: Mapping[str, Any]) -> ReminderConfig:
    """Read the `reminders` key of settings.json; defaults when it is missing."""
    try:
        return ReminderConfig.from_dict(settings.get(SETTINGS_KEY))
    except ValueError as error:
        raise ValueError(f"impostazioni dei promemoria non valide in settings.json: {error}") from None


def settings_with_config(settings: Mapping[str, Any], config: ReminderConfig) -> Dict[str, Any]:
    """Return a copy of `settings` with the reminder configuration in place."""
    return {**settings, SETTINGS_KEY: config.to_dict()}


def config_warnings(config: ReminderConfig) -> List[str]:
    """Settings that are valid but probably not what the user wants."""
    warnings: List[str] = []
    quiet = config.quiet_hours
    for moment in config.moments:
        if not moment.enabled or not quiet.contains(moment.clock):
            continue
        start = datetime.combine(date(2000, 1, 3), moment.clock)
        end = min(start + timedelta(minutes=config.window_minutes), datetime.combine(start.date() + timedelta(days=1), time(0)))
        resume = quiet.ends_after(start)
        if resume < end:
            warnings.append(f"{moment.label}: le {moment.time} cadono nelle ore di silenzio ({quiet.label}), il promemoria arriverà dalle {quiet.end}")
        else:
            warnings.append(f"{moment.label}: le {moment.time} cadono nelle ore di silenzio ({quiet.label}), il promemoria non arriverà mai")
    if config.enabled and not any(moment.enabled for moment in config.moments):
        warnings.append("i promemoria sono accesi ma tutti i momenti sono spenti")
    return warnings


# * — the reminder log (what was sent, and whether an entry followed) —


@dataclass(frozen=True)
class SentReminder:
    moment: str
    day: date
    sent_at: datetime
    via: str = ""
    outcome: str = OUTCOME_PENDING

    def to_dict(self) -> Dict[str, Any]:
        return {
            "moment": self.moment,
            "day": self.day.isoformat(),
            "sent_at": self.sent_at.isoformat(timespec="seconds"),
            "via": self.via,
            "outcome": self.outcome,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SentReminder":
        _require_keys(data, ("moment", "day", "sent_at", "via", "outcome"), "registro dei promemoria")
        moment, outcome = data.get("moment"), data.get("outcome", OUTCOME_PENDING)
        if moment not in MOMENTS:
            raise ValueError(f"registro dei promemoria: momento sconosciuto '{moment}'")
        if outcome not in OUTCOMES:
            raise ValueError(f"registro dei promemoria: esito sconosciuto '{outcome}'")
        try:
            day = date.fromisoformat(data["day"])
            sent_at = datetime.fromisoformat(data["sent_at"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("registro dei promemoria: data o ora non valida") from None
        return cls(moment=moment, day=day, sent_at=sent_at, via=str(data.get("via", "")), outcome=outcome)


@dataclass(frozen=True)
class ReminderLog:
    records: Tuple[SentReminder, ...] = ()

    def was_sent(self, moment: str, day: date) -> bool:
        return any(record.moment == moment and record.day == day for record in self.records)

    def for_moment(self, moment: str) -> List[SentReminder]:
        """Records of one moment, newest first."""
        return sorted((record for record in self.records if record.moment == moment), key=lambda record: record.sent_at, reverse=True)

    def to_dict(self) -> Dict[str, Any]:
        return {"format": LOG_FORMAT, "records": [record.to_dict() for record in self.records]}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ReminderLog":
        _require_keys(data, ("format", "records"), "registro dei promemoria")
        if data.get("format", LOG_FORMAT) != LOG_FORMAT:
            raise ValueError("il registro dei promemoria ha un formato più recente: aggiorna ZibaldOne")
        records = data.get("records", [])
        if not isinstance(records, list):
            raise ValueError("registro dei promemoria: 'records' deve essere una lista")
        return cls(records=tuple(SentReminder.from_dict(record) for record in records))


def record_sent(log: ReminderLog, reminder: "Reminder", sent_at: datetime, via: str = "") -> ReminderLog:
    entry = SentReminder(moment=reminder.moment, day=reminder.day, sent_at=_local(sent_at), via=via)
    return ReminderLog(records=log.records + (entry,))


def resolve_outcomes(log: ReminderLog, written_by_day: Mapping[date, Iterable[str]], today: date) -> ReminderLog:
    """Mark each reminder 'written' when that day's entry exists, 'ignored' once the day is over without it."""
    resolved = []
    for record in log.records:
        if record.moment in set(written_by_day.get(record.day, ())):
            outcome = OUTCOME_WRITTEN
        elif record.day < today:
            outcome = OUTCOME_IGNORED
        else:
            outcome = OUTCOME_PENDING
        resolved.append(replace(record, outcome=outcome))
    return ReminderLog(records=tuple(resolved))


def prune_log(log: ReminderLog, today: date, keep_days: int = LOG_KEEP_DAYS) -> ReminderLog:
    """Keep only the last `keep_days` days."""
    oldest = today - timedelta(days=keep_days)
    return ReminderLog(records=tuple(record for record in log.records if record.day >= oldest))


# * — what is due now —


@dataclass(frozen=True)
class Reminder:
    """A notification to show. Title and body never contain entry data."""

    moment: str
    day: date
    title: str
    body: str
    milestone: bool = False


@dataclass(frozen=True)
class MomentCheck:
    """Whether one moment is due now, and why (or why not) in Italian."""

    moment: str
    due: bool
    reason: str
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None


def _local(now: datetime) -> datetime:
    """Treat `now` as local wall-clock time: timezone info is dropped, never converted."""
    return now.replace(tzinfo=None)


def window_of(config: ReminderConfig, key: str, day: date) -> Tuple[datetime, datetime]:
    """When the moment's reminder may fire on `day`: from its time until the window,
    the next active moment or midnight, whichever comes first."""
    moment = config.moment(key)
    start = datetime.combine(day, moment.clock)
    end = min(start + timedelta(minutes=config.window_minutes), datetime.combine(day + timedelta(days=1), time(0)))
    for other in config.active_moments(day):
        other_start = datetime.combine(day, other.clock)
        if other.key != key and start < other_start < end:
            end = other_start
    return start, end


def check_moment(config: ReminderConfig, key: str, now: datetime, written_today: Iterable[str], log: ReminderLog) -> MomentCheck:
    """Apply every rule to one moment, in the order the user would ask about them."""
    now = _local(now)
    key = parse_moment(key)
    moment, today = config.moment(key), now.date()
    if not config.enabled:
        return MomentCheck(key, False, REASON_GLOBAL_OFF)
    if not moment.enabled:
        return MomentCheck(key, False, REASON_MOMENT_OFF)
    if today.weekday() not in moment.weekdays:
        return MomentCheck(key, False, REASON_NOT_TODAY)
    start, end = window_of(config, key, today)
    if key in set(written_today):
        return MomentCheck(key, False, REASON_WRITTEN, start, end)
    if log.was_sent(key, today):
        return MomentCheck(key, False, REASON_SENT, start, end)
    if now < start:
        return MomentCheck(key, False, REASON_EARLY.format(time=moment.time), start, end)
    if now >= end:
        return MomentCheck(key, False, REASON_LATE.format(time=end.strftime("%H:%M")), start, end)
    if config.quiet_hours.contains(now.time()):
        return MomentCheck(key, False, REASON_QUIET.format(hours=config.quiet_hours.label), start, end)
    return MomentCheck(key, True, REASON_DUE, start, end)


def check_all(config: ReminderConfig, now: datetime, written_today: Iterable[str], log: ReminderLog) -> List[MomentCheck]:
    written = frozenset(written_today)
    return [check_moment(config, key, now, written, log) for key in MOMENTS]


def due_reminders(
    config: ReminderConfig,
    now: datetime,
    written_today: Iterable[str],
    log: ReminderLog,
    streak_days: int = 0,
) -> List[Reminder]:
    """The reminders to send now, at most one per moment."""
    day = _local(now).date()
    return [
        compose_reminder(check.moment, day, streak_days)
        for check in check_all(config, now, written_today, log)
        if check.due
    ]


def in_app_prompt(config: ReminderConfig, now: datetime, written_today: Iterable[str], streak_days: int = 0) -> Optional[Reminder]:
    """For a banner when the app is open: the latest moment already started today and not yet written.

    Quiet hours, the window and the log do not apply: the user is already in the app.
    """
    now = _local(now)
    written = frozenset(written_today)
    started = [moment for moment in config.active_moments(now.date()) if datetime.combine(now.date(), moment.clock) <= now]
    pending = [moment for moment in started if moment.key not in written]
    return compose_reminder(pending[-1].key, now.date(), streak_days) if pending else None


@dataclass(frozen=True)
class UpcomingReminder:
    moment: str
    at: datetime


def next_reminder(
    config: ReminderConfig,
    now: datetime,
    written_today: Iterable[str] = (),
    log: ReminderLog = ReminderLog(),
    horizon_days: int = 8,
) -> Optional[UpcomingReminder]:
    """The earliest time a reminder could fire, from `now` on (`now` itself when one is due)."""
    now = _local(now)
    written = frozenset(written_today)
    for offset in range(horizon_days):
        day = now.date() + timedelta(days=offset)
        for moment in config.active_moments(day):
            if offset == 0 and (moment.key in written or log.was_sent(moment.key, day)):
                continue
            start, end = window_of(config, moment.key, day)
            candidate = max(start, now)
            if config.quiet_hours.contains(candidate.time()):
                candidate = config.quiet_hours.ends_after(candidate)
            if candidate < end:
                return UpcomingReminder(moment.key, candidate)
    return None


# * — messages and streaks —


def streak(days_with_entries: Iterable[date], today: date) -> int:
    """Consecutive days with at least one entry, ending today or yesterday."""
    days = set(days_with_entries)
    current = today if today in days else today - timedelta(days=1)
    count = 0
    while current in days:
        count += 1
        current -= timedelta(days=1)
    return count


def is_milestone(days: int) -> bool:
    return days in STREAK_MILESTONES or (days > 365 and (days % 100 == 0 or days % 365 == 0))


def reminder_title(moment: str) -> str:
    return f"{APP_TITLE} · {MOMENT_LABELS[moment]}"


def reminder_body(moment: str, day: date, streak_days: int = 0) -> str:
    """A rotating message picked from the date, so the same day always gives the same text.

    A milestone streak gets a celebration; a lost streak is never mentioned.
    """
    seed = day.toordinal() + MOMENTS.index(moment)
    if is_milestone(streak_days):
        return MILESTONE_MESSAGES[seed % len(MILESTONE_MESSAGES)].format(days=streak_days)
    variants = MESSAGES[moment]
    return variants[seed % len(variants)]


def compose_reminder(moment: str, day: date, streak_days: int = 0) -> Reminder:
    return Reminder(
        moment=moment,
        day=day,
        title=reminder_title(moment),
        body=reminder_body(moment, day, streak_days),
        milestone=is_milestone(streak_days),
    )


@dataclass(frozen=True)
class NightPrompt:
    """The banner shown in Oggi between midnight and 5: never a notification (it would wake who sleeps)."""

    title: str
    body: str
    template: str = NIGHT_TEMPLATE


def night_prompt(now: datetime) -> Optional[NightPrompt]:
    """The night message for `now` (naive local time), or None outside 00:00-05:00.

    The text rotates by date, like `reminder_body`; the time of day does not change it.
    """
    if not NIGHT_START <= now.time() < NIGHT_END:
        return None
    return NightPrompt(title=NIGHT_LABEL, body=NIGHT_MESSAGES[now.date().toordinal() % len(NIGHT_MESSAGES)])


# * — back-off: propose fewer reminders, never decide alone —


@dataclass(frozen=True)
class BackoffSuggestion:
    moment: str
    ignored_in_a_row: int
    proposed_weekdays: Tuple[int, ...]
    message: str


def ignored_in_a_row(log: ReminderLog, moment: str, since: Optional[date] = None) -> int:
    """How many of the latest finished reminders of `moment` were ignored, back to the last one followed by an entry.

    Reminders on or before `since` (when the user chose to keep the frequency) do not count.
    Outcomes must be resolved first with `resolve_outcomes`.
    """
    count = 0
    for record in log.for_moment(moment):
        if since is not None and record.day <= since:
            break
        if record.outcome == OUTCOME_PENDING:
            continue
        if record.outcome == OUTCOME_WRITTEN:
            break
        count += 1
    return count


def thinned_weekdays(weekdays: Sequence[int]) -> Tuple[int, ...]:
    """Every other chosen day: all week -> lun, mer, ven, dom; lun–ven -> lun, mer, ven."""
    days = sorted(set(weekdays))
    return tuple(days[::2]) if days else ()


def backoff_suggestions(config: ReminderConfig, log: ReminderLog) -> List[BackoffSuggestion]:
    suggestions: List[BackoffSuggestion] = []
    for moment in config.moments:
        if not (config.enabled and moment.enabled):
            continue
        count = ignored_in_a_row(log, moment.key, moment.backoff_dismissed_on)
        if count < IGNORED_BEFORE_BACKOFF:
            continue
        proposed = thinned_weekdays(moment.weekdays)
        if proposed != moment.weekdays:
            offer = f"Vuoi riceverli meno spesso, per esempio solo {format_weekdays(proposed)}?"
        else:
            offer = "Vuoi spegnerli per un po'? Puoi riaccenderli quando vuoi."
        message = f"Gli ultimi {count} promemoria {MOMENT_OF[moment.key]} sono passati senza una voce, e va benissimo così. {offer}"
        suggestions.append(BackoffSuggestion(moment.key, count, proposed, message))
    return suggestions


def thin_out(config: ReminderConfig, key: str, today: date) -> ReminderConfig:
    """Accept the suggestion: keep every other day, and start counting ignored reminders again."""
    moment = config.moment(key)
    return config.with_moment(replace(moment, weekdays=thinned_weekdays(moment.weekdays), backoff_dismissed_on=today))


def keep_frequency(config: ReminderConfig, key: str, today: date) -> ReminderConfig:
    """Decline the suggestion: same days, and ask again only after 3 more ignored reminders."""
    return config.with_moment(replace(config.moment(key), backoff_dismissed_on=today))


__all__ = [
    "MOMENTS",
    "MOMENT_LABELS",
    "BackoffSuggestion",
    "MomentCheck",
    "MomentConfig",
    "QuietHours",
    "Reminder",
    "ReminderConfig",
    "ReminderLog",
    "SentReminder",
    "UpcomingReminder",
    "backoff_suggestions",
    "check_all",
    "check_moment",
    "compose_reminder",
    "config_from_settings",
    "config_warnings",
    "due_reminders",
    "format_weekdays",
    "ignored_in_a_row",
    "in_app_prompt",
    "is_milestone",
    "keep_frequency",
    "next_reminder",
    "parse_clock",
    "parse_moment",
    "parse_weekdays",
    "prune_log",
    "record_sent",
    "reminder_body",
    "resolve_outcomes",
    "settings_with_config",
    "streak",
    "thin_out",
    "thinned_weekdays",
    "window_of",
]
