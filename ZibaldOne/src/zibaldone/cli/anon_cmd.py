"""`zbone anon …`: see what the anonymizer would replace, and how well it works (ADR-0009)."""

from typing import Dict, List, Optional, Tuple

import typer

from zibaldone.cli.common import fail, open_store
from zibaldone.core.anon_eval import EvalReport, Score, evaluate
from zibaldone.core.anonymizer import KIND_DESCRIPTIONS, MODES, PERSON_CATEGORY, AnonymizedText, Anonymizer, people_from_entries
from zibaldone.storage.database import Store

anon_app = typer.Typer(
    help="Anonimizzatore: toglie i dati personali prima che un testo arrivi a un modello di IA.",
    no_args_is_help=True,
)

MODE_NOTES = {
    "pseudo": "La tabella dei segnaposto è rimasta in memoria per questa anteprima: non è stata salvata da nessuna parte.",
    "anon": "Modalità anonimato: la tabella non viene conservata, il testo non è più riconducibile ai valori originali.",
}
RULES_WARNING = "Le regole possono sbagliare: rileggi il testo prima di usarlo."


def people_in_store(store: Store) -> List[List[str]]:
    """Alias groups from the person entries (templates of category 'persone')."""
    pairs = [
        (entry, template)
        for template in store.list_templates(category=PERSON_CATEGORY)
        for entry in store.list_entries(template=template.slug, newest_first=False)
    ]
    return people_from_entries(pairs)


def parse_names(raw: str) -> List[str]:
    return [name.strip() for name in raw.split(",") if name.strip()]


def replacement_rows(result: AnonymizedText) -> List[Tuple[str, str, str, int]]:
    """(kind description, original, placeholder, times), in order of first appearance."""
    counts: Dict[Tuple[str, str, str], int] = {}
    for replacement in result.replacements:
        finding = replacement.finding
        key = (KIND_DESCRIPTIONS.get(finding.kind, finding.kind.lower()), finding.text, replacement.placeholder)
        counts[key] = counts.get(key, 0) + 1
    return [(kind, original, placeholder, times) for (kind, original, placeholder), times in counts.items()]


def print_preview(result: AnonymizedText) -> None:
    typer.echo(f"Modalità: {MODES[result.mode]}\n")
    typer.echo("Testo da inviare:")
    for line in result.text.splitlines() or [""]:
        typer.echo(f"  {line}")
    rows = replacement_rows(result)
    if not rows:
        typer.echo(f"\nNessun dato personale riconosciuto. {RULES_WARNING}")
        return
    typer.echo(f"\nSostituzioni ({len(result.replacements)}):")
    kind_width = max(len("Tipo"), *(len(row[0]) for row in rows))
    original_width = min(40, max(len("Originale"), *(len(row[1]) for row in rows)))
    typer.echo(f"  {'Tipo'.ljust(kind_width)}  {'Originale'.ljust(original_width)}  Segnaposto")
    for kind, original, placeholder, times in rows:
        shown = original if len(original) <= original_width else original[: original_width - 1] + "…"
        repeated = f"  (×{times})" if times > 1 else ""
        typer.echo(f"  {kind.ljust(kind_width)}  {shown.ljust(original_width)}  {placeholder}{repeated}")
    typer.echo(f"\n{MODE_NOTES[result.mode]}")
    typer.echo(RULES_WARNING)


@anon_app.command("preview")
def preview(
    text: str = typer.Argument(..., metavar="TESTO", help="il testo da controllare, tra virgolette"),
    mode: str = typer.Option("pseudo", "--mode", "-m", help="pseudo (pseudonimi reversibili) o anon (anonimato)"),
    names: Optional[str] = typer.Option(
        None, "--names", "-n", help="nomi separati da virgola, al posto di quelli delle tue voci Persona"
    ),
) -> None:
    """Mostra cosa verrebbe sostituito in un testo, senza salvare né inviare nulla."""
    if mode not in MODES:
        fail(f"modalità sconosciuta '{mode}': usa pseudo oppure anon")
    try:
        if names is not None:
            listed = parse_names(names)
            anonymizer = Anonymizer(names=listed)
            typer.echo(f"Dizionario dei nomi: {len(listed)} da --names.")
        else:
            with open_store() as store:
                people = people_in_store(store)
            anonymizer = Anonymizer(people=people)
            if people:
                forms = sum(len(group) for group in people)
                typer.echo(f"Dizionario dei nomi: {forms} forme (nomi, cognomi, soprannomi) dalle tue voci Persona.")
            else:
                typer.echo("Nessuna voce Persona: i nomi di persona non verranno riconosciuti.")
                typer.echo("Per aggiungerle: zbone pack install persone, poi zbone entry add persona")
        result = anonymizer.anonymize(text, mode)
    except ValueError as error:
        fail(str(error))
    print_preview(result)


def _percent(value: Optional[float]) -> str:
    return "—" if value is None else f"{value * 100:.1f}%".replace(".", ",")


def _score_line(label: str, score: Score, width: int) -> str:
    return (
        f"  {label.ljust(width)}  {_percent(score.precision):>10}  {_percent(score.recall):>9}  {_percent(score.f1):>7}"
        f"  {score.true_positives:>4} {score.false_positives:>4} {score.false_negatives:>4}"
    )


def print_report(report: EvalReport, show_errors: bool) -> None:
    labels = sum(len(case.expected) for case in report.cases)
    typer.echo(f"Frasi di prova: {len(report.cases)}, con {labels} dati personali da trovare.")
    typer.echo("Confronto esatto: stesso tipo e stessi caratteri.\n")
    order = [kind for kind in KIND_DESCRIPTIONS if kind in report.exact] + [kind for kind in report.kinds if kind not in KIND_DESCRIPTIONS]
    width = max(len("Totale"), *(len(kind) for kind in order)) if order else len("Totale")
    typer.echo(f"  {'Tipo'.ljust(width)}  {'Precisione':>10}  {'Richiamo':>9}  {'F1':>7}  {'VP':>4} {'FP':>4} {'FN':>4}")
    for kind in order:
        typer.echo(_score_line(kind, report.exact[kind], width))
    typer.echo(_score_line("Totale", report.overall, width))
    relaxed = report.overall_relaxed
    typer.echo(
        f"\nConfronto parziale (stesso tipo, testo sovrapposto): precisione {_percent(relaxed.precision)}, "
        f"richiamo {_percent(relaxed.recall)}, F1 {_percent(relaxed.f1)}"
    )
    typer.echo("VP = trovati giusti, FP = sostituiti per errore, FN = sfuggiti.")
    if not report.errors:
        return
    if not show_errors:
        typer.echo(f"\n{len(report.errors)} frasi con errori: aggiungi --errors per vederle.")
        return
    typer.echo(f"\nFrasi con errori ({len(report.errors)}):")
    for case in report.errors:
        typer.echo(f"  {case.text}")
        for finding in case.missed:
            typer.echo(f"    sfuggito   {finding.kind}: {finding.text}")
        for finding in case.spurious:
            typer.echo(f"    in più     {finding.kind}: {finding.text}")


@anon_app.command("eval")
def run_eval(
    show_errors: bool = typer.Option(False, "--errors", "-e", help="mostra le frasi in cui le regole sbagliano"),
) -> None:
    """Misura precisione e richiamo per tipo di dato sulle frasi di prova."""
    print_report(evaluate(), show_errors)
