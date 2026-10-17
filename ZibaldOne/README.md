# 📔 ZibaldOne

Un **tutto in uno personale**, componibile e local-first: diario, collezioni, appunti, documenti, finanze e altro, costruiti a blocchi (testo, slider, voti, tag, segnalibri…) come vuoi tu. Per Windows e Android, in futuro Linux. Vedi la [visione](docs/tecnica/visione.md).

> Stato: **v0.0.8**, modelli a blocchi, voci in SQLite, modelli pronti, pacchetti da condividere, storia e backup cifrati, accesso con Google e copie cifrate su Drive o in una cartella. Vedi la [roadmap](docs/tecnica/roadmap.md) e il [CHANGELOG](CHANGELOG.md).

## Avvio rapido (Windows, PowerShell)

```powershell
cd ZibaldOne
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
zibaldone help      # oppure: zbone help
zibaldone version
pytest
```

## Privacy in una riga
Tutto ciò che scrivi resta **sul tuo dispositivo**. Nessun dato viene inviato a noi. I backup si cifrano con `zbone backup setup` e, se lo scegli, vanno cifrati anche sul tuo Google Drive. Dettagli: [privacy e sicurezza](docs/tecnica/privacy-e-sicurezza.md).

## Documentazione
- [docs/](docs/README.md): indice di tutta la documentazione.
