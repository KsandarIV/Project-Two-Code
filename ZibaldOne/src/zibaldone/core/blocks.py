"""Block types: the bricks every template is made of.

A block type knows how to check its options, normalise a value, read a value
typed in the terminal and turn a value into plain text (for search, export
and the anonymizer). Values are plain JSON data, never objects.
"""

import math
import re
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Tuple

# — option checks —


def _int_option(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"l'opzione '{name}' deve essere un numero intero")
    return value


def is_number(value: Any) -> bool:
    """True for finite int or float values (bool excluded)."""
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _number_option(value: Any, name: str) -> float:
    if not is_number(value):
        raise ValueError(f"l'opzione '{name}' deve essere un numero")
    return value


def _str_option(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) > 200:
        raise ValueError(f"l'opzione '{name}' deve essere un testo breve")
    return value


def _bool_option(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"l'opzione '{name}' deve essere true o false")
    return value


def _str_list_option(value: Any, name: str) -> List[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"l'opzione '{name}' deve essere una lista di testi")
    if len(value) > 100:
        raise ValueError(f"l'opzione '{name}' ha troppe voci (massimo 100)")
    return [item.strip() for item in value]


def _number_list_option(value: Any, name: str) -> List[float]:
    if not isinstance(value, list) or not all(is_number(item) for item in value):
        raise ValueError(f"l'opzione '{name}' deve essere una lista di numeri")
    return value


OptionCheck = Callable[[Any, str], Any]

PROGRESS_STATUSES: Dict[str, str] = {
    "wishlist": "Da fare",
    "not_started": "Non iniziato",
    "ongoing": "In corso",
    "paused": "In pausa",
    "completed": "Completato",
    "dropped": "Abbandonato",
}

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ITALIAN_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
ENTRY_ID = re.compile(r"^[0-9a-f]{32}$")


def parse_day(raw: str) -> str:
    """Accept YYYY-MM-DD, DD/MM/YYYY, 'oggi' or 'ieri' and return YYYY-MM-DD."""
    text = raw.strip().lower()
    if text in ("oggi", "today"):
        return date.today().isoformat()
    if text in ("ieri", "yesterday"):
        return date.fromordinal(date.today().toordinal() - 1).isoformat()
    match = ITALIAN_DATE.match(text)
    if match:
        day, month, year = (int(part) for part in match.groups())
        text = f"{year:04d}-{month:02d}-{day:02d}"
    if not ISO_DATE.match(text):
        raise ValueError(f"data non valida: '{raw}' (usa AAAA-MM-GG oppure GG/MM/AAAA)")
    try:
        date.fromisoformat(text)
    except ValueError as error:
        raise ValueError(f"data non valida: '{raw}'") from error
    return text


class BlockType:
    """Base class. Subclasses set the class attributes and override the hooks."""

    name: str = ""
    label: str = ""
    description: str = ""
    # Philosophical name shown next to the plain label (brand identity).
    nickname: str = ""
    nickname_source: str = ""
    options: Dict[str, OptionCheck] = {}

    def check_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        unknown = set(options) - set(self.options)
        if unknown:
            raise ValueError(f"opzioni sconosciute per il blocco '{self.name}': {', '.join(sorted(unknown))}")
        checked = {key: self.options[key](value, key) for key, value in options.items()}
        self.check_option_rules(checked)
        return checked

    def check_option_rules(self, options: Dict[str, Any]) -> None:
        """Cross-option rules (for example min < max)."""

    def normalize(self, value: Any, options: Dict[str, Any]) -> Any:
        raise NotImplementedError

    def parse(self, raw: str, options: Dict[str, Any]) -> Any:
        """Read a value typed by the user in the terminal."""
        return self.normalize(raw, options)

    def to_text(self, value: Any, options: Dict[str, Any]) -> str:
        return str(value)

    def is_empty(self, value: Any) -> bool:
        return value is None or value == "" or value == [] or value == {}


# — v0.0.3 base blocks —


