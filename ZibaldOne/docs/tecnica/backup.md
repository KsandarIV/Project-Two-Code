# Storia e backup (Mnemosyne)

Come funzionano le istantanee di ZibaldOne ([ADR-0006](../decisioni/ADR-0006-storia-e-backup-cifrati.md)). Il codice è in `src/zibaldone/storage/backups.py`, i comandi in `src/zibaldone/cli/backup_cmd.py`.

## Le istantanee
- Un'**istantanea** è una copia completa e coerente dei dati, come un commit di git. Si crea a mano (`zbone backup create`) o da sola una volta al giorno, dopo un comando che ha salvato qualcosa.
- Ogni istantanea è un file in `backups/` dentro la cartella dati, con il nome dell'ora in UTC: `20261017T112233Z-a1b2c3.zbsnap`. Le ultime 6 cifre bastano per indicarla nei comandi.
- Dentro c'è uno zip con:
  - `manifest.json`: id, ora, versione dell'app, versione dello schema, motivo (manuale, automatica, prima di un ripristino, prima di un aggiornamento), nota, impronta SHA-256 e dimensione del database, numero di voci e modelli;
  - `zibaldone.db`: la copia fatta con l'API di backup di SQLite, coerente anche se l'app sta scrivendo;
  - `settings.json`: una copia delle impostazioni, per consultarla.
- Prima che un aggiornamento dell'app cambi lo schema del database, ZibaldOne salva un'istantanea "prima di un aggiornamento".

## Ripristino
- `zbone backup restore ID` riporta modelli e voci com'erano. Prima controlla tutta l'istantanea, poi salva lo stato attuale come istantanea "prima di un ripristino", poi sostituisce il file in un colpo solo. Il comando stampa come annullare.
- Restano come sono adesso `settings.json` e (dalla 0.0.7) `keys.json`: un'istantanea vecchia non deve revocare un consenso, cambiare la durata dei backup (cancellerebbe istantanee) o riportare una vecchia passphrase.
- ZibaldOne deve essere chiuso nelle altre finestre: un database in uso viene rilevato e il ripristino si ferma con un messaggio.

## Durata (retention)
Come `restic forget`: per ogni regola si tiene l'istantanea più recente di ognuno degli ultimi N giorni, settimane e mesi che ne hanno una. Di base **7 giornaliere, 4 settimanali, 12 mensili**: un dato cancellato può sopravvivere nei backup fino a circa 12 mesi, e l'avviso privacy lo dice. Si tengono sempre l'istantanea più recente e l'ultima "prima di un ripristino".

```powershell
zbone backup config                                   # mostra le impostazioni
zbone backup config --days 3 --weeks 2 --months 3     # durata più corta
zbone backup config --no-auto                         # niente istantanee automatiche
zbone backup config --interval 12                     # automatica ogni 12 ore
zbone backup prune --dry-run                          # cosa cancellerebbe
```

## Verifica
`zbone backup verify` controlla l'ultima istantanea (`--all` tutte, oppure un ID): zip integro, impronta SHA-256, `PRAGMA integrity_check` di SQLite e versione dello schema.

## Export
`zbone export markdown` crea uno zip con un file Markdown per voce, da aprire in Obsidian; `zbone export csv` uno zip con un CSV per modello. Il codice è in `src/zibaldone/storage/export.py`. Gli export **non sono cifrati**: il comando lo ricorda.
