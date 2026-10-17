"""Local anonymizer: personal data becomes placeholders before any AI model (ADR-0009).

Rules only, standard library only, nothing leaves the device. Two modes:

- `pseudo`: reversible pseudonyms. The placeholder → original table stays in
  memory, so a model's answer can be brought back with `restore`;
- `anon`: the table is never kept and the text is no longer traceable.

Detectors favour recall: when in doubt they replace (ADR-0009). Person names come
from the user's dictionary (Persona entries and nicknames). A local NER model
(for example Italian spaCy) can be plugged in later as one more detector: any
callable `text -> Iterable[Finding]` passed in `Anonymizer(detectors=…)`.

Pseudonymised text is still personal data under the GDPR (recital 26): the
mapping must be protected like the rest of the user's data.
"""

import ipaddress
import re
import unicodedata
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Iterator, List, Mapping, Optional, Pattern, Sequence, Tuple

from zibaldone.core.templates import Entry, Template

# * — kinds and modes —

KIND_DESCRIPTIONS: Dict[str, str] = {
    "PERSONA": "nome di persona",
    "EMAIL": "indirizzo email",
    "TELEFONO": "numero di telefono",
    "CODICE_FISCALE": "codice fiscale",
    "PARTITA_IVA": "partita IVA",
    "IBAN": "IBAN",
    "CARTA": "carta di pagamento",
    "URL": "indirizzo web",
    "IP": "indirizzo IP",
    "INDIRIZZO": "indirizzo stradale",
    "DATA_NASCITA": "data di nascita",
    "LUOGO": "luogo del dizionario personale",
    "TERMINE": "termine del dizionario personale",
}
# Identical spans: checksum-validated kinds win, dictionary terms come last.
KIND_PRIORITY: Tuple[str, ...] = (
    "IBAN", "CODICE_FISCALE", "CARTA", "PARTITA_IVA", "EMAIL", "URL", "IP",
    "TELEFONO", "DATA_NASCITA", "INDIRIZZO", "PERSONA",
)
MODES: Dict[str, str] = {"pseudo": "pseudonimi reversibili", "anon": "anonimato irreversibile"}
CUSTOM_KIND = re.compile(r"^[A-Z][A-Z_]{0,28}[A-Z]$")
MIN_NAME_LENGTH = 2

PERSON_CATEGORY = "persone"
PERSON_NAME_KEYS = ("nome", "nome_completo", "name")
NICKNAMES_KEY = "soprannomi"
NAME_PARTICLES = frozenset({
    "d'", "da", "dal", "dalla", "de", "dei", "degli", "del", "della", "delle", "dello", "den", "der", "di",
    "du", "e", "la", "le", "lo", "mc", "van", "von", "y",
})
MIN_NAME_PART_LENGTH = 3

# Names that are also everyday Italian words: matched only when written with a capital.
COMMON_WORD_NAMES = frozenset({
    # first names and nicknames
    "alba", "allegra", "amato", "amata", "ambra", "angelo", "angela", "aria", "asia", "assunta", "augusto",
    "aurora", "beata", "benedetta", "benvenuto", "bianca", "bruna", "bruno", "celeste", "chiara", "chiaro",
    "clemente", "concetta", "costanza", "domenica", "fede", "fedele", "felice", "fiore", "fortuna",
    "fortunata", "fortunato", "fra", "franca", "franco", "gemma", "gentile", "giada", "giusto", "gioia",
    "grazia", "immacolata", "italia", "libero", "lino", "luce", "luna", "mari", "marina", "marino",
    "margherita", "massimo", "max", "mia", "mina", "modesto", "natale", "neve", "oliva", "pace", "pasqua",
    "pasquale", "perla", "pia", "pino", "primo", "remo", "romano", "romana", "rosa", "rosario", "santa",
    "santo", "sere", "serena", "sereno", "severo", "sole", "speranza", "stella", "vale", "vera", "vero",
    "viola", "vittoria",
    # surnames
    "allegri", "alto", "bassi", "basso", "belli", "bello", "bianchi", "bianco", "bosco", "bruni",
    "calabrese", "campo", "canale", "cavallo", "colombo", "conte", "conti", "costa", "fabbri", "fabbro",
    "felici", "ferri", "fiori", "fontana", "forte", "francese", "gallo", "gatti", "gatto", "genovese",
    "grandi", "grasso", "greco", "guerra", "inglese", "leone", "lombardo", "lupo", "marchi", "martelli",
    "mazza", "mele", "merlo", "milanese", "monaco", "monti", "mori", "moro", "neri", "nero", "orso",
    "piazza", "piccoli", "ponte", "porta", "pugliese", "rana", "ricci", "riva", "rocca", "rossi", "rosso",
    "russo", "sala", "santi", "sardo", "sereni", "serra", "siciliano", "silvestri", "spagnolo", "tedesco",
    "testa", "toscano", "vacca", "valle", "veneziano", "villa", "vitale",
})