class TextBlock(BlockType):
    name = "text"
    label = "Testo breve"
    description = "una riga di testo, per esempio un titolo"
    nickname = "Aforisma"
    nickname_source = "il pensiero breve: Ippocrate, Leopardi, Nietzsche"
    options = {"max_length": _int_option, "placeholder": _str_option}

    def normalize(self, value: Any, options: Dict[str, Any]) -> str:
        if not isinstance(value, str):
            raise ValueError("serve un testo")
        text = " ".join(value.split())
        limit = options.get("max_length", 300)
        if len(text) > limit:
            raise ValueError(f"testo troppo lungo (massimo {limit} caratteri)")
        return text


class LongTextBlock(TextBlock):
    name = "longtext"
    label = "Testo lungo"
    description = "riflessioni, note, recensioni, su più righe"
    nickname = "Saggio"
    nickname_source = "Montaigne, Saggi (1580): scrivere per provarsi"

    def normalize(self, value: Any, options: Dict[str, Any]) -> str:
        if not isinstance(value, str):
            raise ValueError("serve un testo")
        text = value.replace("\r\n", "\n").strip()
        limit = options.get("max_length", 50_000)
        if len(text) > limit:
            raise ValueError(f"testo troppo lungo (massimo {limit} caratteri)")
        return text

    def parse(self, raw: str, options: Dict[str, Any]) -> str:
        # In the terminal "\n" typed literally becomes a new line.
        return self.normalize(raw.replace("\\n", "\n"), options)


class NumberBlock(BlockType):
    name = "number"
    label = "Numero"
    description = "un numero, con unità facoltativa (pagine, ore, euro)"
    nickname = "Misura"
    nickname_source = "Protagora: l'uomo è misura di tutte le cose"
    options = {"min": _number_option, "max": _number_option, "unit": _str_option, "integer": _bool_option}

    def check_option_rules(self, options: Dict[str, Any]) -> None:
        if "min" in options and "max" in options and options["min"] > options["max"]:
            raise ValueError("'min' deve essere minore di 'max'")

    def normalize(self, value: Any, options: Dict[str, Any]) -> float:
        if not is_number(value):
            raise ValueError("serve un numero")
        if options.get("integer") and value != int(value):
            raise ValueError("serve un numero intero")
        if "min" in options and value < options["min"]:
            raise ValueError(f"il valore minimo è {options['min']}")
        if "max" in options and value > options["max"]:
            raise ValueError(f"il valore massimo è {options['max']}")
        return int(value) if value == int(value) else float(value)

    def parse(self, raw: str, options: Dict[str, Any]) -> float:
        try:
            number = float(raw.strip().replace(",", "."))
        except ValueError as error:
            raise ValueError(f"'{raw}' non è un numero") from error
        return self.normalize(number, options)

    def to_text(self, value: Any, options: Dict[str, Any]) -> str:
        unit = options.get("unit")
        return f"{value} {unit}" if unit else str(value)


class RatingBlock(BlockType):
    name = "rating"
    label = "Voto a stelle"
    description = "un voto da 0 al massimo scelto (5 di base)"
    nickname = "Giudizio"
    nickname_source = "Kant, Critica del Giudizio (1790): il giudizio di gusto"
    options = {"max": _int_option}

    def check_option_rules(self, options: Dict[str, Any]) -> None:
        if not 3 <= options.get("max", 5) <= 10:
            raise ValueError("il voto massimo deve essere tra 3 e 10")

    def normalize(self, value: Any, options: Dict[str, Any]) -> int:
        if not is_number(value) or value != int(value):
            raise ValueError("il voto è un numero intero")
        top = options.get("max", 5)
        if not 0 <= value <= top:
            raise ValueError(f"il voto va da 0 a {top}")
        return int(value)

    def parse(self, raw: str, options: Dict[str, Any]) -> int:
        text = raw.strip()
        if text and set(text) <= {"*", "★"}:
            return self.normalize(len(text), options)
        try:
            return self.normalize(int(text), options)
        except ValueError as error:
            raise ValueError(f"'{raw}' non è un voto valido") from error

    def to_text(self, value: Any, options: Dict[str, Any]) -> str:
        top = options.get("max", 5)
        return "★" * value + "☆" * (top - value)


