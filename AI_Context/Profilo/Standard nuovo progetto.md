---
tags:
  - profilo
  - metodo
date: 2026-10-17
---
# Standard nuovo progetto

Torna a [[00 - START HERE]] · vedi [[Stile di codice]], [[Stile di pensiero e lavoro]], [[Workflow Git]].

Richieste di Alex (2026-10-17) valide per qualsiasi nuovo progetto:
- **Scheletro piccolo, poi crescita**: ogni versione aggiunge una sola capacità chiara. Pensato scalabile dal giorno 0.
- **Versionato dal giorno 0**: SemVer, `CHANGELOG.md`, tag git per ogni versione, "vita, morte e miracoli" di ogni versione tracciati, altrimenti il progetto sfugge di mano.
- **CLI con help**: `nomeapp help` / `nomeapp --help` elenca tutti i comandi, come `git` o `ollama`; `nomeapp version`. Comandi ad hoc anche per i test.
- **Poi la UI grafica** sopra la stessa logica (la CLI e la UI chiamano gli stessi moduli).
- **`docs/` ricca e organizzata** in sottocartelle, per esempio: `docs/utente/` (guida semplice), `docs/tecnica/` (architettura, moduli), `docs/decisioni/` (ADR), `docs/versioni/` (note per versione), `docs/sviluppo/` (setup, test, comandi).
- **Ambiente**: **Windows + PowerShell** per ZibaldOne (correzione di Alex 2026-10-17: niente WSL, che usa solo per la cybersecurity). Comandi da lanciare in PowerShell.
- **Privacy e trasparenza**: dati in locale, l'app dice chiaramente dove e con quali rischi; niente telemetria; conformità GDPR come requisito.
- **Tester**: amici su **Android**; aggiornamenti e patch a distanza.
- **IA**: rinviata finché non c'è dove far girare un modello adatto.
- **Backup**: tutto in git e su remoto fin da subito (Alex ha perso appunti irrecuperabili in passato).