Detector = Callable[[str], Iterable["Finding"]]


# * — results —

@dataclass(frozen=True)
class Finding:
    """A piece of personal data found in a text: `text == source[start:end]`."""

    kind: str
    start: int
    end: int
    text: str

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class Replacement:
    finding: Finding
    placeholder: str


@dataclass
class AnonymizedText:
    """The text to send, plus what was replaced.

    `replacements` (and `findings`) hold the originals: show them to the user,
    never send them. `mapping` is empty in `anon` mode.
    """

    text: str
    mode: str
    replacements: List[Replacement]
    mapping: Dict[str, str]

    @property
    def findings(self) -> List[Finding]:
        return [replacement.finding for replacement in self.replacements]

    def restore(self, answer: str) -> str:
        if self.mode != "pseudo":
            raise ValueError("in modalità anonimato la tabella dei segnaposto non esiste: non si può ripristinare")
        return restore(answer, self.mapping)


# * — checksums —

def luhn_ok(digits: str) -> bool:
    """Luhn check (payment cards; also the Italian partita IVA, which is Luhn on 11 digits)."""
    if not digits.isdigit() or len(digits) < 2:
        return False
    total = 0
    for position, char in enumerate(reversed(digits)):
        value = int(char)
        if position % 2 == 1:
            value = value * 2 - 9 if value > 4 else value * 2
        total += value
    return total % 10 == 0


def isbn13_ok(digits: str) -> bool:
    """Book codes (978/979…) can pass Luhn too: they are not cards."""
    if len(digits) != 13 or not digits.isdigit() or not digits.startswith(("978", "979")):
        return False
    return sum(int(char) * (3 if index % 2 else 1) for index, char in enumerate(digits)) % 10 == 0


def partita_iva_ok(value: str) -> bool:
    digits = value[2:] if value[:2].upper() == "IT" else value
    digits = digits.strip()
    return len(digits) == 11 and digits.isdigit() and digits != "0" * 11 and luhn_ok(digits)


CF_SHAPE = re.compile(r"[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]")
CF_ODD = dict(zip(
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    (1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 1, 0, 5, 7, 9, 13, 15, 17, 19, 21,
     2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23),
))
CF_EVEN = {char: (int(char) if char.isdigit() else ord(char) - ord("A")) for char in CF_ODD}


def codice_fiscale_check_char(first15: str) -> str:
    """The 16th character of a codice fiscale (official odd/even tables, mod 26)."""
    code = first15.upper()
    if len(code) != 15 or any(char not in CF_ODD for char in code):
        raise ValueError("servono i primi 15 caratteri del codice fiscale")
    total = sum(CF_ODD[char] if index % 2 == 0 else CF_EVEN[char] for index, char in enumerate(code))
    return chr(ord("A") + total % 26)


def codice_fiscale_ok(value: str) -> bool:
    """Shape (omocodia letters included) and check character, case-insensitive."""
    code = value.strip().upper()
    return bool(CF_SHAPE.fullmatch(code)) and codice_fiscale_check_char(code[:15]) == code[15]


IBAN_LENGTHS: Dict[str, int] = {
    "AD": 24, "AT": 20, "BE": 16, "BG": 22, "CH": 21, "CY": 28, "CZ": 24, "DE": 22, "DK": 18, "EE": 20,
    "ES": 24, "FI": 18, "FR": 27, "GB": 22, "GR": 27, "HR": 21, "HU": 28, "IE": 22, "IS": 26, "IT": 27,
    "LI": 21, "LT": 20, "LU": 20, "LV": 21, "MC": 27, "MT": 31, "NL": 18, "NO": 15, "PL": 28, "PT": 25,
    "RO": 24, "SE": 24, "SI": 19, "SK": 24, "SM": 27, "VA": 22,
}
IBAN_SHAPE = re.compile(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}")