class TagsBlock(BlockType):
    name = "tags"
    label = "Etichette"
    description = "parole chiave, per filtrare e collegare"
    nickname = "Categorie"
    nickname_source = "Aristotele, Categorie"
    options = {"suggestions": _str_list_option}

    def normalize(self, value: Any, options: Dict[str, Any]) -> List[str]:
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError("servono delle etichette")
        tags: List[str] = []
        for item in value:
            tag = " ".join(item.strip().lstrip("#").lower().split())
            if not tag:
                continue
            if len(tag) > 60:
                raise ValueError(f"etichetta troppo lunga: '{tag[:20]}…'")
            if tag not in tags:
                tags.append(tag)
        if len(tags) > 50:
            raise ValueError("troppe etichette (massimo 50)")
        return tags

    def parse(self, raw: str, options: Dict[str, Any]) -> List[str]:
        return self.normalize(re.split(r"[,;]", raw), options)

    def to_text(self, value: Any, options: Dict[str, Any]) -> str:
        return ", ".join(value)


# — v0.0.4 blocks —


class DateBlock(BlockType):
    name = "date"
    label = "Data"
    description = "un giorno (compleanno, uscita, scadenza)"
    nickname = "Chronos"
    nickname_source = "il tempo che scorre, per i Greci"
    options = {}

    def normalize(self, value: Any, options: Dict[str, Any]) -> str:
        if not isinstance(value, str):
            raise ValueError("serve una data")
        return parse_day(value)


