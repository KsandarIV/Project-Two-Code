---
tags:
  - log
date: 2026-10-16
---
# Registro lavoro

Torna a [[00 - START HERE]] · formato in [[Template sessione]].

Voci più recenti in alto.

## 2026-10-17 — v0.2.0 cartella dati e avviso privacy
- **Fatto**: su ok di Alex scritta la v0.2: `storage/paths.py` (cartella dati per piattaforma, `ZIBALDONE_HOME`), `storage/settings.py` (`settings.json` atomico con `schema_version` e consenso), `core/privacy.py` (avviso in italiano, `NOTICE_VERSION`), comandi `privacy`, `privacy accept/revoke`, `data path`; `ensure_consent()` all'inizio di ogni comando che usa i dati. 18 test passano (venv di prova). Versione 0.2.0, CHANGELOG, `docs/versioni/v0.2.0.md`, guida e setup aggiornati.
- **Non fatto**: test non ancora lanciati sul PC di Alex; nessun commit o tag (li fa Alex).
- **Prossimo passo**: v0.3, modelli e voci con 4 blocchi base, serializzabili (ADR-0005).

## 2026-10-17 — Pacchetti condivisibili e backup cifrati
- **Fatto**: su idea di Alex scritto ADR-0005 (pacchetti `.zbpack.json`, solo struttura, solo dati); aggiornati roadmap (nuova v0.5, UI a v0.8, APK a v0.9), visione, architettura, CHANGELOG; aggiunta D-005; poi ADR-0006 e D-006 (storia dei dati e backup cifrati a tempo, anche fuori, leggibili solo dall'utente), roadmap v0.6/v0.7 e privacy aggiornate; ADR-0007 e D-007 (accesso Google obbligatorio, solo locale o + Drive, altri cloud in futuro; tester Alex + 2 amici); roadmap di [[Diario Componibile]] allineata alla repo.
- **Non fatto**: nessun codice, nessun commit.
- **Prossimo passo**: v0.2 dopo l'ok di Alex.

## 2026-10-17 — Visione "tutto in uno"
- **Fatto**: scritto `ZibaldOne/docs/tecnica/visione.md` (moduli, piattaforme, sincronizzazione, note di sicurezza su password e documenti); aggiornati README, roadmap, architettura, CHANGELOG.
- **Deciso poi**: Flet + SQLite (D-004, ADR-0004). **Aperto**: sincronizzazione PC ↔ telefono.
- **Prossimo passo**: v0.2, cartella dati e avviso privacy al primo avvio.

## 2026-10-17 — Requisiti privacy, distribuzione, piattaforme
- **Fatto**: aggiunti in ZibaldOne `docs/tecnica/privacy-e-sicurezza.md`, `distribuzione.md`, ADR-0002 (local-first e privacy), ADR-0003 (distribuzione); roadmap rifatta (IA rinviata, privacy in v0.2, Android); setup passato da WSL a Windows/PowerShell.
- **Aperto**: tecnologia per l'app Android (proposta Flet); formato dati.

## 2026-10-17 — Nome e ricerca
- **Fatto**: nome **ZibaldOne** (comandi `zibaldone` e `zbone`); ricerca breve in [[2026-10-17 Progetti simili a ZibaldOne]] con proposta di salvare le voci in Markdown + YAML.
- **Fatto**: scheletro **v0.1.0** in `Project-Two-Code/ZibaldOne/` (pyproject, CLI Typer `zibaldone`/`zbone` con `help` e `version`, 3 test pytest passati in un venv Python 3.13 di prova, CHANGELOG, `docs/` con 5 sottocartelle, ADR-0001).
- **Non fatto**: nessun commit o tag (li fa Alex); test non ancora eseguiti in WSL sul suo PC.
- **Prossimo passo**: decidere il formato dei dati, poi v0.2.

## 2026-10-17 — Scelta del progetto e piano
- **Fatto**: sincronizzato `AI_Context` nella nuova repo `Project-Two-Code`; lette le note della vecchia Journal App (manifest, modelli); scritto il piano [[Diario Componibile]] con roadmap v0.1–v0.8; registrata D-003.
- **Prossimo passo**: Alex approva nome e piano, poi si crea lo scheletro v0.1.

## 2026-10-17 — Brainstorming da zero
- **Fatto**: archiviato il primo brainstorming; nuove idee in [[2026-10-17 Brainstorming da zero]] (Wardrobe consigliata); creato [[Standard nuovo progetto]]; aggiornato [[Alex]] con filosofia, CyberGame, scrittura; lette le bozze `Desktop\wardrobe` (CSV, 36 foto) e `Desktop\ScannerLibri`.
- **Non fatto**: `CG—TOOLS` non leggibile (collegamento a WSL). Le modifiche sono nella copia del progetto: da sincronizzare quando Alex comunica la nuova repo.

## 2026-10-17 — Letto AI 4 Restaurants
- **Fatto**: letta la repo pubblica `KsandarIV/AI_4_Restaurants` (branch `casa_savov`, confrontato con `savov`), riscritta [[Chatbot Ristorante]] con stack e parti di Alex (voice, lan, entrypoint, setup); palette del sito ristorante esclusa da [[Design e palette]] su richiesta di Alex (non è sua); aggiornata [[Mappa competenze]].
- **Non fatto**: nessuna modifica a quella repo.

## 2026-10-17 — Correzione competenze dal corso
- **Fatto**: su indicazione di Alex corretti [[Materiale ITS AIRO2527]], [[Mappa competenze]], [[Percorso ITS]]; aggiunta [[Chatbot Ristorante]]; brainstorming riformulato (gap ML/DL ridimensionato, kit a due binari dati/app IA).
- **Prossimo passo**: scelta dell'opzione entro il 18 ottobre; codice del chatbot localizzato (vedi [[Chatbot Ristorante]]).

## 2026-10-16 sera — Integrato il Drive del corso
- **Fatto**: aggiunta [[Materiale ITS AIRO2527]] (sintesi preparata dal thread Drive), aggiornati [[Percorso ITS]], [[Mappa competenze]] e il brainstorming con l'opzione 0 "ML Project Kit" per il Project Work Exprivia del 20-23 ottobre.
- **Non fatto**: nessun codice modificato, nessun commit.
- **Prossimo passo**: Alex sceglie entro il 18 ottobre; se è l'opzione 0, si parte sabato dal kit.

## 2026-10-16 — Esplorazione repo e avvio brainstorming
- **Fatto**: esplorata la repo `GitHubRepository` saltando i file di dati; create le note di [[Alex]], [[Stile di codice]], [[Stile di pensiero e lavoro]], [[Design e palette]], [[Workflow Git]], schede dei progetti, [[Percorso ITS]], [[Mappa competenze]].
- **Proposte**: 4 opzioni in [[2026-10-16 Brainstorming nuovo progetto]], consigliata Nexus Metrics "chi vince dai primi 15 minuti".
- **Non fatto**: Google Drive non letto in questa voce (letto più tardi, vedi sopra). Nessun codice esistente modificato, nessun commit.
- **Prossimo passo**: Alex sceglie l'opzione entro domenica 2026-10-18.
