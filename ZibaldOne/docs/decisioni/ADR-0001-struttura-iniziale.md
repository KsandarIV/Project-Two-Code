# ADR-0001 — Struttura iniziale

- **Data**: 2026-10-17 · **Stato**: accettata
- **Contesto**: si riparte da zero rispetto alla vecchia Journal App, che usava una classe fissa per ogni tipo (`Book`, `Anime`…) ed era difficile da estendere.
- **Decisione**: pacchetto Python in `src/zibaldone/`, CLI con Typer esposta come `zibaldone` e `zbone`, test con pytest, documentazione divisa per pubblico in `docs/`, versioni SemVer con CHANGELOG e tag git.
- **Conseguenze**: ogni nuova funzione entra come comando CLI testato prima di avere una UI.
