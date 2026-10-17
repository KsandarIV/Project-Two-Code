"""Windows scheduled tasks that run `zbone remind fire --moment <key>`, so reminders arrive with the app closed.

One task per moment switched on, in the Task Scheduler folder `ZibaldOne`. The
task is imported from XML (`schtasks /Create /XML`) because only XML can say:
run on battery too, run once as soon as possible after a missed start, repeat
every 30 minutes inside the reminder window (the rules in `core.reminders`
make sure the reminder still arrives at most once a day).

Building the plan is pure and testable anywhere; `install_tasks` and
`uninstall_tasks` run `schtasks` and refuse on other systems.
"""

import subprocess
import sys
import sysconfig
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, List, Optional, Sequence
from xml.etree import ElementTree

from zibaldone.core.reminders import MOMENT_OF, MOMENTS, MomentConfig, ReminderConfig, format_weekdays

TASK_FOLDER = "ZibaldOne"
TASK_PREFIX = "promemoria-"
TASK_NAMESPACE = "http://schemas.microsoft.com/windows/2004/02/mit/task"
REPEAT_EVERY_MINUTES = 30
TIME_LIMIT = "PT5M"
SCHTASKS = "schtasks"
XML_DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

Runner = Callable[..., subprocess.CompletedProcess]


class TaskSchedulerError(Exception):
    """Scheduled tasks cannot be created or removed here."""


# * — what to run —


def launcher_command(
    python_executable: Optional[str] = None,
    scripts_dir: Optional[str] = None,
    windowless: bool = True,
) -> List[str]:
    """How a scheduled task starts ZibaldOne.

    In order: `pythonw.exe -m zibaldone` next to the interpreter (no console window
    flashing every 30 minutes), the `zbone.exe` launcher in the venv Scripts folder,
    then `<python> -m zibaldone`.
    """
    executable = Path(python_executable or sys.executable)
    folders = [executable.parent]
    scripts = Path(scripts_dir) if scripts_dir else Path(sysconfig.get_path("scripts"))
    if scripts not in folders:
        folders.append(scripts)
    if windowless:
        pythonw = executable.parent / "pythonw.exe"
        if pythonw.is_file():
            return [str(pythonw), "-m", "zibaldone"]
    for folder in folders:
        for name in ("zbone.exe", "zbone"):
            if (folder / name).is_file():
                return [str(folder / name)]
    return [str(executable), "-m", "zibaldone"]


def fire_arguments(moment: str) -> List[str]:
    return ["remind", "fire", "--moment", moment]


# * — the plan —


def task_name(moment: str) -> str:
    return f"{TASK_FOLDER}\\{TASK_PREFIX}{moment}"


@dataclass(frozen=True)
class PlannedTask:
    moment: str
    name: str
    time: str
    weekdays: tuple
    command: List[str]
    repeat_minutes: Optional[int]
    duration_minutes: int
    xml: str

    def create_args(self, xml_path: Path) -> List[str]:
        return [SCHTASKS, "/Create", "/F", "/TN", self.name, "/XML", str(xml_path)]

    def describe(self) -> str:
        repeat = (
            f", riprovata ogni {self.repeat_minutes} minuti per {self.duration_minutes} minuti"
            if self.repeat_minutes
            else ""
        )
        return f"alle {self.time}, {format_weekdays(self.weekdays)}{repeat}"


@dataclass(frozen=True)
class InstallPlan:
    create: List[PlannedTask]
    remove: List[str]  # task names of moments switched off


def _duration(minutes: int) -> str:
    hours, rest = divmod(minutes, 60)
    return "PT" + (f"{hours}H" if hours else "") + (f"{rest}M" if rest else "")


def _add(parent: ElementTree.Element, tag: str, text: Optional[str] = None) -> ElementTree.Element:
    element = ElementTree.SubElement(parent, tag)
    if text is not None:
        element.text = text
    return element


