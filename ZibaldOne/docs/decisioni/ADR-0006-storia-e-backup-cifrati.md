# ADR-0006 — Storia dei dati e backup cifrati, anche fuori dal dispositivo

- **Data**: 2026-10-17 · **Stato**: accettata; istantanee, durata e ripristino nella 0.0.6, cifratura nella 0.0.7 ([dettagli tecnici](../tecnica/backup.md))
- **Contesto**: Alex vuole poter **tornare indietro** come con i commit di git, con backup **cifrati** che **durano un certo tempo** e possono stare **anche fuori** dal dispositivo, senza che nessuno (né lui come sviluppatore né un servizio esterno) possa leggerli.
- **Decisione**:
  - **Istantanee** (*snapshot*): l'app salva periodicamente una copia completa e coerente dei dati (con l'API di backup di SQLite), con data, versione dell'app e `schema_version`. Ogni istantanea è come un commit: si elencano, si confrontano e si ripristinano.
  - **Cifratura obbligatoria** di ogni istantanea, sul dispositivo dell'utente, prima di uscire: AES-256-GCM, libreria `cryptography`, mai un algoritmo scritto da noi. *Implementazione (0.0.7)*: la passphrase (scrypt) non cifra direttamente le istantanee ma protegge una chiave privata X25519 di lungo periodo; ogni istantanea è cifrata con la chiave pubblica, così i backup automatici non chiedono mai la passphrase ([dettagli](../tecnica/backup.md#cifratura--anello-di-gige-dalla-007)).
  - **Nessuno ha accesso**: la chiave non lascia mai il dispositivo e non esiste un server nostro. Chi conserva la copia (Drive, una chiavetta, un altro PC) vede solo file illeggibili. Neanche chi sviluppa l'app può aprirli.
  - **Chiave di recupero**: alla creazione l'app mostra una chiave di recupero da stampare o scrivere. Senza passphrase e senza chiave di recupero i backup **non si possono aprire da nessuno**: va detto chiaramente all'utente.
  - **Recupero** (scelta di Alex, vedi [ADR-0007](ADR-0007-account-google-e-destinazioni-cloud.md)): dipende da dove l'utente tiene i dati.
    1. **locale + Google Drive** → **recupero con account Google**: la chiave dei backup, a sua volta protetta, si salva nello spazio nascosto dell'app sul suo Drive. Comodo, ma chi entra nell'account Google può aprire i backup;
    2. **solo locale** → **codice di recupero**: nessuno tranne l'utente può aprire i backup. Se si perdono passphrase e codice, i backup sono persi.
    Niente recupero via mail con un server nostro: richiederebbe di custodire le chiavi, con costi e obblighi GDPR da titolare del trattamento.
  - **Costi Google (da verificare all'implementazione)**: accesso con Google e API di Drive gratuiti entro i limiti d'uso; i file occupano lo spazio dell'utente. Si usano solo permessi stretti (file creati dall'app, spazio nascosto dell'app) per evitare la valutazione di sicurezza a pagamento richiesta per l'accesso a tutto il Drive; in fase di test bastano fino a 100 tester senza verifica.
  - **Conservazione a tempo** (*retention*), regolabile. Proposta predefinita: le ultime 7 giornaliere, 4 settimanali, 12 mensili; le istantanee più vecchie si cancellano da sole.
  - **Destinazioni**: cartella locale; cartella di Google Drive per desktop su PC; su Android un file da salvare dove si vuole (anche su Drive). In futuro l'API di Drive direttamente.
  - **Ripristino sicuro**: prima di tornare indietro l'app fa un'istantanea dello stato attuale, così anche il ripristino si può annullare. Si può ripristinare tutto o, più avanti, una singola voce.
  - **Integrità**: ogni istantanea ha un'impronta (hash) e la cifratura autenticata rileva file alterati o rotti; `zbone backup verify` lo controlla.
- **Comandi previsti**: `zbone backup create`, `zbone backup list`, `zbone backup restore <id>`, `zbone backup verify`, `zbone backup prune`, `zbone backup config` (destinazione e durata).
- **Conseguenze**:
  - Alla **v0.0.6** istantanee locali, storia, ripristino e conservazione a tempo.
  - Alla **v0.0.7** passphrase, chiave di recupero, cifratura dei backup e copia fuori dal dispositivo.
  - **GDPR**: una voce cancellata resta nei backup fino alla loro scadenza. L'avviso privacy deve dirlo, e la durata della conservazione è anche il tempo massimo in cui un dato cancellato sopravvive. L'utente può cancellare tutti i backup in ogni momento.
  - In futuro si può passare a istantanee **incrementali** con deduplicazione (come restic o borg) se le copie complete diventano troppo pesanti.
- **Alternative scartate**: usare git sul database (non adatto a file binari e non cifrato); un server nostro (contro il local-first e ci renderebbe responsabili dei dati); backup in chiaro su Drive.