def iban_ok(value: str) -> bool:
    """ISO 13616: known length for the country (when known) and mod 97 == 1."""
    code = re.sub(r"\s", "", value).upper()
    if not IBAN_SHAPE.fullmatch(code):
        return False
    expected = IBAN_LENGTHS.get(code[:2])
    if expected and len(code) != expected:
        return False
    rearranged = code[4:] + code[:4]
    return int("".join(str(int(char, 36)) for char in rearranged)) % 97 == 1


# * — rule detectors —

EMAIL = re.compile(r"(?<![\w.%+-])[\w.%+-]+@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,24}(?![\w-])")
URL_WITH_SCHEME = re.compile(r"(?<![\w@])(?:(?:https?|ftp)://|www\.)[^\s<>\"'«»]+", re.IGNORECASE)
URL_BARE_WITH_PATH = re.compile(r"(?<![\w@./-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}/[^\s<>\"'«»]*", re.IGNORECASE)
URL_TRAILING = ".,;:!?…'\"»"
CLOSING_BRACKETS = {")": "(", "]": "[", "}": "{"}
IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?!\w|\.\d)")
IPV6 = re.compile(r"(?<![\w:.])(?=[0-9A-Fa-f:]*[0-9A-Fa-f])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![\w:])")
CODICE_FISCALE = re.compile(
    r"(?<!\w)[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z](?!\w)", re.IGNORECASE
)
PARTITA_IVA = re.compile(r"(?<!\w)(?:IT ?)?\d{11}(?!\w)")
IBAN_START = re.compile(r"(?<!\w)[A-Za-z]{2}\d{2}(?= ?[A-Za-z0-9])")
IBAN_MAX_LENGTH = 34
CARD = re.compile(r"(?<!\w)(?:\d{4}[ -]\d{6}[ -]\d{4,5}|\d{4}(?:[ -]\d{4}){2,3}(?:[ -]\d{1,3})?|\d{13,19})(?!\w)")
MIN_CARD_DIGITS = 13

_SEP = r"(?:[ \u00a0]?[.\-][ \u00a0]?|[ \u00a0])?"
_SEP_SLASH = r"(?:[ \u00a0]?[.\-/][ \u00a0]?|[ \u00a0])?"
PHONE_ITALIAN = re.compile(
    r"(?<![\w+])(?P<prefix>(?:\+|00)39" + _SEP + r"|\(\+?39\)" + _SEP + r")?(?P<number>"
    r"3\d{2}(?:" + _SEP_SLASH + r"\d){6,7}"
    r"|0\d{1,3}(?:" + _SEP_SLASH + r"\d){4,9}"
    r"|\(0\d{1,3}\)" + _SEP + r"\d(?:" + _SEP + r"\d){3,8}"
    r"|8(?:00|03|40|48|9[2-9])(?:" + _SEP + r"\d){6,7}"
    r")(?!\d)"
)
PHONE_INTERNATIONAL = re.compile(r"(?<![\w+])(?:\+|00)[1-9]\d{0,2}(?:" + _SEP + r"(?:\(\d{1,4}\)|\d)){6,14}(?!\d)")
LANDLINE_DIGITS = (6, 11)
INTERNATIONAL_DIGITS = (8, 15)
NOT_PHONE = (
    re.compile(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}"),  # a date
    re.compile(r"\d{1,2}[.:]\d{2} ?[-–/] ?\d{1,2}[.:]\d{2}"),  # a time range
    re.compile(r"\d{1,3}(?:\.\d{3})+"),  # thousands separators
)
NUMBER_JUST_BEFORE = re.compile(r"\w*\d\w*[ .\-/:]?$")

