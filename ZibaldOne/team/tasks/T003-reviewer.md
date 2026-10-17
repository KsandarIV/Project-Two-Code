# T003 — Reviewer: giudizio su T001 + T002

**Ruolo e obiettivo:** Reviewer indipendente (non ha scritto T001 né T002). Verificare la patch contro i criteri di accettazione.

**Input:** `team/tasks/T002-developer.md` (criteri), `team/handoffs/T001-design.md`, `team/handoffs/T002.patch`, `team/handoffs/T002.md`.

**Deliverable:** verdetto APPROVATO / DA RIVEDERE, con per ogni criterio 1–4 l'evidenza (comando eseguito e risultato, o riga di codice). Controlli extra: un tema di prova aggiunto in un test temporaneo senza toccare altri file; fallback con id sconosciuto; nessun cambiamento di comportamento per i chiamanti.

**Vincoli:** non correggere il codice; segnalare. Applicare la patch su una copia di scratch.

**Output:** handoff ≤10 righe in `team/handoffs/T003.md`.
