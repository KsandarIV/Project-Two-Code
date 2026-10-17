"""Brand identity: names, mascots and quotes taken from philosophy.

ZibaldOne is named after Giacomo Leopardi's "Zibaldone di pensieri" (1817–1832),
a notebook of thousands of pages where everything found a place. "One" stands
for all-in-one. Every name here comes with its source so it can be checked.
"""

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional

APP_NAME = "ZibaldOne"
APP_TAGLINE = "il tuo zibaldone di pensieri, fatto a blocchi"
APP_MOTTO = "Tutto in uno, un pensiero alla volta."


@dataclass(frozen=True)
class Name:
    """A philosophical name for a part of the app, with its plain meaning and source."""

    name: str
    meaning: str
    source: str


# * — the parts of the app —
NOMENCLATURE: Dict[str, Name] = {
    "block": Name("Atomi", "i blocchi", "Democrito: tutto è fatto di atomi che si combinano"),
    "template": Name("Forme", "i modelli", "Platone e Aristotele: la forma che dà struttura alla materia"),
    "entry": Name("Pensieri", "le voci", "Leopardi, Zibaldone di pensieri; Pascal, Pensieri"),
    "pack": Name("Scuole", "i pacchetti di modelli", "le scuole filosofiche antiche: Stoa, Accademia, Liceo, Giardino"),
    "today": Name("Hic et nunc", "la pagina di oggi", "locuzione latina: qui e ora"),
    "search": Name("Zetesis", "la ricerca", "Sesto Empirico: lo scettico è zetetico, cioè colui che cerca"),
    "graph": Name("Rizoma", "il grafo dei collegamenti", "Deleuze e Guattari, Mille piani (1980)"),
    "stats": Name("Theoria", "le statistiche", "greco theorein: guardare, contemplare"),
    "history": Name("Mnemosyne", "storia e backup", "la dea greca della memoria; Aby Warburg, Atlante Mnemosyne"),
    "encryption": Name("Anello di Gige", "la cifratura", "Platone, Repubblica II: l'anello che rende invisibili"),
    "anonymizer": Name("Velo d'ignoranza", "l'anonimizzatore", "John Rawls, Una teoria della giustizia (1971)"),
    "reminders": Name("Daimon", "le notifiche", "Platone, Apologia di Socrate: la voce interiore che avverte"),
    "privacy": Name("Parresia", "la trasparenza sui dati", "Michel Foucault: il coraggio di dire il vero"),
    "cloud": Name("Le Nuvole", "account e cloud", "Aristofane, Le Nuvole (423 a.C.), con Socrate sospeso tra le nuvole"),
    "settings": Name("Organon", "le impostazioni", "Aristotele, Organon: gli strumenti del pensiero"),
    "ai": Name("Maieutica", "le future funzioni di IA", "Platone, Teeteto: l'arte di far nascere le idee"),
}


@dataclass(frozen=True)
class Mascot:
    name: str
    animal: str
    sphere: str
    philosopher: str
    story: str
    color: str


