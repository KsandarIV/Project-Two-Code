# STATE — team multi-thread di ZibaldOne

Aggiornato: 2026-10-17 · Owner del file: Orchestratore (solo lui lo modifica; i worker scrivono solo il proprio handoff).

## Versione
- Ultima rilasciata: **0.1.5** (commit + tag sul PC, non pushati).
- In corso nel thread "Vibe Coding su ZibaldOne": **0.2.0** (8 aree), piano fino alla 0.2.9.
- Trigger del team: fine 0.2.9. Avvio anticipato solo per setup e task isolati (vedi Decisioni D2).

## Ruoli
| Ruolo | Chi | Note |
|---|---|---|
| Orchestratore | thread "Team multi-thread" | non scrive codice; legge solo STATE.md e handoff |
| Developer, Architect, QA, Reviewer, Creative, Design, Web design, Cybersecurity | worker (subagent dell'orchestratore) | un ruolo per task; il Reviewer non rivede mai lavoro suo |
| Facoltativi | Docs, Packaging/Installer, Accessibilità, Localizzazione | solo se serve |

## Task aperti
| ID | Titolo | Owner | Stato | Dipende da |
|---|---|---|---|---|
| T001 | Design registro temi (interfaccia) | Architect (opus) | fatto | — |
| T002 | Refactor brand.py → registro temi + test | Developer (sonnet) | fatto | T001 |
| T003 | Revisione T001+T002 sui criteri di accettazione | Reviewer (opus) | APPROVATO | T002 |
| T006 | Integrare T002.patch nella prossima versione (nomi Diggy/Ary/Hobbsy) | thread di sviluppo | da fare | T003 |
| T007 | UI e CLI leggono `active_theme`; nomenclatura immutabile (MappingProxyType) | Developer | futuro | T006 |
| T004 | Due temi finali da proporre (oltre a Filosofia) | Creative | solo appuntato | temi non ancora scelti da Alex |
| T005 | Installer: scelta di 1, 2 o 3 temi da scaricare | Architect + Packaging | in attesa | T003, T004 |

## Decisioni
- D1 (2026-10-17): tema di default = **Filosofia**. Il registro vive in `src/zibaldone/core/brand.py`; i nomi pubblici attuali (`NOMENCLATURE`, `MASCOTS`, `QUOTES`, `APP_*`, `mascot_for`, `quote_of_the_day`) restano e puntano al tema di default.
- D2 (2026-10-17): partenza anticipata solo di setup e T001–T003, perché brand.py è isolato dal lavoro sulle aree. Il commit di T002 entra nella versione successiva del thread di sviluppo, che resta l'unico a fare commit e tag sul PC.
- D3: `AREAS` (le 8 aree) è struttura dati, non tema: resta fuori dal registro. Ogni tema deve avere una mascotte per area.
- D5 (2026-10-17): i temi oltre a Filosofia non sono ancora decisi; T004 resta solo appuntato finché Alex non li porta.
- D4: un "tema" qui è identità/testi (nomi, mascotte, citazioni, motto). I colori di `ui/theme.py` sono un'altra cosa; se un tema vorrà una palette propria, è un task a parte.

## Regole di lavoro
- Modello per worker (richiesta di Alex, 2026-10-17): ogni worker parte col modello più adatto al task. Haiku per lavoro meccanico (creare cartelle/file, rinominare, copiare); Sonnet per implementazione, test e QA di routine; Opus per design, architettura, sicurezza e revisione da giudice. Il modello scelto si scrive nella colonna Owner.
- Handoff ≤10 righe in `team/handoffs/<ID>.md`: cosa cambiato, file toccati, problemi aperti.
- Letture mirate (grep, intervalli di righe); niente rilettura dell'intero codice.
- Nessun push, nessun commit sul PC dai worker. Codice in inglese, testi utente in italiano.
