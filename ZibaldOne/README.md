# 📔 ZibaldOne

Un **tutto in uno personale**, componibile e local-first: diario, collezioni, appunti, documenti, finanze e altro, costruiti a blocchi (testo, slider, voti, tag, segnalibri…) come vuoi tu. Per Windows e Android, in futuro Linux. Vedi la [visione](docs/tecnica/visione.md).

> Stato: **v0.0.3**, modelli a blocchi e voci salvate in SQLite. Vedi la [roadmap](docs/tecnica/roadmap.md) e il [CHANGELOG](CHANGELOG.md).

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
Tutto ciò che scrivi resta **sul tuo PC**. Nessun dato viene inviato a noi o a terzi. Dettagli: [privacy e sicurezza](docs/tecnica/privacy-e-sicurezza.md).

## Documentazione
- [docs/](docs/README.md): indice di tutta la documentazione.
