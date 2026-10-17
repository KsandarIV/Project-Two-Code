# Architettura

## Concetti
- **Blocco**: un tipo di campo con regole; 12 tipi, da `text` a `link` ([blocchi](blocchi.md)).
- **Modello**: una ricetta dell'utente, cioè una lista ordinata di blocchi con nome (es. "Libro").
- **Voce**: un'istanza di un modello con i valori compilati.
- **Pacchetto**: un file `.zbpack.json` con uno o più modelli, da condividere o importare; contiene solo struttura, mai voci ([ADR-0005](../decisioni/ADR-0005-pacchetti-di-modelli.md)).

Aggiungere un tipo nuovo non richiede codice: un modello è un dato, e quindi si può esportare e condividere.

## Moduli
```
src/zibaldone/
  core/      dominio: blocchi, modelli, voci, validazione (nessuna dipendenza esterna)
  storage/   persistenza nella cartella dati dell'utente (dalla v0.0.2)
  cli/       comandi Typer: zibaldone / zbone
  cloud/     account Google, destinazioni e copie dei backup (dalla v0.0.8)
  ui/        interfaccia grafica (dalla v0.0.9), sopra gli stessi moduli
  ai/        funzioni IA (rinviate: si definiranno molto più avanti)
```
Regola: `cli/` e `ui/` chiamano `core/` e `storage/`, mai il contrario.

## Moduli funzionali
Diario, Collezioni, Documenti, Finanze, Password, Grafo, Raccomandazioni: ognuno sarà un sottopacchetto in `src/zibaldone/modules/` che usa solo il cuore. Dettagli in [visione](visione.md).

## Dati (dalla 0.0.3)
- Un file SQLite, `zibaldone.db`, nella cartella dati. Due tabelle: `templates` (chiave `slug`, il modello in JSON) e `entries` (id di 32 caratteri esadecimali, modello, giorno, valori in JSON, date di creazione e modifica).
- Modelli e voci sono salvati come JSON perché ogni modello ha blocchi diversi: niente colonne da aggiungere quando l'utente inventa un modello nuovo.
- Non si può eliminare un modello che ha voci (chiave esterna `RESTRICT`).
- **Migrazioni**: una lista in `storage/database.py` che si può solo allungare; la versione dello schema è in `PRAGMA user_version`. Un database più nuovo dell'app viene rifiutato invece di rovinarlo.
- `core/templates.py` definisce `BlockSpec`, `Template` ed `Entry`; tutti si trasformano in JSON e ritorno senza perdere nulla, e rifiutano i campi sconosciuti.

## Backup (dalla 0.0.6)
- Istantanee complete in `backups/` nella cartella dati, una al giorno in automatico dopo un comando che salva dati, più quelle a mano. `cli/common.open_store()` le avvia: prima di un aggiornamento dello schema e dopo un comando che ha cambiato qualcosa.
- Formato, durata e ripristino: [storia e backup](backup.md).

## Account e cloud (dalla 0.0.8)
- `cloud/` non dipende dalla CLI: `account.py` (account e modalità in `settings.json`), `google_auth.py` (OAuth con PKCE), `tokens.py`, `destinations.py`, `sync.py`. L'HTTP passa da `cloud/http.py` (solo libreria standard), che nei test si sostituisce con un finto Google.
- `cli/common.open_store()` chiede l'accesso al primo avvio, quando un client Google è configurato; dopo un backup automatico avvia la copia sulla destinazione scelta. Backup, export e privacy non chiedono l'accesso.
- Dettagli: [copie fuori dal dispositivo](backup.md#copie-fuori-dal-dispositivo--le-nuvole-dalla-008).
