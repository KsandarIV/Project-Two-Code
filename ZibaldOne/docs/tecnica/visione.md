# Visione di ZibaldOne

ZibaldOne **non è solo un diario**: è un **tutto in uno personale** dove tenere ciò che serve di sé, costruito a blocchi e diviso in moduli indipendenti.

## Piattaforme
- **Windows** e **Android** da subito, **Linux** in futuro. Alex lo userà sia da PC sia da telefono.
- Gli **stessi dati** devono essere accessibili dal PC e dal telefono (vedi "Sincronizzazione").

## Moduli previsti
Ogni modulo è un pacchetto separato sopra lo stesso cuore (blocchi, modelli, voci, salvataggio). Un modulo si può attivare o disattivare.

| Modulo | Cosa fa | Delicatezza dei dati |
|---|---|---|
| **Diario** | pagine del giorno, riflessioni, umore, checkpoint | alta |
| **Collezioni** | libri, film, serie, giochi, canzoni con blocchi a scelta | bassa |
| **Appunti e idee** | pensieri, testi, pezzi di canzoni | media |
| **Documenti e carte** | copie di documenti, tessere, carte | **molto alta** |
| **Portafoglio e finanze** | spese, entrate, budget, conti | **molto alta** |
| **Password** | integrazione con un gestore come **Bitwarden** | **critica** |
| **Grafo** | vista a grafo stile Obsidian dei collegamenti tra voci | segue i dati collegati |
| **Raccomandazioni** | consigli di lettura (e altro) basati su ciò che hai letto **e** sulle tue riflessioni su cosa ti è piaciuto | segue i dati usati |

## Configurazioni condivisibili
Una configurazione di blocchi (uno o più modelli) si salva in un **pacchetto**, un file da passare ad altri. Le fonti sono tre: i modelli pronti forniti dall'app, quelli creati e condivisi dagli utenti e, in futuro, quelli che l'app ti consiglia. Un pacchetto contiene solo la struttura, mai i tuoi dati, ed è solo dati, mai codice. Dettagli in [ADR-0005](../decisioni/ADR-0005-pacchetti-di-modelli.md).

## Tornare indietro
I dati hanno una **storia**, come i commit di git: l'app salva istantanee cifrate che durano un tempo scelto e possono stare anche fuori dal dispositivo, leggibili solo dall'utente. Dettagli in [ADR-0006](../decisioni/ADR-0006-storia-e-backup-cifrati.md).

## Principi di codice
- **Agile**: incrementi piccoli, una capacità per versione, criteri di accettazione e test.
- **Compartimentazione**: ogni modulo ha i suoi dati, i suoi test e la sua documentazione; i moduli parlano tra loro solo attraverso il cuore (per esempio il grafo e le raccomandazioni *leggono* le voci, non entrano nei moduli).
- **Scalabilità**: aggiungere un modulo non deve richiedere modifiche agli altri.

## Note di sicurezza sui moduli delicati
- **Password**: scrivere da zero un gestore di password sicuro è difficile e rischioso. La strada consigliata è **integrarsi con Bitwarden** (per esempio link alle voci o lettura tramite la sua CLI ufficiale), non duplicarne le funzioni. Da decidere quando si arriverà al modulo.
- **Documenti, carte, finanze**: cifratura **obbligatoria** per questi moduli (non opzionale), blocco con PIN o biometria su Android, nessun dato in chiaro nei backup.
- Questi moduli alzano il livello di responsabilità: vedi [privacy e sicurezza](privacy-e-sicurezza.md).

## Sincronizzazione PC ↔ telefono (da progettare)
Vincolo: niente server nostro (local-first, nessun dato inviato a noi). Strade possibili:
1. **Archivio cifrato su Google Drive dell'utente**: ogni dispositivo ha i suoi dati locali e sincronizza un file cifrato sul Drive personale. I dati su Drive sono illeggibili senza la passphrase.
2. **Sincronizzazione diretta tra dispositivi** sulla stessa rete (stile Syncthing).
3. **Export/import manuale** come soluzione minima iniziale.
Proposta: partire dalla 3, progettare la 1. La scelta va in un ADR quando ci si arriva.

## Raccomandazioni (futuro)
Esempio: consigli di lettura che usano i libri letti, i voti **e** le riflessioni scritte su cosa è piaciuto (temi, stile, idee). È un sistema di raccomandazione ibrido (contenuto + testo delle riflessioni). Rientra nella parte IA, rinviata.
