"""`zbone persona …`: Agorà, the people of one's life (0.2.1)."""

from datetime import date
from typing import List, Optional

import typer

from zibaldone.cli.common import fail, open_store
from zibaldone.core.areas import area_info, area_label
from zibaldone.core.blocks import parse_day
from zibaldone.core.people import CONTACT_KINDS, Person, due_people, find_person, load_people, log_contact, person_page, people_in_area

person_app = typer.Typer(help="Agorà: le persone della tua vita, i contatti e tutto quello che le riguarda.", no_args_is_help=False)

KINDS_HELP = ", ".join(kind.lower() for kind in CONTACT_KINDS)


def pick(people: List[Person], text: str) -> Person:
    person = find_person(people, text)
    if person is None:
        fail(f"nessuna persona '{text}': scrivi il nome, un soprannome o l'id (zbone persona list)")
    return person


def person_line(person: Person, today: date) -> str:
    due = "  · da sentire" if person.is_due(today) else ""
    roles = f" ({person.role_line})" if person.role_line else ""
    return f"  {person.short_id}  {person.name}{roles} · {person.contact_line(today)}{due}"


@person_app.callback(invoke_without_command=True)
def people_overview(ctx: typer.Context) -> None:
    """Le persone, chi è da sentire per prima."""
    if ctx.invoked_subcommand is None:
        list_people(area=None, due=False)


@person_app.command("list")
def list_people(
    area: Optional[str] = typer.Option(None, "--area", "-a", help="solo le persone di un'area"),
    due: bool = typer.Option(False, "--da-sentire", help="solo chi vorresti sentire e non senti da un po'"),
) -> None:
    """Elenca le persone con l'ultimo contatto."""
    today = date.today()
    with open_store() as store:
        people = load_people(store)
    if area:
        try:
            people = people_in_area(people, area_info(area).key)
        except ValueError as error:
            fail(str(error))
    if due:
        people = due_people(people, today)
    if not people:
        typer.echo("Nessuna persona." if not due else "Nessuno da sentire: il ritmo che hai scelto è rispettato.")
        return
    waiting = due_people(people, today)
    if waiting and not due:
        typer.echo("Da sentire")
        for person in waiting:
            typer.echo(person_line(person, today))
        typer.echo("")
    waiting_ids = {person.id for person in waiting}
    for person in people if due else [person for person in people if person.id not in waiting_ids]:
        typer.echo(person_line(person, today))


@person_app.command("show")
def show_person(name: str = typer.Argument(..., metavar="NOME", help="nome, soprannome o id")) -> None:
    """Tutto di una persona, area per area."""
    today = date.today()
    with open_store() as store:
        person = pick(load_people(store), name)
        page = person_page(store, person)
    typer.echo(person.name + (f" ({', '.join(person.nicknames)})" if person.nicknames else ""))
    if person.role_line:
        typer.echo(f"  {person.role_line}")
    if person.areas:
        typer.echo(f"  Aree: {', '.join(area_label(area) for area in person.areas)}")
    for label, value in (("Telefono", person.phone), ("Email", person.email), ("Social", ", ".join(person.social))):
        if value:
            typer.echo(f"  {label}: {value}")
    typer.echo(f"\nContatti: {person.contact_line(today)}")
    if person.rhythm_line(today):
        typer.echo(f"  {person.rhythm_line(today)}")
    for contact in person.contacts[:3]:
        typer.echo(f"  {contact.day}  {contact.label:<14} {contact.title}")
    for group in page.groups:
        typer.echo(f"\n{group.label}")
        for item in group.items:
            typer.echo(f"  {item.entry.short_id}  {item.entry.day}  {item.template_name:<18} {item.title}")
    if page.mentions:
        typer.echo("\nLa nominano senza collegamento")
        for hit in page.mentions:
            typer.echo(f"  {hit.entry.short_id}  {hit.entry.day}  {hit.title}")
    if not page.total:
        typer.echo(f"\nAncora nessuna voce la collega. Scrivi [[{person.name}]] in un testo, oppure: zbone persona sentito \"{person.name}\"")


@person_app.command("sentito")
def heard(
    name: str = typer.Argument(..., metavar="NOME", help="nome, soprannome o id"),
    kind: str = typer.Option("", "--tipo", "-t", help=KINDS_HELP),
    note: str = typer.Option("", "--nota", "-n", help="com'è andata"),
    day: Optional[str] = typer.Option(None, "--day", "-d", help="il giorno (di base oggi)"),
) -> None:
    """Segna che hai sentito o visto qualcuno (un Simposio con la persona)."""
    with open_store() as store:
        person = pick(load_people(store), name)
        entry = log_contact(store, person, kind, note, day=parse_day(day) if day else None)
    typer.echo(f"Segnato: {entry.values.get('titolo')} (id {entry.short_id}).")
