"""Privacy notice shown at first start and by `zbone privacy`.

Changing the text in a way that matters to the user means raising
NOTICE_VERSION, so everyone is asked again. A change that only lowers a
risk (like 0.0.7 saying that backups can now be encrypted) keeps it.
"""

from pathlib import Path
from typing import List

NOTICE_VERSION = 2

RISKS: List[str] = [
    "Se perdi o rompi il dispositivo senza un backup, perdi i dati.",
    "Chi usa questo dispositivo con il tuo account può leggere il database, che resta in chiaro. "
    "Le istantanee (backup) sono cifrate dopo `zbone backup setup`.",
    "Se metti la cartella dentro Google Drive, i dati stanno anche sui server di Google, "
    "alle condizioni del tuo account Google.",
    "Le istantanee (backup) conservano anche le voci che cancelli finché non scadono: "
    "con la durata predefinita fino a circa 12 mesi. Puoi accorciarla con `zbone backup config`.",
]


def notice_text(folder: Path) -> str:
    """Return the full notice for the given data folder."""
    risks = "\n".join(f"  - {risk}" for risk in RISKS)
    return (
        "ZibaldOne salva ciò che scrivi solo su questo dispositivo, nella cartella:\n"
        f"  {folder}\n\n"
        "Nessuno, nemmeno chi ha creato l'app, riceve i tuoi dati. "
        "L'app non invia statistiche né segnalazioni automatiche.\n\n"
        f"Rischi:\n{risks}\n\n"
        "Puoi rileggere queste informazioni quando vuoi con `zbone privacy`."
    )
