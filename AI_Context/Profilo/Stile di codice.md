---
tags:
  - profilo
  - stile
date: 2026-10-16
---
# Stile di codice

Torna a [[00 - START HERE]] · vedi anche [[Design e palette]], [[Python Starter Kit]].

## Python
- **Nomi espliciti e di dominio**, lunghi se serve: `load_daily_journal_from_json_file`, `calculate_recreation_item_progress_percentage`, `dataset_quality_report`.
- **Type hint** sulle funzioni pubbliche (`typing.Dict`, `List`, `Optional`, `Tuple`), `@dataclass` per i risultati (es. `ClassificationResult`).
- Costanti in MAIUSCOLO a livello di modulo (`CYBER_PALETTE`, `BACKGROUND_COLOR`, `STOP_BOT`).
- Funzioni piccole e coese; moduli separati per responsabilità (Clean Architecture leggera): `clients/`, `core/`, `extractors/`, `analytics/`, `services/`, `visualization/`.
- Codice, commenti, docstring, log in **inglese**; documentazione e conversazione in italiano. Nei laboratori ITS il codice è a volte in italiano (`costruisci_prompt_aumentato`): nei progetti personali vale l'inglese.
- Commenti **pochi** e rivolti allo sviluppatore. Tag *Better Comments* per note azionabili: `# * — API boundary —`, `# ! attenzione`, `# ? dubbio`, `# TODO`. Separatori con trattino lungo, mai righe di `#` o `-` decorative.
- scikit-learn sempre con `Pipeline` + `ColumnTransformer` per evitare leakage; `random_state=42`; split stratificato quando possibile.
- Errori espliciti con `ValueError` e messaggi chiari; niente falsi messaggi di successo.

## Test e struttura
- Test **offline e deterministici** con `unittest` (`python -m unittest discover -s tests -v`), HTTP mockato, nessuna chiave richiesta.
- I notebook sono per esplorare; quando la logica è stabile si sposta in `src/` con test.
- Segreti in `.env` (escluso da Git) con `.env.example` senza valori reali.
- Dipendenze minime, spiegate prima di aggiungerle; `requirements.txt` per progetto.

## Documentazione di progetto
Ogni progetto serio ha: `README.md` (stato attuale verificato), una roadmap con milestone a checkbox, un file per agenti AI, e una *Definition of Done*. Le emoji nei titoli dei documenti sono gradite (📔, 📊, 🚀, 📋).
