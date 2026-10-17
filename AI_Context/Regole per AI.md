---
tags:
  - ai-context
  - regole
date: 2026-10-16
---
# <span style="color:#00E5FF">Regole per AI</span>

Torna a [[00 - START HERE]].

> [!warning] Regole non negoziabili
> - **Chiedi prima** di modificare codice o configurazioni esistenti.
> - **Mai** `commit`, `push`, `merge`, PR, branch o tag senza una richiesta esplicita di Alex. Alex fa i commit da solo (vedi [[Workflow Git]]).
> - **Mai** leggere, stampare o allegare `.env`, chiavi API, PUUID o dati personali.
> - **Non** leggere file di dati grandi (`.csv`, `.json`, `.db`, `.parquet`, `.sqlite`, timeline): basta lo schema o poche righe.
> - Niente servizi a pagamento o cloud obbligatori senza una decisione esplicita: si preferisce **locale e gratuito** (es. Ollama).

## Come lavorare
- Conversazione e documenti in **italiano**; codice, commenti, docstring, log ed eccezioni in **inglese** (regola di [[Nexus Metrics]]).
- Un passo piccolo e verificabile alla volta, con criteri di accettazione chiari. Vedi [[Stile di pensiero e lavoro]].
- Prima di toccare un progetto, leggi i suoi file di contesto (`AGENTS.md`, `AI_WORKING_AGREEMENT.md`, `project_roadmap.md`, `HANDOFF.md`, `BACKLOG.md`) se esistono.
- I notebook sono esplorativi; la logica stabile va in moduli Python con test offline.
- Non dichiarare successo se qualcosa non è stato verificato: riporta cosa hai eseguito e cosa no.

## A fine sessione
1. Aggiungi una voce in [[Registro lavoro]] usando [[Template sessione]].
2. Se è stata presa una decisione che vincola il futuro, aggiungila in [[Registro decisioni]].
3. Aggiorna la nota del progetto attivo (stato e prossimo passo).
4. Aggiorna `aggiornato:` in [[00 - START HERE]] se hai cambiato la mappa.
