"""`zbone stats` and `zbone review`: Theoria, the statistics, and the reviews (0.1.4)."""

from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import typer

from zibaldone.cli.common import fail, open_store
from zibaldone.cli.graph_cmd import write_file
from zibaldone.core.blocks import parse_day
from zibaldone.core.stats import (
    Review,
    bar,
    in_period,
    number,
    propose_review_values,
    render_html,
    review,
    review_slugs,
    review_template,
    short_day,
    trend_words,
)
from zibaldone.core.templates import Template

PERIODS = {"week": "week", "settimana": "week", "w": "week", "month": "month", "mese": "month", "m": "month"}


def load(store: Any) -> Tuple[list, Dict[str, Template], list]:
    templates = {template.slug: template for template in store.list_templates()}
    return store.list_entries(newest_first=False), templates, store.all_links()


def pick_day(raw: Optional[str]) -> date:
    return date.fromisoformat(parse_day(raw)) if raw else date.today()


def point_name(point: Any) -> str:
    if point.start == point.end:
        return short_day(point.start)
    return f"sett. {point.start.isocalendar()[1]} ({point.start.day}/{point.start.month}–{point.end.day}/{point.end.month})"


def print_summary(result: Review, heading: str) -> None:
    period, activity, mood = result.period, result.activity, result.mood
    previous = f"la {period.noun} prima" if period.kind == "week" else f"il {period.noun} prima"
    typer.echo(f"{heading} · {period.label}\n")
    typer.echo("Scrittura")
    if result.entries:
        days = "1 giorno" if activity.active_days == 1 else f"{activity.active_days} giorni"
        typer.echo(f"  {result.entries} voc{'e' if result.entries == 1 else 'i'} in {days} su {activity.days} ({previous}: {result.previous_entries})")
        typer.echo("  " + " · ".join(f"{name} {count}" for _, name, count in activity.per_template[:6]))
    else:
        typer.echo("  Nessuna voce in questo periodo.")
    if activity.current_streak > 1:
        typer.echo(f"  Giorni di fila con almeno una voce: {activity.current_streak} (la serie più lunga: {activity.longest_streak})")
    elif activity.longest_streak > 1:
        typer.echo(f"  La serie più lunga di giorni con almeno una voce: {activity.longest_streak}")
    if mood.average is not None:
        typer.echo("\nUmore (da 1 a 5)")
        trend = trend_words(mood, period.noun)
        typer.echo(f"  Media {number(mood.average)}" + (f", {trend}" if trend else ""))
        for point in result.mood_points:
            fraction = None if point.average is None else (point.average - 1) / 4
            typer.echo(f"  {point_name(point):<24} {bar(fraction)} {number(point.average)}")
    areas = [stat for stat in result.scales if stat.area]
    if areas:
        typer.echo("\nAree della vita")
        width = max(len(stat.label) for stat in areas)
        for stat in areas:
            typer.echo(f"  {stat.label:<{width}}  {bar(stat.normalized)} {number(stat.average)}/{stat.high}")
        if result.best_area and result.worst_area:
            typer.echo(f"  Più in alto: {result.best_area.label} · quella che chiede più cura: {result.worst_area.label}")
    others = [stat for stat in result.scales if not stat.area]
    if others:
        typer.echo("\nAltri punteggi")
        for stat in others:
            typer.echo(f"  {stat.label} ({stat.template_name}): {number(stat.average)} su {stat.high}")
    if result.in_progress:
        typer.echo("\nIn corso")
        for item in result.in_progress[:8]:
            details = [item.template_name, item.status_label + (f" {item.percent}%" if item.percent is not None else "")]
            if item.bookmark:
                details.append(item.bookmark)
            typer.echo(f"  {item.title} · " + " · ".join(details))
    if result.completed:
        typer.echo("\nCompletati")
        for item in result.completed:
            typer.echo(f"  {item.title} · {item.template_name}")
    if result.people:
        typer.echo("\nPersone più presenti")
        typer.echo("  " + ", ".join(f"{person.title} ({person.count})" for person in result.people))
    if result.open_items:
        typer.echo(f"\nAncora aperti ({len(result.open_items)})")
        for item in result.open_items[:10]:
            typer.echo(f"  [ ] {item.text}  ({item.template_name}, {short_day(item.day)})")