class ChecklistBlock(BlockType):
    name = "checklist"
    label = "Lista di cose da fare"
    description = "voci da spuntare: obiettivi, priorità, to-do"
    nickname = "Regole"
    nickname_source = "Descartes, Discorso sul metodo (1637): le regole e la morale provvisoria"
    options = {"max_items": _int_option}

    def normalize(self, value: Any, options: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            raise ValueError("serve una lista")
        items = []
        for item in value:
            if isinstance(item, str):
                item = {"text": item, "done": False}
            if not isinstance(item, dict) or set(item) - {"text", "done"}:
                raise ValueError("ogni voce ha solo 'text' e 'done'")
            text = " ".join(str(item.get("text", "")).split())
            if not text:
                continue
            if len(text) > 300:
                raise ValueError("voce troppo lunga (massimo 300 caratteri)")
            items.append({"text": text, "done": bool(item.get("done", False))})
        if len(items) > options.get("max_items", 100):
            raise ValueError(f"troppe voci (massimo {options.get('max_items', 100)})")
        return items

    def parse(self, raw: str, options: Dict[str, Any]) -> List[Dict[str, Any]]:
        items = []
        for part in raw.split(";"):
            part = part.strip()
            done = part.lower().startswith("[x]")
            if part.startswith("[") and "]" in part[:4]:
                part = part[part.index("]") + 1:]
            items.append({"text": part, "done": done})
        return self.normalize(items, options)

    def to_text(self, value: Any, options: Dict[str, Any]) -> str:
        return "; ".join(("[x] " if item["done"] else "[ ] ") + item["text"] for item in value)


class ScaleBlock(BlockType):
    name = "scale"
    label = "Scala"
    description = "un punteggio su una scala, per esempio da 0 a 10"
    nickname = "Giusto mezzo"
    nickname_source = "Aristotele, Etica Nicomachea II: la virtù sta tra due estremi"
    options = {"min": _int_option, "max": _int_option, "low_label": _str_option, "high_label": _str_option}

    def bounds(self, options: Dict[str, Any]) -> Tuple[int, int]:
        return options.get("min", 0), options.get("max", 10)

    def check_option_rules(self, options: Dict[str, Any]) -> None:
        low, high = self.bounds(options)
        if not low < high or high - low > 100:
            raise ValueError("la scala va da 'min' a 'max', con min < max e al massimo 100 passi")

    def normalize(self, value: Any, options: Dict[str, Any]) -> int:
        low, high = self.bounds(options)
        if not is_number(value) or value != int(value):
            raise ValueError("serve un numero intero")
        if not low <= value <= high:
            raise ValueError(f"il valore va da {low} a {high}")
        return int(value)

    def parse(self, raw: str, options: Dict[str, Any]) -> int:
        try:
            return self.normalize(int(raw.strip()), options)
        except ValueError as error:
            low, high = self.bounds(options)
            raise ValueError(f"'{raw}' non è un numero da {low} a {high}") from error

    def to_text(self, value: Any, options: Dict[str, Any]) -> str:
        return f"{value}/{self.bounds(options)[1]}"


class ChoiceBlock(BlockType):
    name = "choice"
    label = "Scelta"
    description = "una voce da un elenco, per esempio l'umore"
    nickname = "Aut-Aut"
    nickname_source = "Kierkegaard, Aut-Aut (1843)"
    # `values` gives each choice a number, so statistics can follow it over time.
    options = {"choices": _str_list_option, "values": _number_list_option}

    def check_option_rules(self, options: Dict[str, Any]) -> None:
        choices = options.get("choices")
        if not choices or len(choices) < 2:
            raise ValueError("il blocco scelta ha bisogno di almeno 2 'choices'")
        if len(set(choice.lower() for choice in choices)) != len(choices):
            raise ValueError("le scelte devono essere diverse tra loro")
        if "values" in options and len(options["values"]) != len(choices):
            raise ValueError("'values' deve avere un numero per ogni scelta")

    def score(self, value: str, options: Dict[str, Any]) -> Optional[float]:
        """The number attached to a choice, if the template defines `values`."""
        values = options.get("values")
        if not values or value not in options.get("choices", []):
            return None
        return values[options["choices"].index(value)]

    def normalize(self, value: Any, options: Dict[str, Any]) -> str:
        if not isinstance(value, str):
            raise ValueError("serve una delle scelte")
        for choice in options.get("choices", []):
            if value.strip().lower() == choice.lower():
                return choice
        raise ValueError(f"scegli tra: {', '.join(options.get('choices', []))}")

    def parse(self, raw: str, options: Dict[str, Any]) -> str:
        choices = options.get("choices", [])
        text = raw.strip()
        if text.isdigit() and 1 <= int(text) <= len(choices):
            return choices[int(text) - 1]
        # Accept a unique prefix, ignoring a leading emoji: "buo" -> "🙂 Buono".
        lowered = text.lower()
        matches = [choice for choice in choices if choice.lower().split(" ", 1)[-1].startswith(lowered) or choice.lower().startswith(lowered)]
        if lowered and len(matches) == 1:
            return matches[0]
        return self.normalize(text, options)


class ProgressBlock(BlockType):
    name = "progress"
    label = "Avanzamento"
    description = "stato (da fare, in corso, completato …) e contatore, per esempio pagine lette"
    nickname = "Divenire"
    nickname_source = "Eraclito: tutto scorre"
    options = {"unit": _str_option, "total": _int_option}

    def normalize(self, value: Any, options: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(value, dict) or set(value) - {"status", "current", "total"}:
            raise ValueError("l'avanzamento ha 'status', 'current' e 'total'")
        status = value.get("status", "not_started")
        if status not in PROGRESS_STATUSES:
            raise ValueError(f"stato sconosciuto: {status}")
        result: Dict[str, Any] = {"status": status}
        for key in ("current", "total"):
            number = value.get(key)
            if number is None:
                continue
            if not is_number(number) or number < 0:
                raise ValueError(f"'{key}' deve essere un numero positivo")
            result[key] = int(number) if number == int(number) else float(number)
        if "total" not in result and "total" in options:
            result["total"] = options["total"]
        if "current" in result and "total" in result and result["current"] > result["total"]:
            raise ValueError("il contatore supera il totale")
        if status == "completed" and "total" in result:
            result["current"] = result["total"]
        return result

    def parse(self, raw: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Formats: 'in corso', '150/320', 'in corso 150/320', 'completato'."""
        text = raw.strip().lower()
        value: Dict[str, Any] = {}
        counter = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:/\s*(\d+(?:[.,]\d+)?))?\s*$", text)
        if counter:
            value["current"] = float(counter.group(1).replace(",", "."))
            if counter.group(2):
                value["total"] = float(counter.group(2).replace(",", "."))
            text = text[: counter.start()].strip()
        status = None
        for key, label in PROGRESS_STATUSES.items():
            if text in (key, label.lower()) or (text and label.lower().startswith(text)):
                status = key
                break
        if text and status is None:
            raise ValueError(f"stato sconosciuto: '{raw}'. Usa: {', '.join(PROGRESS_STATUSES.values())}")
        value["status"] = status or ("ongoing" if "current" in value else "not_started")
        return self.normalize(value, options)

    def to_text(self, value: Any, options: Dict[str, Any]) -> str:
        text = PROGRESS_STATUSES[value["status"]]
        if "current" in value:
            counter = f"{value['current']}"
            if "total" in value:
                counter += f"/{value['total']}"
            unit = options.get("unit")
            text += f" ({counter}{' ' + unit if unit else ''})"
        return text

    def is_empty(self, value: Any) -> bool:
        return value is None or value == {}


class BookmarkBlock(TextBlock):
    name = "bookmark"
    label = "Segnalibro"
    description = "dove sei arrivato: 'pag. 150', 'S02E05', 'capitolo 7'"
    nickname = "Anamnesi"
    nickname_source = "Platone, Menone: conoscere è ricordare"
    options = {"placeholder": _str_option}

    def normalize(self, value: Any, options: Dict[str, Any]) -> str:
        return super().normalize(value, {"max_length": 120})


class LinkBlock(BlockType):
    name = "link"
    label = "Collegamento"
    description = "collega questa voce ad altre (per esempio a una Persona)"
    nickname = "Nesso"
    nickname_source = "Hume, Ricerca sull'intelletto umano: la connessione tra le idee"
    options = {"template": _str_option, "multiple": _bool_option}

    def normalize(self, value: Any, options: Dict[str, Any]) -> List[str]:
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list) or not all(isinstance(item, str) and ENTRY_ID.match(item) for item in value):
            raise ValueError("i collegamenti sono identificativi di voci")
        unique = list(dict.fromkeys(value))
        if not options.get("multiple", True) and len(unique) > 1:
            raise ValueError("questo blocco collega una sola voce")
        return unique

    def parse(self, raw: str, options: Dict[str, Any]) -> List[str]:
        # The CLI resolves titles and short ids to full ids before calling normalize.
        return self.normalize([part.strip() for part in raw.split(",") if part.strip()], options)

    def to_text(self, value: Any, options: Dict[str, Any]) -> str:
        return ", ".join(item[:8] for item in value)


BLOCK_TYPES: Dict[str, BlockType] = {
    block.name: block
    for block in (
        TextBlock(),
        LongTextBlock(),
        NumberBlock(),
        RatingBlock(),
        TagsBlock(),
        DateBlock(),
        ChecklistBlock(),
        ScaleBlock(),
        ChoiceBlock(),
        ProgressBlock(),
        BookmarkBlock(),
        LinkBlock(),
    )
}

BASE_BLOCK_TYPES = ("text", "number", "rating", "tags")


def get_block_type(name: str) -> BlockType:
    try:
        return BLOCK_TYPES[name]
    except KeyError:
        raise ValueError(f"tipo di blocco sconosciuto: '{name}'. Tipi disponibili: {', '.join(BLOCK_TYPES)}") from None


def block_type_or_none(name: str) -> Optional[BlockType]:
    return BLOCK_TYPES.get(name)
