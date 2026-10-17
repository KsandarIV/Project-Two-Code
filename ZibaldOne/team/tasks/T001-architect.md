# T001 — Architect: interfaccia del registro temi

**Ruolo e obiettivo:** Architect. Progettare l'interfaccia del registro temi di `brand.py`, così che un tema si aggiunga con una sola voce di registro.

**Input (leggere solo questo):**
- `src/zibaldone/core/brand.py` (121 righe, tutto)
- `tests/test_brand.py`
- `grep -rn "core.brand import" src` per vedere chi usa cosa
- `src/zibaldone/ui/navigation.py` righe 30–65 (usa NOMENCLATURE all'import)
- `team/STATE.md`, sezione Decisioni

**Deliverable:** `team/handoffs/T001-design.md` (≤40 righe) con:
- dataclass `Theme` (id, nome visibile, app name/tagline/motto, nomenclature, mascots, quotes) e cosa resta fuori (AREAS);
- API: registro (dict id→Theme), `register_theme`, `list_themes`, `get_theme(id)` con fallback al default, `active_theme(settings)` / chiave `theme` in settings.json (o env `ZIBALDONE_THEME`), `DEFAULT_THEME_ID = "filosofia"`;
- regole di validazione (stesse chiavi di nomenclatura del default, una mascotte per ogni area, almeno N citazioni);
- come i nomi pubblici attuali restano compatibili;
- elenco dei test da scrivere.

**Criteri di accettazione:** il Developer può implementare senza domande; nessun file fuori da `brand.py` e dai test va cambiato per aggiungere un tema; il comportamento attuale resta identico.

**Vincoli:** solo design, niente codice in `src/`. Non toccare i colori (`ui/theme.py`). Il cambio tema a runtime nella UI è fuori scopo (annotarlo come task futuro).

**Output:** il file di design + handoff ≤10 righe in `team/handoffs/T001.md`.
