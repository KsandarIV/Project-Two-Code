# Rilascio Android: l'APK per i tester

Da ZibaldOne 0.1.1 ogni tag `zibaldone-vX.Y.Z` mandato su GitHub fa partire un lavoro di GitHub Actions (`.github/workflows/zibaldone-apk.yml`, nella radice della repo) che:

1. installa ZibaldOne e fa girare i test;
2. calcola il numero di build per Android dalla versione (`0.1.1` → `1001`, `0.1.5` → `1005`, `1.2.3` → `1002003`): deve sempre crescere, altrimenti Android rifiuta l'aggiornamento;
3. aggiunge il client OAuth di Google e la chiave di firma, presi dai segreti della repo;
4. costruisce l'APK con `flet build apk` (Flutter e Android SDK li scarica da solo);
5. crea la release con quel tag, segnata come *pre-release*, con la nota `docs/versioni/vX.Y.Z.md` e l'APK `ZibaldOne-X.Y.Z.apk` allegato.

L'app (dalla 0.1.1) legge proprio queste release per dire ai tester che c'è una versione nuova ([ADR-0003](../decisioni/ADR-0003-distribuzione-e-aggiornamenti.md)).

## Una volta sola: la chiave di firma
Android accetta un aggiornamento solo se è firmato con **la stessa chiave** della versione installata. Senza chiave, il workflow firma con una chiave di prova che cambia a ogni build, e i tester dovrebbero disinstallare (perdendo i dati) a ogni versione.

Serve Java (il JDK 17 va bene). In PowerShell:
```powershell
keytool -genkeypair -v -keystore zibaldone.jks -alias zibaldone -keyalg RSA -keysize 2048 -validity 10000
```
Scegli una password lunga e rispondi alle domande (basta il nome). **Conserva `zibaldone.jks` e la password fuori dalla repo** (per esempio nel gestore di password): se li perdi, nessun telefono potrà più aggiornare l'app senza disinstallarla.

Poi trasformala in testo per GitHub:
```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("zibaldone.jks")) | Set-Clipboard
```

## Una volta sola: i segreti della repo
Su GitHub: **Settings → Secrets and variables → Actions → New repository secret**.

| Segreto | Cosa contiene | Obbligatorio |
| --- | --- | --- |
| `ANDROID_KEYSTORE_BASE64` | il testo copiato sopra | sì, per aggiornare senza disinstallare |
| `ANDROID_KEYSTORE_PASSWORD` | la password della chiave | sì, con la chiave |
| `ANDROID_KEY_PASSWORD` | la password dell'alias, se diversa | no (usa la precedente) |
| `ANDROID_KEY_ALIAS` | l'alias, se non è `zibaldone` | no |
| `GOOGLE_CLIENT_JSON` | il contenuto del file del client OAuth "App desktop" ([google-cloud](google-cloud.md)) | sì, per entrare con Google |

Il file del client non va mai nella repo (è in `.gitignore`): il workflow lo scrive solo durante la build.

## La repo deve essere pubblica
I tester scaricano l'APK dalla pagina delle release e l'app controlla gli aggiornamenti senza account: entrambe le cose funzionano solo se la repo è **pubblica**. Con una repo privata la build parte lo stesso, ma l'APK si scarica solo da GitHub con un account che ha accesso, e il controllo degli aggiornamenti risponde "il repository è privato?".

## Fare uscire una versione
Il commit della versione e il tag li prepara Claude (o `scripts/release.py`). Poi, dal PC:
```powershell
cd C:\Users\okami\Desktop\ProjectTwoCode\Project-Two-Code
git push origin main --follow-tags
```

**Attenzione: GitHub non fa partire nulla se si mandano più di tre tag insieme.** Se il push porta tante versioni in un colpo (come la prima volta, dalla 0.0.1 alla 0.1.5), avvia la build a mano per l'ultima:

- da GitHub: **Actions → ZibaldOne APK → Run workflow**, scrivi il tag (es. `zibaldone-v0.1.5`) e conferma;
- oppure, con la CLI di GitHub: `gh workflow run zibaldone-apk.yml -f tag=zibaldone-v0.1.5`.

Il workflow controlla che il tag corrisponda alla versione nel codice. Lanciato senza tag costruisce l'APK del branch scelto e lo lascia tra gli *artifacts* del lavoro, senza release: utile per una prova.

Le versioni senza APK (prima della 0.1.1) non hanno bisogno di release.

## Cosa c'è dentro l'APK
Verificato con `flet build` 1.0.4 (la build completa non è stata provata fuori da GitHub, perché scarica l'Android SDK da Google):
- tutte le chiavi di `[tool.flet]` sono lette; `[tool.flet.android].dependencies` si **aggiunge** a `[project].dependencies`, quindi nel telefono ci sono typer, cryptography e flet 1.0.4;
- sul telefono gira **Python 3.14** (Flet sceglie la versione più recente compatibile con `requires-python`); cryptography, cffi e msgpack per Android arrivano dall'indice di Flet (`pypi.flet.dev`), tutto il resto da PyPI;
- i pacchetti di modelli e `google_client.json` si leggono con `importlib.resources`, quindi funzionano anche dentro l'APK;
- il permesso INTERNET c'è già di base; le notifiche di sistema su Android non sono incluse (i promemoria compaiono dentro l'app).

## Se qualcosa va storto
- **Test rossi**: la build si ferma prima di costruire. Si sistemano, nuova versione, nuovo tag.
- **Tag sbagliato** o build fallita a metà: si rilancia a mano con lo stesso tag; se la release esiste già, l'APK viene sostituito.
- **Il telefono rifiuta l'aggiornamento** ("app non installata"): la firma è diversa (manca o è cambiata la chiave) o il numero di build non è cresciuto.

## Da fare più avanti
- Build per Windows (`flet build windows`) allegata alla stessa release.
- Google Play, traccia di test interno: aggiornamenti automatici per i tester, ma serve un account sviluppatore (25 $ una tantum).
