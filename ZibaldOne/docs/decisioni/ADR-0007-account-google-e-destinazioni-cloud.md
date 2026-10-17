# ADR-0007 — Accesso con Google e destinazioni cloud

- **Data**: 2026-10-17 · **Stato**: accettata (scelta di Alex)
- **Contesto**: i primi tester sono Alex e 2 amici, su Android e Windows. Alex vuole un accesso unico e semplice, con la libertà di tenere i dati solo in locale.
- **Decisione**:
  - Al primo avvio l'accesso con **account Google è obbligatorio**. L'app non ha un server suo: l'accesso serve per identificare l'utente sul dispositivo e per usare il suo Google Drive. L'app conserva in locale solo il necessario (email e token d'accesso, protetti dal sistema operativo).
  - Dopo l'accesso l'utente sceglie dove stanno i dati, e può cambiare idea quando vuole:
    1. **solo locale**: dati e backup restano sul dispositivo; il recupero usa il **codice di recupero**;
    2. **locale + Google Drive**: i backup cifrati vanno anche sul suo Drive; il recupero usa l'**account Google** (vedi [ADR-0006](ADR-0006-storia-e-backup-cifrati.md)).
  - **Destinazioni intercambiabili**: per l'app un cloud è solo un posto dove mettere e riprendere file cifrati (`carica`, `scarica`, `elenca`, `cancella`). Google Drive è la prima destinazione; in futuro altre (OneDrive, Dropbox, WebDAV/Nextcloud, una cartella qualsiasi) configurate dall'utente, senza toccare il resto dell'app.
  - Permessi Google stretti: solo i file creati dall'app e lo spazio nascosto dell'app, mai tutto il Drive.
- **Conseguenze**:
  - Il primo avvio richiede internet per l'accesso; dopo, l'app funziona anche offline.
  - Con pochi tester il progetto Google resta in **modalità test** (gratuita, fino a 100 tester aggiunti per email). In modalità test Google fa scadere l'accesso dopo circa 7 giorni, quindi i tester dovranno rientrare ogni tanto finché l'app non è verificata.
  - Privacy: l'avviso del primo avvio deve dire che l'accesso Google serve solo sul dispositivo e che nessun dato arriva a chi sviluppa. Minimizzazione: si chiedono solo email e i permessi di Drive indicati sopra.
  - Fino alla 0.0.7 la CLI funziona in locale senza accesso. L'accesso con Google arriva alla **0.0.8** insieme al cloud, e da lì è obbligatorio al primo avvio nelle copie che hanno un client Google configurato ([come crearlo](../sviluppo/google-cloud.md)); senza client l'app resta solo locale, per sviluppare e testare.
- **Come è stata realizzata (0.0.8)**:
  - Ambiti: `openid`, `email`, `profile` e `drive.appdata`, cioè lo spazio nascosto dell'app su Drive: ancora più stretto dei "file creati dall'app".
  - Tre modalità invece di due: solo locale, locale + Google Drive, locale + una **cartella** (chiavetta, OneDrive, Dropbox…), che è già la prima "destinazione configurata dall'utente".
  - Il recupero con l'account Google è **proposto** quando si sceglie Drive, con il compromesso spiegato (chi entra nell'account può aprire i backup), e si può togliere. Chi non lo attiva recupera con passphrase o codice di recupero.
  - L'accesso è obbligatorio per usare il diario, non per riavere i propri dati: backup, export e privacy funzionano sempre, anche senza account.
  - Fuori dal dispositivo escono solo istantanee cifrate; nessuna copia remota viene cancellata perché manca sul dispositivo.
- **Alternative scartate**: accesso facoltativo (più privato ma Alex vuole un'esperienza unica); account con email e password su un server nostro (costi e obblighi GDPR).
