"""Brand identity: names, mascots and quotes taken from philosophy.

ZibaldOne is named after Giacomo Leopardi's "Zibaldone di pensieri" (1817–1832),
a notebook of thousands of pages where everything found a place. "One" stands
for all-in-one. Every name here comes with its source so it can be checked.
"""

import os
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Mapping, Optional, Tuple

DEFAULT_THEME_ID = "filosofia"
THEME_ENV_VAR = "ZIBALDONE_THEME"
THEME_SETTING_KEY = "theme"
MIN_QUOTES = 7
_THEME_ID_RE = re.compile(r"^[a-z0-9_-]+$")


@dataclass(frozen=True)
class Name:
    """A philosophical name for a part of the app, with its plain meaning and source."""

    name: str
    meaning: str
    source: str


# * — the parts of the app —
_FILOSOFIA_NOMENCLATURE: Dict[str, Name] = {
    "block": Name("Atomi", "i blocchi", "Democrito: tutto è fatto di atomi che si combinano"),
    "template": Name("Forme", "i modelli", "Platone e Aristotele: la forma che dà struttura alla materia"),
    "entry": Name("Pensieri", "le voci", "Leopardi, Zibaldone di pensieri; Pascal, Pensieri"),
    "pack": Name("Scuole", "i pacchetti di modelli", "le scuole filosofiche antiche: Stoa, Accademia, Liceo, Giardino"),
    "today": Name("Hic et nunc", "la pagina di oggi", "locuzione latina: qui e ora"),
    "areas": Name("Eudaimonia", "le 8 aree della vita", "Aristotele, Etica Nicomachea: la felicità come vita che fiorisce in tutte le sue parti"),
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


@dataclass(frozen=True)
class Quote:
    text: str
    author: str
    source: str


AREAS: List[str] = ["personale", "salute", "finanze", "famiglia", "sociale", "lavoro", "studio", "svago"]


# * — one mascot per life area, plus the app's own (proposal) —
_FILOSOFIA_MASCOTS: List[Mascot] = [
    Mascot("Leopy", "passero", "personale", "Giacomo Leopardi",
           "Il passero solitario dei Canti: ama stare con sé stesso e scrivere quello che pensa.", "#B3F3F6"),
    Mascot("Hegy", "nottola", "studio", "G. W. F. Hegel",
           "La nottola di Minerva, che inizia il suo volo sul far del crepuscolo: capisce le cose ripensandoci la sera.", "#8A2BE2"),
    Mascot("Archy", "riccio", "lavoro", "Archiloco",
           "\"La volpe sa molte cose, il riccio una sola ma grande\": si concentra su ciò che conta.", "#FF5500"),
    Mascot("Monty", "gatta", "svago", "Michel de Montaigne",
           "\"Quando gioco con la mia gatta, chissà se non è lei a passare il tempo con me\" (Saggi II, 12).", "#FFFF00"),
    Mascot("Diggy", "cane", "salute", "Diogene di Sinope",
           "Il cane dei cinici: vita semplice, sole, movimento e poche cose.", "#74EE15"),
    Mascot("Mandy", "ape", "finanze", "Bernard de Mandeville",
           "L'ape della Favola delle api (1714): conta, risparmia e sa dove va il miele.", "#FF0000"),
    Mascot("Ary", "cicogna", "famiglia", "Aristotele",
           "La cicogna che, scrive Aristotele, accudisce i genitori quando invecchiano.", "#FF007F"),
    Mascot("Hobbsy", "lupo", "sociale", "Thomas Hobbes",
           "\"Homo homini lupus\": un lupo burbero che sta imparando a stare in compagnia.", "#00E5FF"),
    Mascot("Zibby", "chimera", "app", "Platone",
           "Proposta: una piccola chimera fatta di pezzi delle altre otto, come i blocchi dell'app e l'anima-chimera della Repubblica (IX, 588c).", "#00E5FF"),
]

# * — short, well-known quotes for the "pensiero del giorno" —
_FILOSOFIA_QUOTES: List[Quote] = [
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


# * — themes: one registry entry per brand identity —
@dataclass(frozen=True)
class Theme:
    """A complete brand identity: app texts, nomenclature, mascots and quotes."""

    id: str
    label: str
    app_name: str
    app_tagline: str
    app_motto: str
    nomenclature: Mapping[str, Name]
    mascots: Tuple[Mascot, ...]
    quotes: Tuple[Quote, ...]

    def mascot_for(self, sphere: str) -> Optional[Mascot]:
        for mascot in self.mascots:
            if mascot.sphere == sphere.lower():
                return mascot
        return None

    def quote_of_the_day(self, day: Optional[date] = None) -> Quote:
        """Same quote all day, a different one tomorrow."""
        day = day or date.today()
        return self.quotes[day.toordinal() % len(self.quotes)]


_THEMES: Dict[str, Theme] = {}


def validate_theme(theme: Theme) -> None:
    """Raise ValueError (naming theme and problem) if the theme is incomplete."""

    def fail(problem: str) -> None:
        raise ValueError(f"theme {theme.id!r}: {problem}")

    if not theme.id or not _THEME_ID_RE.match(theme.id):
        fail("id must be a non-empty slug [a-z0-9_-]+")
    for field in ("label", "app_name", "app_tagline", "app_motto"):
        if not getattr(theme, field).strip():
            fail(f"{field} is empty")
    default = _THEMES.get(DEFAULT_THEME_ID)
    if default is not None and set(theme.nomenclature) != set(default.nomenclature):
        missing = sorted(set(default.nomenclature) - set(theme.nomenclature))
        extra = sorted(set(theme.nomenclature) - set(default.nomenclature))
        fail(f"nomenclature keys differ (missing {missing}, extra {extra})")
    for key, name in theme.nomenclature.items():
        if not (name.name.strip() and name.meaning.strip() and name.source.strip()):
            fail(f"nomenclature {key!r} has an empty name, meaning or source")
    spheres = [mascot.sphere for mascot in theme.mascots]
    if len(set(spheres)) != len(spheres):
        fail("duplicate mascot spheres")
    if sorted(spheres) != sorted(AREAS + ["app"]):
        fail(f"mascots must cover exactly {AREAS + ['app']}, got {sorted(spheres)}")
    names = [mascot.name for mascot in theme.mascots]
    if not all(name.strip() for name in names) or len(set(names)) != len(names):
        fail("mascot names must be non-empty and unique")
    if len(theme.quotes) < MIN_QUOTES:
        fail(f"at least {MIN_QUOTES} quotes needed, got {len(theme.quotes)}")
    texts = [quote.text for quote in theme.quotes]
    if not all(text.strip() for text in texts) or len(set(texts)) != len(texts):
        fail("quote texts must be non-empty and unique")
    if not all(quote.author.strip() and quote.source.strip() for quote in theme.quotes):
        fail("every quote needs an author and a source")


def register_theme(theme: Theme) -> Theme:
    """Validate and add a theme to the registry; return it."""
    validate_theme(theme)
    if theme.id in _THEMES:
        raise ValueError(f"theme {theme.id!r}: already registered")
    _THEMES[theme.id] = theme
    return theme


def list_themes() -> List[Theme]:
    """All themes: the default first, then in registration order."""
    ordered = [theme for theme in _THEMES.values() if theme.id == DEFAULT_THEME_ID]
    return ordered + [theme for theme in _THEMES.values() if theme.id != DEFAULT_THEME_ID]


def get_theme(theme_id: Optional[str]) -> Theme:
    """Theme by id; unknown, empty or None falls back to the default."""
    key = (theme_id or "").strip().lower()
    return _THEMES.get(key) or _THEMES[DEFAULT_THEME_ID]


def active_theme(settings: Optional[Mapping[str, Any]] = None) -> Theme:
    """Theme chosen by env var, then by settings, then the default."""
    chosen = os.environ.get(THEME_ENV_VAR) or (settings or {}).get(THEME_SETTING_KEY)
    return get_theme(chosen if isinstance(chosen, str) else None)


# * — the default theme: philosophy —
FILOSOFIA = register_theme(Theme(
    id=DEFAULT_THEME_ID,
    label="Filosofia",
    app_name="ZibaldOne",
    app_tagline="il tuo zibaldone di pensieri, fatto a blocchi",
    app_motto="Tutto in uno, un pensiero alla volta.",
    nomenclature=_FILOSOFIA_NOMENCLATURE,
    mascots=tuple(_FILOSOFIA_MASCOTS),
    quotes=tuple(_FILOSOFIA_QUOTES),
))

# * — public aliases bound to the default theme (read at import by navigation.py) —
APP_NAME = FILOSOFIA.app_name
APP_TAGLINE = FILOSOFIA.app_tagline
APP_MOTTO = FILOSOFIA.app_motto
NOMENCLATURE: Dict[str, Name] = dict(FILOSOFIA.nomenclature)
MASCOTS: List[Mascot] = list(FILOSOFIA.mascots)
QUOTES: List[Quote] = list(FILOSOFIA.quotes)


def mascot_for(sphere: str) -> Optional[Mascot]:
    return FILOSOFIA.mascot_for(sphere)


def quote_of_the_day(day: Optional[date] = None) -> Quote:
    """Same quote all day, a different one tomorrow."""
    return FILOSOFIA.quote_of_the_day(day)
