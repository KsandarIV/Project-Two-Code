---
tags:
  - progetto
  - ml
  - genai
stato: attivo — MVP analytics e dashboard completati
percorso: Personal Projects/LoL/Nexus_Metrics
date: 2026-10-16
---
# Nexus Metrics

Torna a [[00 - START HERE]] · stile in [[Stile di codice]] · palette in [[Design e palette]].

> [!abstract] In breve
> Progetto local-first per raccogliere e analizzare la propria storia di partite di League of Legends via Riot Match-V5. È il progetto più maturo della repo.

## Stato al 2026-10-10 (da `project_roadmap.md`)
- 926 partite scaricate (dettagli + timeline), 2025-11-08 → 2026-10-09; ~799 MB di JSON, quasi tutto timeline.
- Ingestion incrementale con rate limiter, ledger degli ID, `--full-rescan`.
- `analyze.py` esporta `matches.csv` + riepiloghi per mese, patch, campione, ruolo, coda.
- Dashboard Streamlit neon, sync Riot solo su richiesta.
- 29 test offline passano (Conda Python 3.10.22). Bilancio: 462 V / 464 S.

## File di contesto del progetto
`AGENTS.md`, `AI_WORKING_AGREEMENT.md`, `project_roadmap.md` (canonici). `TODO.ipynb` è storico.

## Milestone aperte rilevanti per lo studio
- Qualità metriche (normalizzazione CS, ruoli sconosciuti).
- **5. Local ML e RAG**: definire una domanda ML concreta; RAG locale con Ollama, retrieval valutato separatamente dalla generazione.

## Collegamenti
- Esiste anche un notebook su dataset Kaggle `high_diamond_ranked_10min` (cartella `LoL/`): predizione vittoria dai primi 10 minuti.
- Candidato per [[2026-10-16 Brainstorming nuovo progetto]] (opzioni 1 e 2).
