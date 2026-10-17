"""`zbone persona …`: Agorà, the people of one's life (0.2.1), their ties and the family tree (0.2.2)."""

from datetime import date
from typing import List, Optional

import typer

from zibaldone.cli.common import fail, open_store
from zibaldone.core.areas import area_info, area_label
from zibaldone.core.blocks import parse_day
from zibaldone.core.people import CONTACT_KINDS, PeopleError, Person, due_people, find_person, load_people, log_contact, person_page, people_in_area
from zibaldone.core.relations import TIE_HOW, TIE_WORDS, Connection, add_tie, family_tree, network, parse_tie, strength_line, strongest

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
        people = load_people(store)
        person = pick(people, name)
        page = person_page(store, person)
    links = network(people).connections(person.id)
    typer.echo(person.name + (f" ({', '.join(person.nicknames)})" if person.nicknames else ""))
    if person.role_line:
        typer.echo(f"  {person.role_line}")
    if person.areas:
        typer.echo(f"  Aree: {', '.join(area_label(area) for area in person.areas)}")
    for label, value in (("Telefono", person.phone), ("Email", person.email), ("Social", ", ".join(person.social))):
        if value:
            typer.echo(f"  {label}: {value}")
    typer.echo(f"\nContatti: {person.contact_line(today)}")
    for line in (person.rhythm_line(today), strength_line(person, today)):
        if line:
            typer.echo(f"  {line}")
    for contact in person.contacts[:3]:
        typer.echo(f"  {contact.day}  {contact.label:<14} {contact.title}")
    if links:
        typer.echo("\nLegami")
        for link in links:
            typer.echo(connection_line(link))
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


def connection_line(link: Connection) -> str:
    common = f" · in comune: {', '.join(other.name for other in link.in_common)}" if link.in_common else ""
    return f"  {link.person.name} · {link.how}{common}"


@person_app.command("lega")
def tie(
    first: str = typer.Argument(..., metavar="NOME", help="chi"),
    word: str = typer.Argument(..., metavar="LEGAME", help=", ".join(TIE_WORDS)),
    second: str = typer.Argument(..., metavar="DI", help="di chi"),
) -> None:
    """Lega due persone: «zbone persona lega Anna genitore Luca» (Anna è genitore di Luca)."""
    with open_store() as store:
        people = load_people(store)
        a, b = pick(people, first), pick(people, second)
        try:
            kind = parse_tie(word)
            added = add_tie(store, a, kind, b)
        except PeopleError as error:
            fail(str(error))
    sentence = f"{a.name} è {TIE_HOW[kind]} di {b.name}" if kind != "conosce" else f"{a.name} conosce {b.name}"
    typer.echo(f"Legati: {sentence}." if added else f"Erano già legati: {sentence}.")


@person_app.command("albero")
def tree() -> None:
    """L'albero di famiglia, generazione per generazione."""
    with open_store() as store:
        rows = family_tree(load_people(store))
    if not rows:
        typer.echo("Ancora nessun familiare. Dai a una persona un ruolo (madre, nonno …) o i suoi Genitori.")
        return
    for number, row in enumerate(rows):
        typer.echo(("\n" if number else "") + row.label)
        for member in row.members:
            typer.echo(f"  {member.name}" + (f" · {member.caption}" if member.caption else ""))


@person_app.command("rete")
def people_network(
    name: Optional[str] = typer.Argument(None, metavar="NOME", help="chi conosce questa persona (di base: i legami più forti)"),
    area: Optional[str] = typer.Option(None, "--area", "-a", help="solo le persone di un'area"),
) -> None:
    """Chi conosce chi, i contatti in comune e la forza dei legami."""
    today = date.today()
    with open_store() as store:
        people = load_people(store)
    if area:
        try:
            people = people_in_area(people, area_info(area).key)
        except ValueError as error:
            fail(str(error))
    net = network(people)
    if name:
        person = pick(net.people, name)
        links = net.connections(person.id)
        typer.echo(f"{person.name}: " + (strength_line(person, today) or "ancora nessun contatto"))
        for link in links:
            typer.echo(connection_line(link))
        if not links:
            typer.echo(f"  Nessun legame. Collegala: zbone persona lega \"{person.name}\" conosce NOME")
        return
    ranked = strongest(net.people, today)
    if not ranked:
        typer.echo("Ancora nessun contatto: segna un incontro con zbone persona sentito NOME.")
        return
    typer.echo("Legami più forti")
    for person, score in ranked:
        known = len(net.neighbours(person.id))
        typer.echo(f"  {score:>2}/10  {person.name}" + (f" · conosce {known} delle tue persone" if known else ""))