# * — one mascot per life area, plus the app's own (proposal) —
MASCOTS: List[Mascot] = [
    Mascot("Leopy", "passero", "personale", "Giacomo Leopardi",
           "Il passero solitario dei Canti: ama stare con sé stesso e scrivere quello che pensa.", "#B3F3F6"),
    Mascot("Hegy", "nottola", "studio", "G. W. F. Hegel",
           "La nottola di Minerva, che inizia il suo volo sul far del crepuscolo: capisce le cose ripensandoci la sera.", "#8A2BE2"),
    Mascot("Archy", "riccio", "lavoro", "Archiloco",
           "\"La volpe sa molte cose, il riccio una sola ma grande\": si concentra su ciò che conta.", "#FF5500"),
    Mascot("Monty", "gatta", "svago", "Michel de Montaigne",
           "\"Quando gioco con la mia gatta, chissà se non è lei a passare il tempo con me\" (Saggi II, 12).", "#FFFF00"),
    Mascot("Diogy", "cane", "salute", "Diogene di Sinope",
           "Il cane dei cinici: vita semplice, sole, movimento e poche cose.", "#74EE15"),
    Mascot("Mandy", "ape", "finanze", "Bernard de Mandeville",
           "L'ape della Favola delle api (1714): conta, risparmia e sa dove va il miele.", "#FF0000"),
    Mascot("Aristy", "cicogna", "famiglia", "Aristotele",
           "La cicogna che, scrive Aristotele, accudisce i genitori quando invecchiano.", "#FF007F"),
    Mascot("Hobby", "lupo", "sociale", "Thomas Hobbes",
           "\"Homo homini lupus\": un lupo burbero che sta imparando a stare in compagnia.", "#00E5FF"),
    Mascot("Zibby", "chimera", "app", "Platone",
           "Proposta: una piccola chimera fatta di pezzi delle altre otto, come i blocchi dell'app e l'anima-chimera della Repubblica (IX, 588c).", "#00E5FF"),
]

AREAS: List[str] = ["personale", "salute", "finanze", "famiglia", "sociale", "lavoro", "studio", "svago"]


def mascot_for(sphere: str) -> Optional[Mascot]:
    for mascot in MASCOTS:
        if mascot.sphere == sphere.lower():
            return mascot
    return None


@dataclass(frozen=True)
class Quote:
    text: str
    author: str
    source: str


# * — short, well-known quotes for the "pensiero del giorno" —
QUOTES: List[Quote] = [
    Quote("Conosci te stesso.", "Iscrizione del tempio di Apollo", "Delfi"),
    Quote("Una vita senza ricerca non è degna di essere vissuta.", "Socrate", "Platone, Apologia di Socrate, 38a"),
    Quote("Tutto scorre.", "Eraclito", "frammento attribuito"),
    Quote("L'uomo è misura di tutte le cose.", "Protagora", "citato da Platone, Teeteto"),
    Quote("Vivi nascosto.", "Epicuro", "massima attribuita (lathe biosas)"),
    Quote("Non abbiamo poco tempo, ma ne perdiamo molto.", "Seneca", "De brevitate vitae, I"),
    Quote("Nessun vento è favorevole per chi non sa dove andare.", "Seneca", "Lettere a Lucilio, 71"),
    Quote("Cogli l'attimo.", "Orazio", "Odi, I, 11"),
    Quote("Abbi il coraggio di servirti della tua intelligenza.", "Immanuel Kant", "Risposta alla domanda: che cos'è l'Illuminismo? (1784)"),
    Quote("Penso, dunque sono.", "René Descartes", "Discorso sul metodo (1637)"),
    Quote("Il cuore ha le sue ragioni, che la ragione non conosce.", "Blaise Pascal", "Pensieri"),
    Quote("Che cosa so?", "Michel de Montaigne", "Saggi"),
    Quote("La nottola di Minerva inizia il suo volo sul far del crepuscolo.", "G. W. F. Hegel", "Lineamenti di filosofia del diritto, prefazione (1820)"),
    Quote("Diventa ciò che sei.", "Friedrich Nietzsche", "da Pindaro; Ecce homo (1888)"),
    Quote("Su ciò di cui non si può parlare si deve tacere.", "Ludwig Wittgenstein", "Tractatus logico-philosophicus, 7"),
    Quote("Bisogna immaginare Sisifo felice.", "Albert Camus", "Il mito di Sisifo (1942)"),
    Quote("La noia è in qualche modo il più sublime dei sentimenti umani.", "Giacomo Leopardi", "Pensieri, LXVIII"),
]


def quote_of_the_day(day: Optional[date] = None) -> Quote:
    """Same quote all day, a different one tomorrow."""
    day = day or date.today()
    return QUOTES[day.toordinal() % len(QUOTES)]
