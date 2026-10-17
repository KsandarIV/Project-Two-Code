# T002 — Developer: refactor di brand.py in registro temi

**Ruolo e obiettivo:** Developer. Implementare il design di T001 in `brand.py`, con Filosofia come tema di default.

**Input:** `team/handoffs/T001-design.md`, `src/zibaldone/core/brand.py`, `tests/test_brand.py`. Per i chiamanti solo `grep -rn "core.brand import" src`.

**Deliverable:**
- `brand.py` con `Theme`, registro, selezione e fallback; il tema Filosofia contiene esattamente i dati della copia condivisa; i nomi Diggy, Ary, Hobbsy del PC si applicano in fase di integrazione.
- Test nuovi in `tests/test_brand.py`: selezione per id, fallback al default per id sconosciuto/vuoto/None, `list_themes`, un tema di prova aggiunto con una sola `register_theme` e visibile in `list_themes`, validazione (area senza mascotte → errore).

**Criteri di accettazione (testabili):**
1. Filosofia è il default e tutti gli import esistenti funzionano senza modifiche; output identico.
2. Aggiungere un tema = una voce di registro, nessun altro file.
3. `pytest` intero verde (oggi 524 test) + test nuovi.
4. Handoff ≤10 righe.

**Vincoli:** cambiare solo `brand.py` e `tests/test_brand.py`. Niente commit, niente bump di versione (lo fa il thread di sviluppo). Lavorare su una copia di scratch, non sulla cartella condivisa finché il Reviewer non approva.

**Output:** patch in `team/handoffs/T002.patch` + handoff in `team/handoffs/T002.md`.
