---
tags:
  - studio
  - competenze
date: 2026-10-16
---
# Mappa competenze

Torna a [[00 - START HERE]] · dati da [[Percorso ITS]] e dai progetti.

> [!note] Stima dedotta dalla repo
> Valutazione fatta leggendo codice e appunti, non da un test. Corretta il 2026-10-17 con le indicazioni di Alex.

| Area | Già fatto | Da consolidare |
|---|---|---|
| Python e ingegneria | OOP grande ([[Journal App]]), architettura a moduli e test ([[Nexus Metrics]]), asyncio, FastAPI, pytest + mypy strict, setup multi-macchina ([[Chatbot Ristorante]]) | CI |
| Dati / EDA | pandas, pulizia, report anomalie ([[EDA Personali]]), SQL ([[FakeUni]]) | feature engineering su dati temporali |
| ML classico | Pipeline sklearn, PCA, appunti su supervisionato/non supervisionato | **validazione (CV), metriche, calibrazione, tuning, interpretabilità**: mai portati fino in fondo su un progetto personale |
| Deep Learning | reti neurali, **CNN**, esercitazioni su Fashion-MNIST, digits e computer vision (ITS), CNN starter | applicarlo a **dati propri** (es. sequenze temporali), confronto onesto con baseline classiche |
| GenAI | encoder-decoder, attention/transformer, RAG Lab, agenti con tool calling, **chatbot + voicebot prenotazioni ristorante** ([[Chatbot Ristorante]]): agente LangGraph con tool e SQLite, Ollama gemma4 locale, STT Whisper + TTS Piper, anonimizzazione PII; Alex ha curato voce, LAN, entrypoint e setup | **valutazione** sistematica (set di domande, recall@k, grounding), modelli locali |
| Diritto e AI Act | GDPR, cybersecurity, AI Act (rischio, art. 9-14) dal corso | applicarlo a un progetto: model card, data governance, supervisione umana |
| Visualizzazione | Plotly, Streamlit, tema neon | accessibilità |

Fonti: [[Materiale ITS AIRO2527]] e correzione di Alex del 2026-10-17.

Gap ridimensionato: le competenze ML, DL e GenAI ci sono dal corso. Manca un **progetto personale di portfolio** che le porti su dati propri, con valutazione rigorosa, documentazione (model card / AI Act) e codice testato nel suo stile. È questo il criterio per il prossimo progetto ([[2026-10-16 Brainstorming nuovo progetto]]).
