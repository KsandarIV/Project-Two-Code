---
tags:
  - decisioni
date: 2026-10-16
---
# Registro decisioni

Torna a [[00 - START HERE]] · formato in [[Template decisione]].

Le decisioni più recenti in alto. Una decisione presa non va ridiscussa senza un motivo nuovo.

## D-007 — 2026-10-17 — Accesso Google obbligatorio, cloud a scelta
- **Decisione**: al primo avvio accesso con Google obbligatorio; poi l'utente sceglie solo locale o locale + Google Drive. Il cloud è solo un posto per file cifrati, quindi in futuro altri cloud configurabili. Arriva alla v0.7.
- **Perché**: scelta di Alex; tester iniziali Alex + 2 amici.
- **Conseguenze**: ADR-0007; progetto Google in modalità test (gratis, accesso da rinnovare ogni ~7 giorni finché l'app non è verificata); permessi Drive stretti.

## D-006 — 2026-10-17 — Storia dei dati e backup cifrati
- **Decisione**: istantanee dei dati come commit (elenco, ripristino), cifrate sul dispositivo con chiave che solo l'utente ha, con durata a tempo (proposta 7 giornaliere, 4 settimanali, 12 mensili), copiabili fuori (Drive, chiavetta). Recupero: con Drive tramite account Google (chiave nello spazio nascosto del suo Drive), in solo locale tramite codice di recupero; niente server nostro con mail.
- **Perché**: idea di Alex: tornare indietro come con git, senza che nessuno, nemmeno lui, possa leggere i backup.
- **Conseguenze**: ADR-0006 (proposta); v0.6 storia e backup locali, v0.7 cifratura e copia fuori. Una voce cancellata vive nei backup fino alla scadenza: va scritto nell'avviso privacy.

## D-005 — 2026-10-17 — Configurazioni di blocchi condivisibili
- **Decisione**: le configurazioni di blocchi (modelli) si raccolgono in **pacchetti** `.zbpack.json`, condivisibili tra utenti. Modelli pronti dell'app, modelli degli utenti e futuri consigli dell'app usano lo stesso formato. Solo struttura, mai voci; solo dati, mai codice.
- **Perché**: idea di Alex; la configurazione di un utente può servire a un altro.
- **Conseguenze**: ADR-0005 (proposta); modelli serializzabili dalla v0.3, modelli pronti come pacchetti alla v0.4, export/import alla v0.5; la UI slitta a v0.8 e la distribuzione ai tester a v0.9.

## D-004 — 2026-10-17 — Flet e SQLite per ZibaldOne
- **Decisione**: interfaccia con Flet (Python, Windows + Android + Linux), dati in SQLite con export Markdown. Scelta di Alex dalla scheda.
- **Perché**: resta in Python e un solo codice copre tutte le piattaforme.
- **Conseguenze**: ADR-0004 nella repo; cuore indipendente dall'interfaccia.

## D-003 — 2026-10-17 — Si parte dal Diario Componibile, nella nuova repo
- **Decisione**: progetto attivo = idea B, [[Diario Componibile]]. Poi Wardrobe (A) e Worldbuilding (D). Si lavora **solo** in `Desktop\ProjectTwoCode\Project-Two-Code`.
- **Perché**: è la più gestibile ora; la vecchia [[Journal App]] dà idee riutilizzabili.
- **Conseguenze**: `GitHubRepository` non si tocca; se ne copiano solo le idee buone. `AI_Context` vive nella nuova repo.

## D-002 — 2026-10-17 — Brainstorming ripartito da zero
- **Decisione**: le opzioni 0, 1, 2 del primo brainstorming vanno in archivio; 3 (Odyssey Analytics) e 4 (Study Buddy) scartate. Nuove idee in [[2026-10-17 Brainstorming da zero]].
- **Perché**: Alex vuole un progetto nuovo, a passi piccoli, che lo faccia crescere; le prime idee non lo convincevano.
- **Conseguenze**: il nuovo progetto segue [[Standard nuovo progetto]] e vivrà in una nuova repo che Alex sta creando, dove sposterà anche `AI_Context`.

## D-001 — 2026-10-16 — Cartella di contesto `AI_Context`
- **Decisione**: il contesto per le sessioni AI vive in `AI_Context/` alla radice della repo, organizzato come vault Obsidian con wikilink.
- **Perché**: Alex non vuole passare ogni volta tutta la repo; un nome neutro va bene per Claude, Codex e altri agenti. Generalizza `AGENTS.md`/`HANDOFF.md` già usati nei singoli progetti.
- **Conseguenze**: ogni sessione aggiorna [[Registro lavoro]]; i file di contesto dei singoli progetti restano dove sono e vengono solo linkati.