def task_xml(moment: MomentConfig, command: Sequence[str], window_minutes: int, start_day: date) -> str:
    """The Task Scheduler 1.2 definition for one moment, as text (saved as UTF-16 by `install_tasks`)."""
    root = ElementTree.Element("Task", {"version": "1.2", "xmlns": TASK_NAMESPACE})
    info = _add(root, "RegistrationInfo")
    _add(info, "Author", TASK_FOLDER)
    _add(info, "Description", f"ZibaldOne: promemoria {MOMENT_OF[moment.key]}. Si toglie con `zbone remind uninstall`.")

    trigger = _add(_add(root, "Triggers"), "CalendarTrigger")
    if window_minutes > REPEAT_EVERY_MINUTES:
        repetition = _add(trigger, "Repetition")
        _add(repetition, "Interval", _duration(REPEAT_EVERY_MINUTES))
        _add(repetition, "Duration", _duration(window_minutes))
        _add(repetition, "StopAtDurationEnd", "false")
    _add(trigger, "StartBoundary", f"{start_day.isoformat()}T{moment.time}:00")
    _add(trigger, "Enabled", "true")
    if len(moment.weekdays) == 7:
        _add(_add(trigger, "ScheduleByDay"), "DaysInterval", "1")
    else:
        weekly = _add(trigger, "ScheduleByWeek")
        days = _add(weekly, "DaysOfWeek")
        for day in moment.weekdays:
            _add(days, XML_DAY_NAMES[day])
        _add(weekly, "WeeksInterval", "1")

    principal = _add(_add(root, "Principals"), "Principal", None)
    principal.set("id", "Author")
    _add(principal, "LogonType", "InteractiveToken")
    _add(principal, "RunLevel", "LeastPrivilege")

    settings = _add(root, "Settings")
    for tag, value in (
        ("MultipleInstancesPolicy", "IgnoreNew"),
        ("DisallowStartIfOnBatteries", "false"),
        ("StopIfGoingOnBatteries", "false"),
        ("AllowHardTerminate", "true"),
        ("StartWhenAvailable", "true"),
        ("RunOnlyIfNetworkAvailable", "false"),
        ("AllowStartOnDemand", "true"),
        ("Enabled", "true"),
        ("Hidden", "false"),
        ("RunOnlyIfIdle", "false"),
        ("WakeToRun", "false"),
        ("ExecutionTimeLimit", TIME_LIMIT),
        ("Priority", "7"),
    ):
        _add(settings, tag, value)

    actions = _add(root, "Actions")
    actions.set("Context", "Author")
    action = _add(actions, "Exec")
    _add(action, "Command", command[0])
    _add(action, "Arguments", subprocess.list2cmdline([*command[1:], *fire_arguments(moment.key)]))
    body = ElementTree.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-16"?>\n' + body


def plan_install(config: ReminderConfig, launcher: Sequence[str], today: date) -> InstallPlan:
    """One task per moment switched on; moments switched off have their task removed."""
    if not config.enabled:
        raise TaskSchedulerError("i promemoria sono spenti: accendili con `zbone remind config --on`, oppure togli le attività con `zbone remind uninstall`")
    create, remove = [], []
    for moment in config.moments:
        if not moment.enabled:
            remove.append(task_name(moment.key))
            continue
        repeat = REPEAT_EVERY_MINUTES if config.window_minutes > REPEAT_EVERY_MINUTES else None
        create.append(
            PlannedTask(
                moment=moment.key,
                name=task_name(moment.key),
                time=moment.time,
                weekdays=moment.weekdays,
                command=[*launcher, *fire_arguments(moment.key)],
                repeat_minutes=repeat,
                duration_minutes=config.window_minutes,
                xml=task_xml(moment, launcher, config.window_minutes, today),
            )
        )
    return InstallPlan(create=create, remove=remove)


def query_args(name: str) -> List[str]:
    return [SCHTASKS, "/Query", "/TN", name]


def delete_args(name: str) -> List[str]:
    return [SCHTASKS, "/Delete", "/F", "/TN", name]


def all_task_names() -> List[str]:
    return [task_name(moment) for moment in MOMENTS]


# * — running schtasks (Windows only) —


@dataclass(frozen=True)
class TaskResult:
    name: str
    action: str  # "creata", "tolta", "assente"
    ok: bool
    detail: str = ""


def _require_windows(platform: str) -> None:
    if not platform.startswith("win"):
        raise TaskSchedulerError(f"le attività pianificate si creano solo su Windows (questo sistema è {platform})")


def _run(runner: Runner, args: List[str]) -> subprocess.CompletedProcess:
    return runner(args, capture_output=True, text=True, errors="replace", check=False)


def _detail(result: subprocess.CompletedProcess) -> str:
    return (result.stderr or result.stdout or "").strip()


def _remove(name: str, runner: Runner) -> TaskResult:
    if _run(runner, query_args(name)).returncode != 0:
        return TaskResult(name, "assente", True)
    result = _run(runner, delete_args(name))
    return TaskResult(name, "tolta", result.returncode == 0, _detail(result))


def install_tasks(plan: InstallPlan, runner: Runner = subprocess.run, platform: str = sys.platform) -> List[TaskResult]:
    """Create (or replace) the planned tasks and remove those of moments switched off."""
    _require_windows(platform)
    results: List[TaskResult] = []
    with tempfile.TemporaryDirectory(prefix="zibaldone-tasks-") as folder:
        for task in plan.create:
            xml_path = Path(folder) / f"{TASK_PREFIX}{task.moment}.xml"
            xml_path.write_text(task.xml, encoding="utf-16")
            result = _run(runner, task.create_args(xml_path))
            results.append(TaskResult(task.name, "creata", result.returncode == 0, _detail(result)))
    results.extend(_remove(name, runner) for name in plan.remove)
    return results


def uninstall_tasks(runner: Runner = subprocess.run, platform: str = sys.platform) -> List[TaskResult]:
    """Remove every ZibaldOne reminder task; missing ones are fine."""
    _require_windows(platform)
    return [_remove(name, runner) for name in all_task_names()]


__all__ = [
    "InstallPlan",
    "PlannedTask",
    "TaskResult",
    "TaskSchedulerError",
    "all_task_names",
    "delete_args",
    "install_tasks",
    "launcher_command",
    "plan_install",
    "task_name",
    "task_xml",
    "uninstall_tasks",
]
