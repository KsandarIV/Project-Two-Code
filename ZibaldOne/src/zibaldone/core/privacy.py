"""Privacy notice shown at first start and by `zbone privacy`.

Changing the text in a way that matters to the user means raising
NOTICE_VERSION, so everyone is asked again. A change that only lowers a
risk (like 0.0.7 saying that backups can now be encrypted) keeps it.
Version 3 (0.0.8): the Google account and the copies on Drive.
Version 4 (0.0.9): reminders on the lock screen.
Version 5 (0.1.1): the daily check for a new version on GitHub.
Version 6 (0.3.1): backups kept longer (up to about 3 years), the Google account is optional.
"""

from pathlib import Path
from typing import List

NOTICE_VERSION = 6

RISKS: List[str] = [
    "Se perdi o rompi il dispositivo senza un backup, perdi i dati.",
    "Chi usa questo dispositivo con il tuo account può leggere il database, che resta in chiaro. "
    "Le istantanee (backup) sono cifrate dopo `zbone backup setup`.",
    "Se scegli le copie su Google Drive, le istantanee cifrate stanno anche sui server di Google. "
    "Senza passphrase o codice di recupero non si aprono; se attivi il recupero con l'account Google, "
    "chi riesce a entrare nel tuo account Google può aprirle.",
    "Se metti la cartella dati dentro una cartella sincronizzata (Google Drive, OneDrive…), "
    "il database in chiaro sta anche sui server di quel servizio.",
    "Le notifiche dei promemoria si vedono anche a schermo bloccato: non contengono mai ciò che scrivi, "
    "ma dicono che usi un diario. Sono calcolate su questo dispositivo, senza servizi esterni.",
    "Le istantanee (backup) conservano anche le voci che cancelli finché non vengono sostituite. "
    "Con il backup automatico, di base, restano la copia di oggi, 4 della settimana, 3 del mese e 3 dell'anno: "
    "una voce cancellata può quindi restare nei backup fino a circa 3 anni. "
    "Con il backup manuale decidi tu: le copie stanno nella cartella dei backup e si possono cancellare.",
]


def notice_text(folder: Path) -> str:
    """Return the full notice. `folder` is kept for the callers: the path is no longer written in the text (0.3.3)."""
    risks = "\n".join(f"  - {risk}" for risk in RISKS)
    return (
        "ZibaldOne salva ciò che scrivi solo su questo dispositivo.\n\n"
        "Nessuno, nemmeno chi ha creato l'app, riceve i tuoi dati. "
        "L'app non invia statistiche né segnalazioni automatiche.\n\n"
        "Se scegli di accedere con il tuo account Google (non è obbligatorio), ZibaldOne riceve solo email e nome, "
        "e li tiene su questo dispositivo. Su Google Drive vede solo il suo spazio nascosto, "
        "mai gli altri tuoi file, e ci mette copie cifrate solo se lo scegli tu.\n\n"
        "Una volta al giorno l'app chiede a GitHub se c'è una versione nuova: GitHub vede "
        "l'indirizzo IP del dispositivo e la versione dell'app, nient'altro. Si spegne in Impostazioni · Informazioni "
        "o con `zbone update --no-auto`.\n\n"
        f"Rischi:\n{risks}\n\n"
        "Puoi rileggere queste informazioni quando vuoi con `zbone privacy`."
    )