_UPPER = "A-ZÀ-ÖØ-Þ"
_CAPITALIZED = rf"[{_UPPER}][\w'’]*(?:-[\w'’]+)*"
_CONNECTOR = (
    r"(?:(?:di|de|del|dello|della|dei|degli|delle|da|dal|dalla|al|alla|ai|agli|sul|sulla|san|santa|santo)\s+"
    r"|(?:dell|d|sant|all|dall|nell|sull)['’])"
)
_STREET_NAME = rf"(?:{_CONNECTOR})*(?:{_CAPITALIZED}|\d{{1,2}}\s+{_CAPITALIZED})(?:\s+(?:{_CONNECTOR})*{_CAPITALIZED}){{0,3}}"
STREET_TYPES = (
    r"via|viale|v\.le|piazza|p\.zza|p\.za|piazzale|p\.le|piazzetta|vicolo|località|loc\.|lungomare|lungotevere"
    r"|lungarno|contrada|c\.da|circonvallazione"
)
# Also everyday words ("il corso di Python"): need a civic number or a preposition before.
AMBIGUOUS_STREET_TYPES = r"corso|c\.so|largo|l\.go|strada|str\.|borgo|salita|traversa|calle|galleria|rione|vico|frazione|fraz\."
AMBIGUOUS_STREET_WORDS = frozenset(re.sub(r"\\", "", AMBIGUOUS_STREET_TYPES).split("|"))
ADDRESS = re.compile(
    rf"(?<!\w)(?P<type>(?i:{STREET_TYPES}|{AMBIGUOUS_STREET_TYPES}))(?:\s+|(?<=\.))"
    rf"(?P<name>{_STREET_NAME})"
    r"(?P<civic>,?\s*(?:(?i:n\.?|nr\.?|n°|civico)\s*)?\d{1,4}(?:\s?/\s?[A-Za-z0-9]{1,2}|[A-Za-z])?(?:\s+(?i:bis|ter))?(?!\w))?"
    rf"(?P<city>,?\s+\d{{5}}\s+{_CAPITALIZED}(?:\s+{_CAPITALIZED})?(?:\s*\([A-Z]{{2}}\))?)?"
)
LOCATIVE_WORDS = frozenset({"in", "a", "ad", "da", "di", "su", "per", "verso", "tra", "fra", "lungo"})
NOT_STREET_NAMES = frozenset({
    "chat", "discord", "dm", "e-mail", "email", "facebook", "fax", "github", "google", "instagram", "internet",
    "linkedin", "mail", "meet", "messaggio", "messenger", "pec", "posta", "radio", "signal", "skype", "slack",
    "sms", "teams", "telefono", "telegram", "tiktok", "twitter", "web", "whatsapp", "zoom",
})

_MONTHS = (
    r"(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)(?!\w)"
    r"|(?:gen|feb|mar|apr|mag|giu|lug|ago|sett|set|ott|nov|dic)(?!\w)\.?"
)
_DATE = (
    r"\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}[./-]\d{1,2}(?:[./-](?:\d{4}|\d{2}))?"
    rf"|(?:\d{{1,2}}|1°|primo)\s+(?:{_MONTHS})(?:\s+(?:del\s+)?\d{{4}})?"
)
_BIRTH_PLACE = rf"(?:(?:a|ad|in)\s+[{_UPPER}][\w'’]*(?:\s+[{_UPPER}][\w'’]*){{0,2}}\s+)?"
_BIRTH_CUE = (
    rf"(?i:nat[oaie]\s+{_BIRTH_PLACE}(?:il|l['’]|in\s+data)\s*"
    r"|data\s+di\s+nascita\s*(?:[:\-–]|è|e['’])?\s*(?:il\s+|l['’]\s*)?"
    r"|nascita\s*[:\-–]\s*"
    r"|compleanno(?:\s+(?:di|del|della)\s+[\w'’]+)?\s*(?:[:\-–]|è\s+il|è\s+l['’]|cade\s+il|il)\s*"
    r"|d\.\s?d\.\s?n\.?\s*[:\-–]?\s*)"
)
BIRTH_DATE = re.compile(rf"(?<!\w){_BIRTH_CUE}(?P<date>{_DATE})(?!\w)")
BIRTH_YEAR = re.compile(rf"(?<!\w)(?i:nat[oaie]\s+{_BIRTH_PLACE}nel(?:l['’]anno)?\s+)(?P<date>(?:19|20)\d{{2}})(?!\d)")


def _finding(kind: str, text: str, start: int, end: int) -> Finding:
    return Finding(kind=kind, start=start, end=end, text=text[start:end])


def find_emails(text: str) -> Iterator[Finding]:
    for match in EMAIL.finditer(text):
        yield _finding("EMAIL", text, match.start(), match.end())


def _trim_url(candidate: str) -> str:
    while candidate:
        last = candidate[-1]
        if last in URL_TRAILING:
            candidate = candidate[:-1]
        elif last in CLOSING_BRACKETS and candidate.count(CLOSING_BRACKETS[last]) < candidate.count(last):
            candidate = candidate[:-1]
        else:
            break
    return candidate