def stats_command(
    week: bool = typer.Option(False, "--week", help="la settimana, da lunedì a domenica (la scelta di base)"),
    month: bool = typer.Option(False, "--month", help="il mese"),
    day: Optional[str] = typer.Option(None, "--date", "-d", help="un giorno del periodo (di base oggi)"),
    html_file: Optional[Path] = typer.Option(None, "--html", help="salva anche una pagina HTML con i grafici"),
) -> None:
    """Le statistiche (Theoria): umore, aree, scrittura e collezioni della settimana o del mese."""
    if week and month:
        fail("scegli --week oppure --month")
    kind = "month" if month else "week"
    with open_store() as store:
        entries, templates, links = load(store)
        result = review(entries, templates, links, kind, pick_day(day), date.today())
    print_summary(result, "Theoria")
    if html_file:
        typer.echo(f"\nPagina salvata: {write_file(html_file, render_html(result))}")


def proposal_lines(values: Dict[str, Any], template: Template) -> List[Tuple[str, str]]:
    lines = []
    for spec in template.blocks:
        if spec.key in values:
            lines.append((spec.label, spec.block_type.to_text(values[spec.key], spec.options)))
    return lines


def review_command(
    period: str = typer.Argument(..., metavar="week|month", help="week (settimana) oppure month (mese)"),
    day: Optional[str] = typer.Option(None, "--date", "-d", help="un giorno del periodo (di base oggi)"),
    template_slug: Optional[str] = typer.Option(None, "--template", "-t", help="il modello della revisione (di base settimana o mese)"),
    save: bool = typer.Option(False, "--save", help="salva la proposta come nuova voce, da rivedere con zbone entry edit"),
    html_file: Optional[Path] = typer.Option(None, "--html", help="salva anche una pagina HTML con i grafici"),
) -> None:
    """La revisione della settimana o del mese (Hypomnemata, Lettera a Lucilio), con una proposta già compilata."""
    kind = PERIODS.get(period.strip().lower())
    if kind is None:
        fail("scegli week (settimana) oppure month (mese)")
    today = date.today()
    with open_store() as store:
        entries, templates, links = load(store)
        target = store.get_template(template_slug) if template_slug else review_template(templates, kind)
        excluded = set(review_slugs(templates)) | ({target.slug} if target else set())
        result = review(entries, templates, links, kind, pick_day(day), today, exclude_templates=sorted(excluded))
        heading = "Hypomnemata" if kind == "week" else "Lettera a Lucilio"
        print_summary(result, f"{heading} · revisione {'della settimana' if kind == 'week' else 'del mese'}")
        lines: List[Tuple[str, str]] = []
        if target is None:
            typer.echo("\nPer avere una revisione già compilata installa il diario (zbone pack install diario) o indica un modello con --template.")
        else:
            values = propose_review_values(result, target)
            lines = proposal_lines(values, target)
            typer.echo(f"\nProposta per «{target.name}» (una bozza: cambiala come vuoi)")
            if not lines:
                typer.echo("  Ancora niente da proporre per questo periodo.")
            for label, text in lines:
                if "\n" in text:
                    typer.echo(f"  {label}:")
                    for line in text.splitlines():
                        typer.echo(f"    {line}")
                else:
                    typer.echo(f"  {label}: {text}")
            if save:
                existing = in_period(store.list_entries(template=target.slug), result.period)
                if existing:
                    typer.echo(f"\nC'è già una revisione per questo periodo (id {existing[0].short_id}): la puoi modificare con zbone entry edit {existing[0].short_id}")
                else:
                    when = min(result.period.end, today) if result.period.start <= today else result.period.end
                    entry = store.add_entry(target.slug, values, when.isoformat())
                    typer.echo(f"\nRevisione salvata (id {entry.short_id}). Per rileggerla e completarla: zbone entry edit {entry.short_id}")
    if html_file:
        typer.echo(f"\nPagina salvata: {write_file(html_file, render_html(result, heading, lines))}")


__all__ = ["review_command", "stats_command"]
