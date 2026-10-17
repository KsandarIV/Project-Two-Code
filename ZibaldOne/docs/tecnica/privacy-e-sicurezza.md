# Privacy, sicurezza e conformità

> Questo documento descrive scelte tecniche. **Non è una consulenza legale.** Prima di distribuire l'app fuori dalla cerchia di amici conviene una verifica con un esperto.

## Principi
1. **Local-first**: tutti i dati restano sul dispositivo dell'utente: su Windows nella cartella dati di ZibaldOne (default `%APPDATA%\ZibaldOne`), su Android nella memoria privata dell'app. L'app non invia nulla a noi.
2. **Trasparenza**: al primo avvio l'app spiega dove salva i dati, quanto spazio usano e quali sono i rischi, e chiede un consenso esplicito. Il comando `zbone privacy` ripete queste informazioni in ogni momento.
3. **Niente telemetria**: nessuna statistica d'uso, nessun crash report automatico. Il feedback dei tester passa da canali scelti da loro.
4. **Controllo dell'utente**: l'utente può vedere, esportare e cancellare tutti i suoi dati con un comando.

## Cosa dice l'avviso al primo avvio (bozza)
> ZibaldOne salva tutto ciò che scrivi solo su questo PC, in `<percorso>`. Nessuno, nemmeno chi ha creato l'app, riceve i tuoi dati. Questo significa anche che **se perdi o rompi il PC senza un backup, perdi i dati**. Puoi attivare un backup o mettere la cartella dentro Google Drive. Continuare? (sì/no)

## Rischi da spiegare all'utente
- Perdita del dispositivo o del disco senza backup.
- Altre persone con accesso al PC possono leggere i file, se non sono cifrati.
- Se la cartella è dentro Google Drive, i dati sono anche sui server di Google, alle condizioni dell'account Google dell'utente.
- Le istantanee conservano anche le voci cancellate finché non scadono (di base fino a circa 12 mesi). Dalla 0.0.6 l'avviso lo dice, e per questo `NOTICE_VERSION` è passato a 2: chi aveva già accettato lo rivede una volta.
- Con le copie su Drive le istantanee cifrate stanno anche sui server di Google; con il recupero con l'account Google, chi entra nell'account può aprirle (avviso versione 3, dalla 0.0.8).
- Le notifiche dei promemoria si vedono anche a schermo bloccato: non contengono mai il testo delle voci, ma rivelano che si usa un diario (avviso versione 4, dalla 0.0.9). Sono calcolate sul dispositivo, senza servizi push.

## Account Google e Drive (dalla 0.0.8)
- **Accesso**: al primo avvio si entra con Google ([ADR-0007](../decisioni/ADR-0007-account-google-e-destinazioni-cloud.md)). L'app riceve solo email e nome e li tiene sul dispositivo; i token stanno in `account-token.json` (DPAPI su Windows). Nessun server nostro: tra l'app e Google non c'è nessuno.
- **Drive**: solo se l'utente lo sceglie, e solo nello spazio nascosto dell'app (`drive.appdata`): l'app non vede gli altri file. Lì vanno solo istantanee **già cifrate** e il file delle chiavi chiuso dalle serrature.
- **Recupero con l'account Google** (facoltativo): mette su Drive un segreto che apre i backup. È comodo, ma rende l'account Google la chiave dei backup; l'app lo spiega prima di attivarlo.
- **Cartella**: in alternativa le copie cifrate vanno in una cartella scelta (chiavetta, OneDrive, Dropbox).
- **Revoca**: `zbone account logout` revoca l'accesso presso Google e cancella i token; le copie su Drive si cancellano con `zbone cloud forget`, o da Drive → Impostazioni → Gestisci app.
- L'avviso del primo avvio è passato alla **versione 3**: spiega l'account e le copie su Drive, quindi chi aveva accettato lo rivede una volta.

## Controllo degli aggiornamenti (dalla 0.1.1)
- Una volta al giorno l'interfaccia chiede a GitHub l'elenco delle versioni, senza account. GitHub vede l'indirizzo IP del dispositivo e la versione dell'app; nessun dato dell'utente parte dal dispositivo.
- Si spegne in Impostazioni → Informazioni o con `zbone update --no-auto`. L'avviso privacy (versione 5) lo dice, quindi chi aveva già accettato lo rilegge una volta.
- La CLI non controlla da sola: solo con `zbone update`.

## Sicurezza tecnica
- **Backup cifrati con storia** ([ADR-0006](../decisioni/ADR-0006-storia-e-backup-cifrati.md)): istantanee che durano un tempo scelto, cifrate sul dispositivo e copiabili fuori; nessuno tranne l'utente può aprirle. Una voce cancellata resta nei backup fino alla loro scadenza, e l'avviso lo deve dire.
- **Cifratura opzionale** dei dati con una passphrase (un diario può contenere salute, opinioni e convinzioni: dati delicati). Se l'utente dimentica la passphrase, i dati non sono recuperabili: va detto chiaramente.
- Scritture atomiche (file temporaneo + rinomina) per non corrompere i dati se il PC si spegne.
- Nessun segreto nel codice o nella repo; `.env` e dati utente esclusi da git.
- Dipendenze minime e controllate (`pip-audit` prima di ogni release).

## Leggi italiane ed europee (orientamento)
- **GDPR**: se i dati restano solo sul PC dell'utente e chi sviluppa non li riceve, lo sviluppatore non li tratta. L'uso personale del proprio diario rientra nell'attività "a carattere esclusivamente personale o domestico". Il quadro cambia se in futuro ci saranno server, account, sincronizzazione gestita da noi o telemetria: allora servono informativa, base giuridica, eventuale DPIA.
- **Categorie particolari** (art. 9 GDPR: salute, convinzioni filosofiche o religiose, opinioni politiche): un diario le contiene spesso. È un motivo in più per cifratura e niente telemetria.
- **Privacy by design e by default** (art. 25 GDPR): le impostazioni predefinite sono le più protettive (tutto locale, nessun invio).
- **Cyber Resilience Act (UE)**: riguarda i prodotti con elementi digitali messi sul mercato nell'ambito di un'attività commerciale; un progetto personale gratuito per amici non dovrebbe rientrarvi. Da rivalutare se l'app diventa un prodotto.
- **AI Act**: non rilevante finché non ci sono funzioni IA; da rivalutare quando arriveranno.
- **Licenza**: scegliere una licenza esplicita prima di dare l'app ai tester (decisione aperta).

## Tester
- Spiegare per iscritto che è una versione di prova e che i dati restano solo sul loro PC.
- Chiedere feedback senza farsi mandare il contenuto dei diari.