def find_urls(text: str) -> Iterator[Finding]:
    for pattern in (URL_WITH_SCHEME, URL_BARE_WITH_PATH):
        for match in pattern.finditer(text):
            url = _trim_url(match.group())
            if len(url) > 4:
                yield _finding("URL", text, match.start(), match.start() + len(url))


def find_ips(text: str) -> Iterator[Finding]:
    for pattern in (IPV4, IPV6):
        for match in pattern.finditer(text):
            candidate = match.group()
            if pattern is IPV6 and "::" not in candidate and candidate.count(":") != 7:
                continue
            try:
                ipaddress.ip_address(candidate)
            except ValueError:
                continue
            yield _finding("IP", text, match.start(), match.end())


def find_codici_fiscali(text: str) -> Iterator[Finding]:
    for match in CODICE_FISCALE.finditer(text):
        if codice_fiscale_ok(match.group()):
            yield _finding("CODICE_FISCALE", text, match.start(), match.end())


def find_partite_iva(text: str) -> Iterator[Finding]:
    for match in PARTITA_IVA.finditer(text):
        if partita_iva_ok(match.group().replace(" ", "")):
            yield _finding("PARTITA_IVA", text, match.start(), match.end())


def _alnum_run(text: str, start: int, limit: int) -> List[int]:
    """End offsets of the alphanumeric characters from `start`, single spaces allowed between groups."""
    ends: List[int] = []
    index = start
    while index < len(text) and len(ends) < limit:
        char = text[index]
        if char.isascii() and char.isalnum():
            ends.append(index + 1)
            index += 1
        elif char == " " and ends and index + 1 < len(text) and text[index + 1].isascii() and text[index + 1].isalnum():
            index += 1
        else:
            break
    return ends


def find_ibans(text: str) -> Iterator[Finding]:
    for match in IBAN_START.finditer(text):
        start = match.start()
        ends = _alnum_run(text, start, IBAN_MAX_LENGTH)
        compact = "".join(text[end - 1] for end in ends)
        country = compact[:2].upper()
        lengths = [IBAN_LENGTHS[country]] if country in IBAN_LENGTHS else range(len(compact), 14, -1)
        for length in lengths:
            if length > len(ends):
                continue
            end = ends[length - 1]
            if end < len(text) and text[end].isalnum():
                continue  # the IBAN must end where a group ends
            if iban_ok(compact[:length]):
                yield _finding("IBAN", text, start, end)
                break


def find_cards(text: str) -> Iterator[Finding]:
    for match in CARD.finditer(text):
        groups = list(re.finditer(r"\d+", match.group()))
        for count in (len(groups), len(groups) - 1):
            if count < 1:
                break
            digits = "".join(group.group() for group in groups[:count])
            if len(digits) >= MIN_CARD_DIGITS and digits.strip("0") and luhn_ok(digits) and not isbn13_ok(digits):
                yield _finding("CARTA", text, match.start(), match.start() + groups[count - 1].end())
                break


def _plausible_phone(text: str, match: "re.Match[str]", digits_range: Tuple[int, int], number_group: str = "") -> bool:
    raw = match.group()
    if any(pattern.fullmatch(raw) for pattern in NOT_PHONE) or raw.count("/") > 1:
        return False
    if NUMBER_JUST_BEFORE.search(text, max(0, match.start() - 40), match.start()):
        return False  # a fragment of a longer code (IBAN, list of numbers…)
    digits = re.sub(r"\D", "", match.group(number_group) if number_group else raw)
    return digits_range[0] <= len(digits) <= digits_range[1]


def find_phones(text: str) -> Iterator[Finding]:
    for match in PHONE_ITALIAN.finditer(text):
        if _plausible_phone(text, match, LANDLINE_DIGITS, number_group="number"):
            yield _finding("TELEFONO", text, match.start(), match.end())
    for match in PHONE_INTERNATIONAL.finditer(text):
        if _plausible_phone(text, match, INTERNATIONAL_DIGITS):
            yield _finding("TELEFONO", text, match.start(), match.end())


def _previous_word(text: str, start: int) -> str:
    words = re.findall(r"[\w'’]+", text[max(0, start - 30):start])
    return words[-1].casefold() if words else ""


