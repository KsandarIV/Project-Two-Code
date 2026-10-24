"""`zbone area …`: Eudaimonia, the 8 life areas (0.2.0)."""

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import typer

from zibaldone.cli.common import fail, open_store
from zibaldone.core.areas import (
    AREA_LIST,
    TODO_TEMPLATE,
    Area,
    AreaDetail,
    AreaSummary,
    add_todo,
    area_detail,
    area_info,
    area_overview,
    goals_overview,
    check_in,
    score_text,
    set_todo,
    upcoming_for,
)
from zibaldone.core.blocks import parse_day
from zibaldone.core.stats import bar, long_date
from zibaldone.core.templates import Entry, Template

area_app = typer.Typer(help="Eudaimonia: le 8 aree della vita, con punteggio, cose da fare e obiettivi.", no_args_is_help=False)

TRENDS = {"su": "in salita", "giù": "in discesa", "stabile": "stabile"}
SPARK = "▁▂▃▄▅▆▇█"
AREA_HELP = "personale, salute, finanze, famiglia, sociale, lavoro, studio o svago"


def pick_area(text: str) -> Area:
    try:
        return area_info(text)
    except ValueError as error:
        fail(str(error))
        raise


def load(store: Any) -> Tuple[List[Entry], Dict[str, Template]]:
    templates = {template.slug: template for template in store.list_templates()}
    return store.list_entries(newest_first=False), templates


def sparkline(values: List[Optional[float]]) -> str:
    """One character per week: higher block = higher score, '·' = no score that week."""
    return "".join("·" if value is None else SPARK[min(len(SPARK) - 1, int(value / 10 * len(SPARK)))] for value in values)


def summary_line(summary: AreaSummary) -> str:
    trend = f", {TRENDS[summary.trend]}" if summary.trend else ""
    average = f"media 30 giorni {score_text(summary.average)}{trend}" if summary.average is not None else "nessun punteggio negli ultimi 30 giorni"
    return f"ultimo {score_text(summary.latest)} · {average}"


@area_app.callback(invoke_without_command=True)
def areas_overview(ctx: typer.Context) -> None:
    """Le 8 aree della vita a colpo d'occhio."""
    if ctx.invoked_subcommand is not None:
        return
    with open_store() as store:
        entries, templates = load(store)
        overview = area_overview(entries, templates, date.today())
    typer.echo("Eudaimonia · le 8 aree della vita\n")
    for summary in overview:
        mascot = summary.area.mascot
        typer.echo(f"  {summary.area.label:<10} {bar(summary.fraction)}  {score_text(summary.latest):>7}  {mascot.name if mascot else ''}")
        typer.echo(f"  {'':<10} {summary.counts_label}")
    coming = upcoming_for()
    if coming:
        typer.echo("\nIn arrivo")
        for item in coming:
            typer.echo(f"  {item.title} ({item.when}): {item.teaser}")
    typer.echo("\nI dettagli di un'area: zbone area show salute")


@area_app.command("obiettivi")
def goals(area: Optional[str] = typer.Argument(None, metavar="[AREA]", help=AREA_HELP)) -> None:
    """Gli obiettivi ancora aperti, per scadenza (di una sola area, se la scrivi)."""
    chosen = pick_area(area).key if area else ""
    today = date.today()
    with open_store() as store:
        lines = goals_overview(store, today, chosen)
    if not lines:
        typer.echo("Nessun obiettivo aperto." + ("" if chosen else " Aggiungine uno: zbone entry add obiettivo --area salute"))
        return
    for line in lines:
        goal = line.goal
        parts = [f"{goal.percent}%"] if goal.percent is not None else []
        if goal.steps_total:
            parts.append(f"{goal.steps_done}/{goal.steps_total} passi")
        if line.days_left is not None:
            parts.append(f"{line.days_left} giorni alla scadenza" if line.days_left >= 0 else f"scaduto da {-line.days_left} giorni")
        typer.echo(f"  {area_info(line.area).label if line.area else 'Senza area':<10} {goal.title}" + (f" · {' · '.join(parts)}" if parts else ""))


@area_app.command("list")
def list_areas() -> None:
    """Elenca le 8 aree, con la mascotte e cosa ci va dentro."""
    for area in AREA_LIST:
        mascot = area.mascot
        who = f"{mascot.name}, {mascot.animal} ({mascot.philosopher})" if mascot else ""
        typer.echo(f"  {area.key:<10} {who:<40} {area.covers}")


