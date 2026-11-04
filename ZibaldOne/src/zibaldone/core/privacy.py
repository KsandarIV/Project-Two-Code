"""Privacy notice shown at first start and by `zbone privacy`.

Changing the text in a way that matters to the user means raising
NOTICE_VERSION, so everyone is asked again. A change that only lowers a
risk (like 0.0.7 saying that backups can now be encrypted) keeps it.
Version 3 (0.0.8): the Google account and the copies on Drive.
Version 4 (0.0.9): reminders on the lock screen.
Version 5 (0.1.1): the daily check for a new version on GitHub.
Version 6 (0.3.1): backups kept longer (up to about 3 years), the Google account is optional.
Version 7 (KAN-29): backup files encrypted in full by the main password, the backup folder is visible to other
apps, the recovery sheet, no more recovery through Google. The encrypted database (KAN-107) only lowers a risk, so
it keeps version 7.
"""

from pathlib import Path
from typing import List

NOTICE_VERSION = 7

RISKS: List[str] = [
    "Se perdi o rompi il dispositivo senza un backup, perdi i dati.",
    "Il diario è cifrato su questo dispositivo, gli allegati (foto e documenti) per ora no: "
    "chi riesce a entrare nella cartella dell'app può aprirli.",
    "Se perdi sia la password principale sia il codice di recupero, i backup non si aprono più: nemmeno chi ha creato l'app può aiutarti.",
    "Chi ha il foglio di recupero, o la password, può aprire i tuoi backup: tienilo su carta, lontano dal telefono.",
    "Se in passato hai attivato il recupero con l'account Google, chi riesce a entrare nel tuo account Google può aprire i backup: "
    "puoi toglierlo nelle Nuvole. Non viene più proposto.",
    "La cartella dei backup la vedono anche le altre app con accesso ai file e un PC collegato col cavo: vedono i file, non il contenuto.",
    "Se metti la cartella dei backup o quella dei dati dentro una cartella sincronizzata (Google Drive, OneDrive…), "
    "i file stanno anche sui server di quel servizio: i backup e il diario restano illeggibili, gli allegati no.",
    "Le notifiche dei promemoria si vedono anche a schermo bloccato: non contengono mai ciò che scrivi, "
    "ma dicono che usi un diario. Sono calcolate su questo dispositivo, senza servizi esterni.",
    "I backup conservano anche le voci che cancelli finché non vengono sostituiti. "
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
        "Dove stanno i tuoi dati\n"
        "Quello che scrivi sta in una cartella privata dell'app, su questo dispositivo, cifrato: la chiave la custodisce "
        "il sistema e, se si perde, la ritrovi con la password principale.\n\n"
        "I backup\n"
        "I backup sono file .zbbackup nella cartella che scegli tu, con nomi a caso. Ognuno è cifrato per intero "
        "con la password principale, che crea ZibaldOne: chi apre il file non legge nulla, nemmeno la data o la versione. "
        "Si apre solo con la password o con il codice di recupero. Anche le istantanee dentro l'app sono cifrate.\n\n"
        "Cosa esce dal dispositivo\n"
        "Niente, finché non lo decidi tu. Se scegli di accedere con il tuo account Google (non è obbligatorio), ZibaldOne riceve solo email e nome, "
        "e li tiene su questo dispositivo. Su Google Drive vede solo il suo spazio nascosto, "
        "mai gli altri tuoi file, e ci mette copie cifrate solo se lo scegli tu.\n\n"
        "Una volta al giorno l'app chiede a GitHub se c'è una versione nuova: GitHub vede "
        "l'indirizzo IP del dispositivo e la versione dell'app, nient'altro. Si spegne in Impostazioni · Informazioni "
        "o con `zbone update --no-auto`.\n\n"
        f"Rischi:\n{risks}\n\n"
        "Puoi rileggere queste informazioni quando vuoi con `zbone privacy`."
    )
