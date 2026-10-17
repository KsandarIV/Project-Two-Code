"""Le Nuvole and the encryption of Mnemosyne as plain data for the views (no Flet).

The cloud and the keys belong to the core (`zibaldone.cloud`, `storage.keys`);
here only what the screens show: lines, choices, checks and the app wording
of messages that were written for the terminal.
"""

from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Tuple

from zibaldone.ui.viewmodels import MONTHS_SHORT, local_timestamp

CONFIRM_ATTEMPTS = 3
MIN_PASSPHRASE_LENGTH = 10  # the core's rule wins when it is importable
LOOKALIKES = str.maketrans({"O": "0", "I": "1", "L": "1"})

# Core messages name terminal commands; in the app the same thing is a button.
APP_HINTS: Tuple[Tuple[str, str], ...] = (
    ("con `zbone cloud use google` o `zbone cloud use folder PERCORSO`", "in Le Nuvole, alla voce «Dove vanno le copie»"),
    ("`zbone backup setup`", "«Attiva la cifratura» in Impostazioni · Mnemosyne"),
    ("`zbone account login`", "«Entra con Google» in Impostazioni · Le Nuvole"),
    ("`zbone cloud recovery on`", "Impostazioni · Le Nuvole"),
    ("`zbone cloud sync`", "«Sincronizza ora» in Le Nuvole"),
    ("`zbone cloud`", "Impostazioni · Le Nuvole"),
    ("con `zbone privacy`", "in Impostazioni · Parresia"),
    ("`zbone privacy`", "Impostazioni · Parresia"),
)

RECOVERY_TRADEOFF_FALLBACK = (
    "Recupero con l'account Google (facoltativo): se lo attivi, su un dispositivo nuovo ti basterà entrare "
    "con Google per riavere i backup, anche senza passphrase. Il prezzo: chi riesce a entrare nel tuo account "
    "Google può aprirli. Se non lo attivi, servono la passphrase o il codice di recupero."
)


def app_hint(message: str) -> str:
    """Rewrite the terminal commands in a core message as places in the app."""
    text = str(message or "")
    for command, place in APP_HINTS:
        text = text.replace(command, place)
    return text


def error_text(error: BaseException) -> str:
    """What to show for an error: the core already writes Italian sentences."""
    text = app_hint(str(error)).strip()
    if not text:
        return f"qualcosa non ha funzionato ({type(error).__name__})"
    return text[0].upper() + text[1:]


# * — account and destination —


@dataclass(frozen=True)
class ModeChoice:
    mode: str
    label: str
    hint: str
    enabled: bool


def mode_choices(status: Any) -> List[ModeChoice]:
    signed_in = bool(getattr(status, "signed_in", False))
    drive = bool(getattr(status, "drive_allowed", False))
    email = getattr(status, "email", None) or ""
    if not signed_in:
        google_hint = "prima entra con Google, qui sopra"
    elif not drive:
        google_hint = "all'accesso non hai dato il permesso per Drive: esci e rientra lasciando la casella spuntata"
    else:
        google_hint = f"cifrate, nello spazio nascosto dell'app sul Drive di {email}"
    return [
        ModeChoice("local", "Solo su questo dispositivo", "puoi cambiare idea quando vuoi", True),
        ModeChoice("google", "Anche su Google Drive", google_hint, signed_in and drive),
        ModeChoice("folder", "Anche in una cartella", "una chiavetta, o la cartella di OneDrive o Dropbox", True),
    ]


def who(status: Any) -> str:
    name = getattr(status, "name", None) or ""
    email = getattr(status, "email", None) or ""
    return f"{name} <{email}>" if name and email else (email or name)


def cloud_lines(status: Any, encryption_on: bool) -> List[Tuple[str, str]]:
    """(label, value) pairs for the Nuvole page."""
    if status is None:
        return []
    lines: List[Tuple[str, str]] = []
    if getattr(status, "signed_in", False):
        lines.append(("Account", f"{who(status)} (Google)"))
        lines.append(("Permesso Drive", "sì" if getattr(status, "drive_allowed", False) else "no: copie solo qui o in una cartella"))
    elif getattr(status, "google_configured", False):
        lines.append(("Account", "non sei entrato"))
    else:
        lines.append(("Account", "nessuno: l'accesso con Google non è configurato in questa copia, funziona tutto in locale"))
    mode = getattr(status, "mode", "local")
    lines.append(("Copie", str(getattr(status, "mode_label", None) or mode)))
    if mode == "folder" and getattr(status, "folder_path", None):
        lines.append(("Cartella", str(status.folder_path)))
    if mode == "google":
        lines.append(("Recupero con Google", "attivo" if getattr(status, "google_recovery", False) else "non attivo"))
    lines.append(("Cifratura dei backup", "attiva" if encryption_on else "non attiva"))
    if mode != "local":
        last = getattr(status, "last_sync", None)
        lines.append(("Ultima copia", local_timestamp(last) if last else "mai"))
        error = getattr(status, "last_sync_error", None)
        if error:
            lines.append(("Problema", app_hint(error)))
    return lines


