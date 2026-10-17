# Accesso con Google: creare il client OAuth

Per far entrare gli utenti con Google, ZibaldOne ha bisogno di un **client OAuth** di tipo "App desktop". Lo crea una volta sola chi distribuisce l'app (Alex), gratis, nella Google Cloud Console. Finché il client non c'è, ZibaldOne funziona tutto in locale e non chiede l'accesso: è il modo di sviluppare e testare (vedi [ADR-0007](../decisioni/ADR-0007-account-google-e-destinazioni-cloud.md)).

> Costi: nessuno. Un progetto in **modalità test** accetta fino a 100 tester aggiunti per email e non serve la verifica di Google.

## 1. Il progetto
1. Apri [console.cloud.google.com](https://console.cloud.google.com/) con il tuo account Google.
2. In alto, selettore dei progetti → **Nuovo progetto** → nome `ZibaldOne` → Crea.

## 2. L'API di Drive
1. Menu → **API e servizi** → **Libreria**.
2. Cerca **Google Drive API** → **Abilita**.

## 3. La schermata di consenso (Google Auth Platform)
1. Menu → **API e servizi** → **Schermata consenso OAuth** (si apre "Google Auth Platform") → **Inizia**.
2. **Informazioni sull'app**: nome `ZibaldOne`, email di assistenza la tua.
3. **Pubblico**: **Esterno**.
4. **Dati di contatto**: la tua email. Accetta le norme e crea.
5. Sezione **Pubblico** → **Utenti di test** → **Aggiungi utenti**: la tua email e quelle dei 2 amici tester. Solo questi account potranno entrare.
6. Sezione **Accesso ai dati** → **Aggiungi o rimuovi ambiti**, e seleziona:
   - `openid`
   - `.../auth/userinfo.email`
   - `.../auth/userinfo.profile`
   - `.../auth/drive.appdata` (lo spazio nascosto dell'app su Drive: ZibaldOne non vede gli altri file)

   Salva.

## 4. Il client
1. Sezione **Client** → **Crea client**.
2. Tipo di applicazione: **App desktop**. Nome: `ZibaldOne desktop`. Crea.
3. **Scarica JSON**. Il file contiene `{"installed": {"client_id": …, "client_secret": …}}`.

Per Google il `client_secret` di un'app desktop non è un vero segreto, perché sta dentro l'app installata; la protezione vera la dà PKCE, che ZibaldOne usa sempre. Non va comunque messo su GitHub: `.gitignore` lo esclude.

## 5. Dove metterlo
ZibaldOne cerca il client in quest'ordine:

| Dove | Quando usarlo |
|---|---|
| variabile `ZIBALDONE_GOOGLE_CLIENT` con il percorso del JSON | per provare al volo |
| `google-client.json` nella cartella dati (`zbone data path`) | sul tuo PC, per sviluppare |
| `src/zibaldone/cloud/google_client.json` dentro il pacchetto | per le build da dare ai tester (escluso da git) |

## 6. Prova
```powershell
zbone account login     # si apre il browser: scegli l'account, lascia spuntato Drive
zbone account           # chi sei
zbone cloud use google  # le copie cifrate dei backup su Drive
zbone cloud             # come va
```

## Cose da sapere
- In modalità test Google fa **scadere l'accesso dopo circa 7 giorni**. Quando succede ZibaldOne lo dice ("entra di nuovo con `zbone account login`"); diario e backup locali non ne risentono.
- Nella pagina di Google comparirà "Google non ha verificato questa app": è normale in modalità test. I tester cliccano **Continua**.
- Se un tester toglie la spunta su Drive, ZibaldOne funziona lo stesso, ma le copie possono stare solo sul dispositivo o in una cartella.
- Il redirect usa `http://127.0.0.1:<porta>/`, una porta libera scelta ogni volta: con un client "App desktop" non serve registrarlo.
- **Android: da verificare sul telefono.** Il flusso con il browser e il ritorno su 127.0.0.1 funziona sul PC. Su Android l'app deve restare viva mentre il browser è aperto; se non basta, alla 0.1.1 si passa a un client "Android" con la firma dell'APK.
- Per togliere l'accesso a ZibaldOne: [myaccount.google.com/permissions](https://myaccount.google.com/permissions). `zbone account logout` lo revoca già da solo.