def find_addresses(text: str) -> Iterator[Finding]:
    for match in ADDRESS.finditer(text):
        first_word = re.split(r"[\s'’]+", match.group("name"))[0].casefold()
        if first_word in NOT_STREET_NAMES:
            continue
        ambiguous = match.group("type").casefold() in AMBIGUOUS_STREET_WORDS
        if ambiguous and not match.group("civic") and _previous_word(text, match.start()) not in LOCATIVE_WORDS:
            continue
        yield _finding("INDIRIZZO", text, match.start(), match.end())


def find_birth_dates(text: str) -> Iterator[Finding]:
    """Only dates with an explicit cue ("nato il", "data di nascita:", "compleanno:"); the span is the date."""
    for pattern in (BIRTH_DATE, BIRTH_YEAR):
        for match in pattern.finditer(text):
            yield _finding("DATA_NASCITA", text, match.start("date"), match.end("date"))


RULE_DETECTORS: Tuple[Detector, ...] = (
    find_emails, find_urls, find_ips, find_codici_fiscali, find_partite_iva, find_ibans, find_cards,
    find_phones, find_addresses, find_birth_dates,
)


# * — dictionary of names —

def fold(text: str) -> str:
    """Comparison form of a name: no accents, no case, single spaces ('Nicolò' == 'nicolo'')."""
    decomposed = unicodedata.normalize("NFKD", text.replace("’", "'"))
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(plain.casefold().replace("-", " ").split()).rstrip("'")


def _strip_accent(char: str) -> str:
    return "".join(part for part in unicodedata.normalize("NFKD", char) if not unicodedata.combining(part))


def _needs_capital(alias: str) -> bool:
    return len(alias) <= MIN_NAME_LENGTH or fold(alias) in COMMON_WORD_NAMES


def _alias_pattern(alias: str) -> str:
    """Regex for one alias: flexible spaces, accented letters also unaccented ('Nicolò', 'Nicolo', "Nicolo'")."""
    words = []
    for word in alias.split():
        pieces = []
        for index, char in enumerate(word):
            base = _strip_accent(char)
            if char in "'’":
                pieces.append("['’]")
            elif char == "-":
                pieces.append(r"[-\s]")
            elif base != char and index == len(word) - 1:
                pieces.append(f"(?:{re.escape(char)}|{re.escape(base)}['’]?)")
            elif base != char:
                pieces.append(f"[{re.escape(char)}{re.escape(base)}]")
            else:
                pieces.append(re.escape(char))
        words.append("".join(pieces))
    pattern = r"\s+".join(words)
    if _needs_capital(alias):
        pattern = rf"(?=(?-i:[{_UPPER}])){pattern}"
    return pattern


def compile_names(aliases: Iterable[str]) -> Optional[Pattern[str]]:
    """One case-insensitive regex for all aliases, longest first, on word boundaries ('Marcon' is not 'Marco')."""
    unique = sorted({alias.strip() for alias in aliases if alias.strip()}, key=lambda alias: (-len(alias), alias))
    if not unique:
        return None
    alternatives = "|".join(_alias_pattern(alias) for alias in unique)
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE)


def _check_alias(alias: object) -> str:
    if not isinstance(alias, str):
        raise ValueError("i nomi del dizionario devono essere testi")
    cleaned = " ".join(alias.split())
    if cleaned and len(cleaned) < MIN_NAME_LENGTH:
        raise ValueError(f"nome troppo corto per essere riconosciuto: '{cleaned}'")
    return cleaned


def name_parts(full_name: str) -> List[str]:
    """'Marco De Luca' -> ['Marco', 'Luca']: the single words worth matching alone."""
    return [
        part for part in full_name.split()
        if fold(part) not in NAME_PARTICLES and len(part.strip("'’.")) >= MIN_NAME_PART_LENGTH
    ]


def people_groups(people: Iterable[Tuple[str, Iterable[str]]]) -> List[List[str]]:
    """Alias groups from (full name, nicknames): full name first, then nicknames, then name parts.

    A form shared by two people ('Marco' of Marco Rossi and Marco Bianchi) leaves
    both groups and becomes a group of its own, so it is still replaced.
    """
    groups: List[List[str]] = []
    for full_name, nicknames in people:
        aliases: List[str] = []
        seen = set()
        for alias in [full_name, *nicknames, *name_parts(full_name)]:
            alias = " ".join(alias.split())
            if len(alias) >= MIN_NAME_LENGTH and fold(alias) not in seen:
                seen.add(fold(alias))
                aliases.append(alias)
        if aliases:
            groups.append(aliases)
    owners: Dict[str, int] = {}
    for group in groups:
        for alias in group:
            owners[fold(alias)] = owners.get(fold(alias), 0) + 1
    shared: Dict[str, str] = {}
    result: List[List[str]] = []
    for group in groups:
        for alias in group:
            if owners[fold(alias)] > 1:
                shared.setdefault(fold(alias), alias)
        own = [alias for alias in group if owners[fold(alias)] == 1]
        if own:
            result.append(own)
    return result + [[alias] for alias in shared.values()]