def needs_encryption_note(status: Any, encryption_on: bool) -> str:
    if status is None or getattr(status, "mode", "local") == "local" or encryption_on:
        return ""
    return "Le copie partono quando attivi la cifratura dei backup: nessun dato esce dal dispositivo in chiaro."


def destination_label(status: Any) -> str:
    mode = getattr(status, "mode", "local")
    if mode == "google":
        email = getattr(status, "email", None)
        return f"Google Drive ({email})" if email else "Google Drive"
    if mode == "folder":
        return str(getattr(status, "folder_path", None) or "la cartella scelta")
    return ""


def sign_in_notes(before: Any, after: Any) -> List[str]:
    """What to tell after a sign-in, like `zbone account login` does."""
    notes = [f"Sei entrato come {getattr(after, 'email', '') or 'utente Google'}."]
    if (
        before is not None
        and getattr(before, "signed_in", False)
        and getattr(before, "email", None) != getattr(after, "email", None)
        and getattr(before, "mode", "") == "google"
    ):
        notes.append("È un account diverso dal precedente: le copie su Drive sono tornate a solo locale.")
    if not getattr(after, "drive_allowed", False):
        notes.append("Non hai dato il permesso per Drive: le copie possono stare solo qui o in una cartella.")
    return notes


# * — encryption of the snapshots —


def check_new_passphrase(first: str, second: str) -> str:
    """'' when the new passphrase is fine, else the reason (Italian)."""
    try:
        from zibaldone.storage.keys import KeysError, check_passphrase
    except Exception:  # the keys part is missing: apply the same length rule
        if len(first or "") < MIN_PASSPHRASE_LENGTH:
            return f"La passphrase deve avere almeno {MIN_PASSPHRASE_LENGTH} caratteri: meglio tre o quattro parole a caso."
    else:
        try:
            check_passphrase(first or "")
        except KeysError as problem:
            return error_text(problem)
    if first != second:
        return "Le due passphrase non coincidono."
    return ""


def recovery_last_group(code: str) -> str:
    return (code or "").split("-")[-1].strip().upper().translate(LOOKALIKES)


def recovery_answer_ok(code: str, answer: str) -> bool:
    """The user copied the last group of the code (case and O/0, I/L/1 forgiven)."""
    cleaned = "".join((answer or "").split()).replace("-", "").upper().translate(LOOKALIKES)
    return bool(cleaned) and cleaned == recovery_last_group(code)


# * — the copies that are out there —


@dataclass(frozen=True)
class RemoteChoice:
    id: str
    label: str


def remote_choices(snapshots: Iterable[Any]) -> List[RemoteChoice]:
    """Snapshot ids with '17 ott 2026, 12:33 · 1.2 MB', newest first as given."""
    from datetime import datetime, timezone

    from zibaldone.storage.paths import human_size

    choices = []
    for item in snapshots:
        created = getattr(item, "created_at", None)
        if isinstance(created, datetime):
            moment = created.astimezone() if created.tzinfo else created.replace(tzinfo=timezone.utc).astimezone()
            when = f"{moment.day} {MONTHS_SHORT[moment.month - 1]} {moment.year}, {moment:%H:%M}"
        else:
            when = str(created or "")
        size = human_size(int(getattr(item, "size", 0) or 0))
        choices.append(RemoteChoice(str(getattr(item, "id", "")), f"{when} · {size}"))
    return choices


def restored_text(result: Any) -> str:
    restored = getattr(result, "restored", None)
    created = getattr(restored, "created_at", None)
    when = ""
    if created is not None:
        when = remote_choices([restored])[0].label.split(" · ")[0]
    text = f"Dati riportati all'istantanea del {when}." if when else "Dati riportati."
    return text + " Le chiavi dei backup ora sono anche qui: i prossimi backup useranno la stessa passphrase."


def recovery_methods(google_available: bool) -> List[Tuple[str, str]]:
    methods = [("passphrase", "Con la passphrase dei backup"), ("code", "Con il codice di recupero")]
    if google_available:
        methods.insert(0, ("google", "Con l'account Google, senza passphrase"))
    return methods


def first_sync_text(result: Optional[Any]) -> str:
    message = getattr(result, "message", "") if result is not None else ""
    return message or "Copia fatta."
