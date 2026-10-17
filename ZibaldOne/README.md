# 📔 ZibaldOne

Un **tutto in uno personale**, componibile e local-first: diario, collezioni, appunti, documenti, finanze e altro, costruiti a blocchi (testo, slider, voti, tag, segnalibri…) come vuoi tu. Per Windows e Android, in futuro Linux. Vedi la [visione](docs/tecnica/visione.md).

> Stato: **v0.1.5**, la fase 0.1 completa: ricerca, collegamenti, grafo, statistiche e revisioni delle voci, anonimizzatore per le future funzioni di IA, sopra la prima versione per i tester: interfaccia grafica per Windows e Android (APK nelle [release](https://github.com/KsandarIV/Project-Two-Code/releases)), modelli a blocchi, voci, modelli pronti, pacchetti da condividere, backup cifrati, accesso con Google e copie su Drive, promemoria per scrivere, avviso quando esce una versione nuova. Vedi la [roadmap](docs/tecnica/roadmap.md) e il [CHANGELOG](CHANGELOG.md).

## Avvio rapido (Windows, PowerShell)

```powershell
cd ZibaldOne
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,ui]"
zbone app           # l'app, in una finestra (oppure: zbone app --web, nel browser)
zbone help          # i comandi del terminale (zbone è l'alias corto di zibaldone)
pytest
```

| Sul PC | Sul telefono |
|---|---|
| ![Oggi, sul PC](docs/immagini/oggi-pc.png) | ![La voce della sera, sul telefono](docs/immagini/sera-telefono.png) |

## Privacy in una riga
Tutto ciò che scrivi resta **sul tuo dispositivo**. Nessun dato viene inviato a noi. I backup si cifrano con `zbone backup setup` e, se lo scegli, vanno cifrati anche sul tuo Google Drive. Dettagli: [privacy e sicurezza](docs/tecnica/privacy-e-sicurezza.md).

## Documentazione
- [docs/](docs/README.md): indice di tutta la documentazione.
- [Guida per i tester](docs/utente/guida-tester.md): installare l'APK su Android e aggiornarlo.
- [Rilascio Android](docs/sviluppo/rilascio-android.md): come esce un APK.