def is_person_template(template: Template) -> bool:
    """Templates describing a person (like 'persona'), not events with people (like 'incontro')."""
    if template.category != PERSON_CATEGORY:
        return False
    return template.title_key in PERSON_NAME_KEYS or any(block.key == NICKNAMES_KEY for block in template.blocks)


def people_from_entries(pairs: Iterable[Tuple[Entry, Template]]) -> List[List[str]]:
    """Alias groups from the user's person entries: title plus the `soprannomi` tags."""
    people = []
    for entry, template in pairs:
        if not is_person_template(template):
            continue
        nicknames = [
            tag for block in template.blocks
            if block.key == NICKNAMES_KEY and block.type == "tags"
            for tag in entry.values.get(block.key, [])
        ]
        people.append((entry.title(template), nicknames))
    return people_groups(people)


# * — overlaps and placeholders —

def _priority(kind: str) -> int:
    return KIND_PRIORITY.index(kind) if kind in KIND_PRIORITY else len(KIND_PRIORITY)


def resolve_overlaps(findings: Iterable[Finding]) -> List[Finding]:
    """Keep non-overlapping findings: the longest wins, then the earliest, then by KIND_PRIORITY."""
    ranked = sorted(
        {finding for finding in findings if finding.length > 0},
        key=lambda finding: (-finding.length, finding.start, _priority(finding.kind), finding.kind),
    )
    chosen: List[Finding] = []
    for finding in ranked:
        if all(finding.end <= other.start or finding.start >= other.end for other in chosen):
            chosen.append(finding)
    return sorted(chosen, key=lambda finding: finding.start)


