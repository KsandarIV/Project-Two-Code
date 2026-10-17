"""`zbone remind …`: gentle reminders to write, for the 3 moments of the day."""

import os
import sys
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Optional

import typer

from zibaldone.cli.common import ensure_consent, fail, open_store
from zibaldone.core.privacy import NOTICE_VERSION
from zibaldone.core.reminders import (
    MOMENT_LABELS,
    MOMENTS,
    WEEKDAY_FULL_NAMES,
    ReminderConfig,
    UpcomingReminder,
    config_warnings,
    format_weekdays,
    is_milestone,
    keep_frequency,
    parse_moment,
    parse_weekdays,
    thin_out,
)
from zibaldone.notify import TerminalNotifier, get_notifier
from zibaldone.notify.service import ReminderOverview, fire_due_reminders, reminder_overview
from zibaldone.notify.windows_tasks import (
    InstallPlan,
    TaskResult,
    TaskSchedulerError,
    all_task_names,
    install_tasks,
    launcher_command,
    plan_install,
    uninstall_tasks,
)
from zibaldone.storage.paths import ENV_DATA_DIR, data_dir
from zibaldone.storage.reminder_log import load_reminder_config, save_reminder_config
from zibaldone.storage.settings import SettingsError, has_consent

remind_app = typer.Typer(help="Promemoria gentili per scrivere: mattina, metà giornata e sera.", no_args_is_help=True)

TEST_TITLE = "ZibaldOne"
TEST_BODY = "Le notifiche funzionano. I promemoria non mostrano mai il testo delle tue voci."
MOMENTS_HINT = ", ".join(MOMENTS)


def current_time() -> datetime:
    """The real clock: the only place the reminder commands read it (tests replace it)."""
    return datetime.now().replace(microsecond=0)


def on_windows() -> bool:
    return sys.platform.startswith("win")


# * — formatting —


def day_text(day: date) -> str:
    return f"{WEEKDAY_FULL_NAMES[day.weekday()]} {day.strftime('%d/%m')}"


def when_text(upcoming: UpcomingReminder, now: datetime) -> str:
    at = upcoming.at
    if at <= now:
        return "adesso"
    if at.date() == now.date():
        return f"oggi alle {at:%H:%M}"
    if at.date() == now.date() + timedelta(days=1):
        return f"domani alle {at:%H:%M}"
    return f"{day_text(at.date())} alle {at:%H:%M}"


def streak_text(days: int) -> str:
    if days == 0:
        return "comincia quando vuoi"
    if days == 1:
        return "1 giorno"
    return f"{days} giorni di fila" + (" — bel traguardo!" if is_milestone(days) else "")


def print_config(config: ReminderConfig) -> None:
    quiet = config.quiet_hours
    typer.echo(f"Promemoria: {'accesi' if config.enabled else 'spenti'}")
    typer.echo(f"Ore di silenzio: {quiet.label if quiet.enabled else 'spente'}")
    typer.echo(f"Finestra: fino a {config.window_minutes} minuti dopo l'orario, o fino al momento successivo")
    for moment in config.moments:
        state = "acceso" if moment.enabled else "spento"
        typer.echo(f"  {moment.label:<14} {moment.time}  {format_weekdays(moment.weekdays):<18} {state}")


def print_suggestions(overview: ReminderOverview) -> None:
    for suggestion in overview.suggestions:
        typer.echo(f"\nSuggerimento: {suggestion.message}")
        current = overview.config.moment(suggestion.moment).weekdays
        if suggestion.proposed_weekdays != current:
            typer.echo(f"  zbone remind config --moment {suggestion.moment} --thin-out   ({format_weekdays(suggestion.proposed_weekdays)})")
        else:
            typer.echo(f"  zbone remind config --moment {suggestion.moment} --off")
        typer.echo(f"  zbone remind config --moment {suggestion.moment} --keep       (lascia così)")


def print_warnings(overview: ReminderOverview) -> None:
    for key in overview.missing_templates:
        typer.echo(f"Attenzione: manca il modello '{key}', installalo con `zbone pack install diario`.")
    for warning in overview.warnings:
        typer.echo(f"Attenzione: {warning}.")


# * — consent for scheduled runs —


def ensure_consent_without_prompt() -> None:
    """A scheduled task has nobody to answer the privacy question: stop instead of waiting."""
    stdin = sys.stdin
    if stdin is not None and stdin.isatty():
        return
    try:
        if has_consent(data_dir(), NOTICE_VERSION):
            return
    except SettingsError as error:
        fail(str(error))
    fail("serve prima il consenso all'avviso privacy: leggilo con `zbone privacy` e accettalo con `zbone privacy accept`")


# * — commands —