def print_detail(detail: AreaDetail, templates: Dict[str, Template], today: date) -> None:
    area, summary = detail.area, detail.summary
    mascot = area.mascot
    typer.echo(f"{area.label} · {mascot.name}, {mascot.animal} ({mascot.philosopher})" if mascot else area.label)
    typer.echo(f"  {area.covers}\n")
    typer.echo("Punteggio")
    typer.echo(f"  {summary_line(summary)}")
    if summary.latest_day is not None:
        typer.echo(f"  l'ultimo è del {long_date(summary.latest_day)}")
    weeks = len(detail.series)
    typer.echo(f"  ultime {weeks} settimane: {sparkline([point.average for point in detail.series])}")
    typer.echo("\nDa fare")
    if detail.todos:
        for number_, todo in enumerate(detail.todos, 1):
            where = f"{todo.source}, " if todo.template != TODO_TEMPLATE else ""
            typer.echo(f"  {number_}. {todo.text}  ({where}{todo.day.day}/{todo.day.month})")
    else:
        typer.echo(f"  Niente da fare. Aggiungi: zbone area todo {area.key} \"...\"")
    typer.echo("\nObiettivi")
    if detail.goals:
        for goal in detail.goals:
            parts = [goal.status_label]
            if goal.percent is not None:
                parts.append(f"{goal.percent}%")
            if goal.deadline:
                late = " (scaduto)" if goal.active and goal.deadline < today else ""
                parts.append(f"entro il {long_date(goal.deadline)}{late}")
            if goal.steps_total:
                parts.append(f"{goal.steps_done}/{goal.steps_total} passi")
            typer.echo(f"  - {goal.title} · {' · '.join(parts)}")
    else:
        typer.echo(f"  Nessun obiettivo. Aggiungine uno: zbone entry add obiettivo --area {area.key}")
    typer.echo(f"\nVoci dell'area ({summary.total})")
    if detail.recent:
        for entry in detail.recent:
            template = templates.get(entry.template)
            name = template.name if template else entry.template
            title = entry.title(template) if template else entry.short_id
            typer.echo(f"  {entry.short_id}  {entry.day}  {name:<18} {title}")
    else:
        typer.echo("  Ancora nessuna. Le voci dei modelli di quest'area entrano da sole; le altre con --area.")
    coming = upcoming_for(area.key)
    if coming:
        typer.echo("\nIn arrivo")
        for item in coming:
            typer.echo(f"  {item.title} ({item.when}): {item.teaser}")


@area_app.command("show")
def show_area(
    area: str = typer.Argument(..., metavar="AREA", help=AREA_HELP),
    weeks: int = typer.Option(12, min=2, max=104, help="quante settimane di andamento"),
) -> None:
    """Mostra un'area: punteggio nel tempo, cose da fare, obiettivi e voci."""
    key = pick_area(area).key
    with open_store() as store:
        entries, templates = load(store)
        today = date.today()
        detail = area_detail(entries, templates, key, today, weeks=weeks)
    print_detail(detail, templates, today)


@area_app.command("checkin")
def area_checkin(
    area: str = typer.Argument(..., metavar="AREA", help=AREA_HELP),
    score: Optional[int] = typer.Option(None, "--punteggio", "-p", min=0, max=10, help="come va quest'area, da 0 a 10"),
    good: str = typer.Option("", "--bene", help="cosa va bene"),
    better: str = typer.Option("", "--meglio", help="cosa può andare meglio"),
    note: str = typer.Option("", "--nota", help="una nota"),
    day: Optional[str] = typer.Option(None, "--day", "-d", help="il giorno (di base oggi)"),
) -> None:
    """Il check-in di una sola area (Prosoché)."""
    key = pick_area(area).key
    if score is None and not (good or better or note):
        score = typer.prompt(f"Come va l'area {area_info(key).label}, da 0 a 10", type=int)
    with open_store() as store:
        entry = check_in(store, key, score, good, better, note, day=parse_day(day) if day else None)
    text = f" con {score}/10" if score is not None else ""
    typer.echo(f"Check-in di {area_info(key).label} salvato{text} (id {entry.short_id}).")


@area_app.command("todo")
def area_todo(
    area: str = typer.Argument(..., metavar="AREA", help=AREA_HELP),
    text: List[str] = typer.Argument(..., metavar="TESTO", help="cosa c'è da fare"),
) -> None:
    """Aggiunge una cosa da fare alla lista di un'area."""
    key = pick_area(area).key
    with open_store() as store:
        add_todo(store, key, " ".join(text))
        entries, templates = load(store)
        open_count = len(area_detail(entries, templates, key, date.today()).todos)
    typer.echo(f"Aggiunto a {area_info(key).label}: ora hai {open_count} cos{'a' if open_count == 1 else 'e'} da fare.")


@area_app.command("fatto")
def area_done(
    area: str = typer.Argument(..., metavar="AREA", help=AREA_HELP),
    position: int = typer.Argument(..., metavar="NUMERO", min=1, help="il numero in `zbone area show`"),
) -> None:
    """Spunta una cosa da fare (il numero è quello di `zbone area show`)."""
    key = pick_area(area).key
    with open_store() as store:
        entries, templates = load(store)
        todos = area_detail(entries, templates, key, date.today()).todos
        if position > len(todos):
            raise ValueError(f"in {area_info(key).label} ci sono {len(todos)} cose da fare: scegli un numero da 1 a {len(todos)}" if todos else f"in {area_info(key).label} non c'è niente da fare")
        todo = todos[position - 1]
        set_todo(store, todo, True)
    left = len(todos) - 1
    typer.echo(f"Fatto: {todo.text}. " + (f"Ne restano {left}." if left else "Non resta altro da fare."))