def _phone_key(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if value.lstrip("(").startswith("+"):
        digits = "+" + digits
    elif digits.startswith("00"):
        digits = "+" + digits[2:]
    return digits[3:] if digits.startswith("+39") else digits


def value_key(finding: Finding) -> str:
    """Normalised value: two spellings of the same data get the same placeholder."""
    if finding.kind == "TELEFONO":
        return _phone_key(finding.text)
    if finding.kind in ("IBAN", "CODICE_FISCALE", "CARTA", "PARTITA_IVA"):
        compact = re.sub(r"[^0-9A-Za-z]", "", finding.text).upper()
        return compact[2:] if finding.kind == "PARTITA_IVA" and compact.startswith("IT") else compact
    if finding.kind == "IP":
        return str(ipaddress.ip_address(finding.text))
    if finding.kind in ("URL", "EMAIL"):
        return finding.text.casefold().rstrip("/")
    return fold(finding.text)


def placeholder_text(kind: str, number: int) -> str:
    return f"[{kind}_{number}]"


ANSWER_PLACEHOLDER = re.compile(r"\[\s*([A-Za-z][A-Za-z_]*?)[_ ](\d+)\s*\]|(?<![\w\[])([A-Z][A-Z_]*?)_(\d+)(?!\w)")


def restore(text: str, mapping: Mapping[str, str]) -> str:
    """Put the originals back in a model's answer.

    Tolerates what models do to placeholders: repeat them, change case
    ('[persona_1]'), add spaces ('[ PERSONA 1 ]') or drop the brackets ('PERSONA_1').
    Unknown placeholders stay as they are.
    """
    def original(match: "re.Match[str]") -> str:
        kind = match.group(1) or match.group(3)
        number = match.group(2) or match.group(4)
        return mapping.get(placeholder_text(kind.upper(), int(number)), match.group())

    return ANSWER_PLACEHOLDER.sub(original, text)


# * — the anonymizer —

class Anonymizer:
    """Finds personal data and replaces it with placeholders, consistent within one session.

    - `names`: single names or nicknames, each with its own placeholder;
    - `people`: alias groups, one placeholder per person (`people_groups`); restore
      uses the first alias, usually the full name;
    - `terms`: extra dictionary words by kind, for example {"LUOGO": ["Bressanone"]};
    - `detectors`: rule detectors to use (default RULE_DETECTORS); a local NER model
      can be added here later.

    The same value always gets the same placeholder in one Anonymizer, so several
    texts sent together stay coherent. `forget()` starts a new session.
    """

    def __init__(
        self,
        names: Iterable[str] = (),
        people: Iterable[Sequence[str]] = (),
        terms: Optional[Mapping[str, Iterable[str]]] = None,
        detectors: Optional[Sequence[Detector]] = None,
    ) -> None:
        self.detectors: List[Detector] = list(RULE_DETECTORS if detectors is None else detectors)
        self._groups: Dict[Tuple[str, str], str] = {}
        self._canonical: Dict[str, str] = {}
        aliases_by_kind: Dict[str, List[str]] = {"PERSONA": []}
        for group_number, group in enumerate(people):
            if isinstance(group, str):
                raise ValueError("ogni persona è una lista di nomi, non un singolo testo")
            cleaned = [alias for alias in (_check_alias(item) for item in group) if alias]
            if not cleaned:
                continue
            group_key = f"#persona-{group_number}"
            self._canonical[group_key] = cleaned[0]
            for alias in cleaned:
                self._groups.setdefault(("PERSONA", fold(alias)), group_key)
                aliases_by_kind["PERSONA"].append(alias)
        aliases_by_kind["PERSONA"].extend(alias for alias in (_check_alias(name) for name in names) if alias)
        for kind, kind_terms in (terms or {}).items():
            if not isinstance(kind, str) or not CUSTOM_KIND.match(kind):
                raise ValueError(f"tipo di termine non valido: '{kind}' (maiuscole e _, per esempio LUOGO)")
            aliases_by_kind.setdefault(kind, []).extend(alias for alias in (_check_alias(term) for term in kind_terms) if alias)
        self.names: List[str] = sorted(set(aliases_by_kind["PERSONA"]), key=str.casefold)
        self._matchers: List[Tuple[str, Pattern[str]]] = [
            (kind, pattern) for kind, aliases in aliases_by_kind.items() if (pattern := compile_names(aliases))
        ]
        self.forget()

    def forget(self) -> None:
        """Start a new session: placeholders restart from 1 and the table is emptied."""
        self._placeholders: Dict[Tuple[str, str], str] = {}
        self._counters: Dict[str, int] = {}
        self._originals: Dict[str, str] = {}

    @property
    def mapping(self) -> Dict[str, str]:
        """Placeholder → original for everything pseudonymised in this session."""
        return dict(self._originals)

    def find(self, text: str) -> List[Finding]:
        if not isinstance(text, str):
            raise ValueError("serve un testo da anonimizzare")
        findings: List[Finding] = []
        for detector in self.detectors:
            findings.extend(detector(text))
        for kind, pattern in self._matchers:
            findings.extend(_finding(kind, text, match.start(), match.end()) for match in pattern.finditer(text))
        return resolve_overlaps(findings)

    def anonymize(self, text: str, mode: str = "pseudo") -> AnonymizedText:
        if mode not in MODES:
            raise ValueError(f"modalità sconosciuta '{mode}': usa {' oppure '.join(MODES)}")
        pieces: List[str] = []
        replacements: List[Replacement] = []
        mapping: Dict[str, str] = {}
        cursor = 0
        for finding in self.find(text):
            placeholder = self._placeholder(finding, keep_original=mode == "pseudo")
            pieces.extend((text[cursor:finding.start], placeholder))
            cursor = finding.end
            replacements.append(Replacement(finding, placeholder))
            if mode == "pseudo":
                mapping[placeholder] = self._originals[placeholder]
        pieces.append(text[cursor:])
        return AnonymizedText(text="".join(pieces), mode=mode, replacements=replacements, mapping=mapping)

    def restore(self, text: str) -> str:
        """Restore with the whole session table (several texts sent together)."""
        return restore(text, self._originals)

    def _placeholder(self, finding: Finding, keep_original: bool) -> str:
        group_key = self._groups.get((finding.kind, fold(finding.text)))
        key = (finding.kind, group_key or value_key(finding))
        placeholder = self._placeholders.get(key)
        if placeholder is None:
            number = self._counters.get(finding.kind, 0) + 1
            self._counters[finding.kind] = number
            placeholder = self._placeholders[key] = placeholder_text(finding.kind, number)
        if keep_original:
            self._originals.setdefault(placeholder, self._canonical[group_key] if group_key else finding.text)
        return placeholder