@remind_app.command("status")
def show_status() -> None:
    """Mostra i promemoria, le voci di oggi, la serie di giorni e i suggerimenti."""
    with open_store() as store:
        overview = reminder_overview(store, data_dir(), current_time())
    print_config(overview.config)
    typer.echo(f"\nOggi, {day_text(overview.now.date())}:")
    for check in overview.checks:
        if check.moment in overview.written_today:
            typer.echo(f"  ✓ {MOMENT_LABELS[check.moment]:<14} scritta")
        else:
            typer.echo(f"  ○ {MOMENT_LABELS[check.moment]:<14} da scrivere · {check.reason}")
    if overview.upcoming:
        upcoming = overview.upcoming
        typer.echo(f"Prossimo promemoria: {when_text(upcoming, overview.now)} ({MOMENT_LABELS[upcoming.moment]})")
    else:
        typer.echo("Prossimo promemoria: nessuno in programma")
    typer.echo(f"Serie: {streak_text(overview.streak_days)}")
    print_suggestions(overview)
    print_warnings(overview)


@remind_app.command("config")
def configure(
    moment: Optional[str] = typer.Option(None, "--moment", "-m", help=f"il momento da cambiare: {MOMENTS_HINT}"),
    switch: Optional[bool] = typer.Option(None, "--on/--off", help="accende o spegne i promemoria; con --moment solo quel momento"),
    at: Optional[str] = typer.Option(None, "--time", "-t", help="orario HH:MM, per esempio 08:30 (serve --moment)"),
    days: Optional[str] = typer.Option(None, "--days", "-d", help="giorni: lun,mer,ven · lun-ven · feriali · weekend · tutti (senza --moment vale per tutti i momenti)"),
    quiet: Optional[bool] = typer.Option(None, "--quiet/--no-quiet", help="accende o spegne le ore di silenzio"),
    quiet_start: Optional[str] = typer.Option(None, "--quiet-start", help="inizio delle ore di silenzio, HH:MM"),
    quiet_end: Optional[str] = typer.Option(None, "--quiet-end", help="fine delle ore di silenzio, HH:MM"),
    window: Optional[int] = typer.Option(None, "--window", help="per quanti minuti dopo l'orario il promemoria può ancora arrivare"),
    thin: bool = typer.Option(False, "--thin-out", help="dirada i promemoria del momento: un giorno sì e uno no"),
    keep: bool = typer.Option(False, "--keep", help="lascia la frequenza com'è e non proporre di diradare per un po'"),
    reset: bool = typer.Option(False, "--reset", help="torna alle impostazioni predefinite"),
) -> None:
    """Cambia orari, giorni e ore di silenzio dei promemoria; senza opzioni li mostra."""
    ensure_consent()
    folder = data_dir()
    today = current_time().date()
    try:
        original = load_reminder_config(folder)
        config = ReminderConfig() if reset else original
        key = parse_moment(moment) if moment else None
        if key is None and (at is not None or thin or keep):
            raise ValueError(f"--time, --thin-out e --keep valgono per un momento: aggiungi --moment ({MOMENTS_HINT})")
        if thin and keep:
            raise ValueError("scegli --thin-out oppure --keep, non tutti e due")
        weekdays = parse_weekdays(days) if days is not None else None
        if key is not None:
            changes = {name: value for name, value in (("enabled", switch), ("time", at), ("weekdays", weekdays)) if value is not None}
            config = config.with_moment(replace(config.moment(key), **changes))
            if thin:
                before = config.moment(key).weekdays
                config = thin_out(config, key, today)
                if config.moment(key).weekdays == before:
                    typer.echo(f"{MOMENT_LABELS[key]} ha già un solo giorno: per meno promemoria puoi spegnerlo con --off.")
            if keep:
                config = keep_frequency(config, key, today)
        else:
            if switch is not None:
                config = replace(config, enabled=switch)
            if weekdays is not None:
                for each in config.moments:
                    config = config.with_moment(replace(each, weekdays=weekdays))
        quiet_changes = {name: value for name, value in (("enabled", quiet), ("start", quiet_start), ("end", quiet_end)) if value is not None}
        if quiet_changes:
            config = replace(config, quiet_hours=replace(config.quiet_hours, **quiet_changes))
        if window is not None:
            config = replace(config, window_minutes=window)
    except ValueError as error:
        fail(str(error))
    if config != original:
        save_reminder_config(folder, config)
        typer.echo("Impostazioni dei promemoria salvate.\n")
    print_config(config)
    for warning in config_warnings(config):
        typer.echo(f"Attenzione: {warning}.")
    if config != original and on_windows():
        typer.echo("\nSe usi le attività pianificate di Windows, aggiornale con `zbone remind install`.")


@remind_app.command("fire")
def fire(
    moment: Optional[str] = typer.Option(None, "--moment", "-m", help=f"solo questo momento: {MOMENTS_HINT}"),
    dry_run: bool = typer.Option(False, "--dry-run", help="mostra cosa invierebbe, senza inviare né registrare nulla"),
) -> None:
    """Invia adesso i promemoria dovuti (lo usano le attività pianificate)."""
    try:
        key = parse_moment(moment) if moment else None
    except ValueError as error:
        fail(str(error))
    ensure_consent_without_prompt()
    with open_store(require_account=False) as store:  # a scheduled task has nobody to sign in
        notifier = None if dry_run else get_notifier()
        result = fire_due_reminders(store, data_dir(), current_time(), notifier, key, dry_run)
    if not result.due:
        typer.echo("Nessun promemoria da inviare adesso.")
        for check in result.overview.checks:
            if key is None or check.moment == key:
                typer.echo(f"  {MOMENT_LABELS[check.moment]}: {check.reason}")
        return
    if dry_run:
        for reminder in result.due:
            typer.echo(f"Prova, non invio nulla: «{reminder.title} — {reminder.body}»")
        return
    for reminder in result.sent:
        typer.echo(f"Promemoria inviato ({result.via}): {MOMENT_LABELS[reminder.moment]}")
    if result.failed:
        names = ", ".join(MOMENT_LABELS[reminder.moment] for reminder in result.failed)
        fail(f"non sono riuscito a mostrare il promemoria ({names}): riproverò al prossimo controllo. Prova `zbone remind test`")


def print_plan(plan: InstallPlan) -> None:
    for task in plan.create:
        typer.echo(f"  {task.name}  {task.describe()}")
        typer.echo(f"    esegue: {' '.join(task.command)}")
    for name in plan.remove:
        typer.echo(f"  {name}  da togliere: momento spento")


def print_results(results: list[TaskResult]) -> bool:
    ok = True
    for result in results:
        if result.ok and result.action != "assente":
            typer.echo(f"  {result.name}: {result.action}")
        elif not result.ok:
            ok = False
            typer.secho(f"  {result.name}: non riuscito — {result.detail}", fg=typer.colors.RED, err=True)
    return ok


@remind_app.command("install")
def install() -> None:
    """Crea le attività pianificate di Windows: i promemoria arrivano anche ad app chiusa."""
    ensure_consent()
    folder = data_dir()
    try:
        plan = plan_install(load_reminder_config(folder), launcher_command(), current_time().date())
    except (TaskSchedulerError, ValueError) as error:
        fail(str(error))
    if not on_windows():
        typer.echo("Su Windows `zbone remind install` creerebbe queste attività pianificate:")
        print_plan(plan)
        typer.echo(
            f"\nSu questo sistema ({sys.platform}) non creo nulla. Puoi pianificare da te `zbone remind fire` "
            "ogni 30 minuti, per esempio con cron: */30 * * * * zbone remind fire"
        )
        return
    if os.environ.get(ENV_DATA_DIR):
        typer.echo(f"Attenzione: {ENV_DATA_DIR} vale solo se è impostata anche per il tuo utente di Windows, non solo in questo terminale.")
    try:
        results = install_tasks(plan)
    except (TaskSchedulerError, OSError) as error:
        fail(str(error))
    typer.echo("Attività pianificate:")
    if not print_results(results):
        fail("alcune attività non sono state create o tolte (vedi sopra)")
    typer.echo("Fatto: i promemoria arriveranno anche ad app chiusa. Per toglierli: zbone remind uninstall")


@remind_app.command("uninstall")
def uninstall() -> None:
    """Toglie le attività pianificate di Windows dei promemoria."""
    ensure_consent()
    if not on_windows():
        typer.echo(f"Su questo sistema ({sys.platform}) ZibaldOne non crea attività pianificate: non c'è niente da togliere.")
        typer.echo("Su Windows toglierei: " + ", ".join(all_task_names()))
        return
    try:
        results = uninstall_tasks()
    except (TaskSchedulerError, OSError) as error:
        fail(str(error))
    if not print_results(results):
        fail("alcune attività non sono state tolte (vedi sopra)")
    removed = [result for result in results if result.action == "tolta"]
    typer.echo("Attività tolte." if removed else "Non c'erano attività dei promemoria da togliere.")


@remind_app.command("test")
def send_test() -> None:
    """Invia una notifica di prova."""
    ensure_consent()
    notifier = get_notifier()
    if not notifier.send(TEST_TITLE, TEST_BODY):
        fail("non sono riuscito a mostrare la notifica di prova: controlla che le notifiche di sistema siano permesse")
    typer.echo(f"Notifica di prova inviata ({notifier.name}).")
    if isinstance(notifier, TerminalNotifier):
        typer.echo("Per le notifiche di sistema su Windows, macOS o Linux installa il pacchetto desktop-notifier.")
    elif notifier.name == TerminalNotifier.name:
        typer.echo("Le notifiche di sistema non hanno risposto: l'ho mostrata qui nel terminale.")


__all__ = ["remind_app"]
