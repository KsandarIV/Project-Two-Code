# Ricerca e collegamenti · Zetesis (dalla 0.1.2)

*Zetesis* è "la ricerca" degli scettici antichi: Sesto Empirico chiama lo scettico *zetetico*, colui che cerca. In ZibaldOne cerca in tutte le voci e tiene i collegamenti tra una voce e l'altra.

## Cosa si cerca
- Tutti i blocchi di testo di una voce: titolo, testi, segnalibri, scelte, liste, i titoli delle voci collegate; le etichette hanno un campo loro.
- Maiuscole e accenti non contano: "perche" trova "perché", "CITTA" trova "città".
- La sintassi è una sola, uguale nella CLI e nell'app:

| Scrivi | Trova |
|---|---|
| `cena lago` | le voci con tutte e due le parole |
| `"cena al lago"` | le parole in quest'ordine |
| `perch*` | le parole che cominciano così |
| `-lavoro` | le voci senza questa parola (anche `-"riunione lunga"`) |

Quello che scrive l'utente non arriva mai così com'è a SQLite: diventa una lista di parole fatte solo di lettere e numeri, sempre tra virgolette (`core/search.py`).

## Come funziona
- **Indici derivati** (migrazione 2 del database): `search_index` (titolo, nome, corpo, etichette e testo normalizzato di ogni voce), `entry_tags`, `entry_names` (titoli e soprannomi, per risolvere `[[...]]`), `links` e `index_state`. Si scrivono **nella stessa transazione** della voce, quindi non restano mai indietro.
- **FTS5 quando c'è**: se SQLite ha FTS5 (quasi sempre su PC; su Android non è garantito) c'è anche la tabella `search_fts`, ordinata con `bm25()` e pesi titolo 5, corpo 1, etichette 3. Senza FTS5 la stessa ricerca gira con `LIKE` sul testo normalizzato: stessi risultati, solo più lenta su tanti dati. `ZIBALDONE_NO_FTS=1` forza la ricerca semplice (serve nei test).
- **Si ricostruiscono sempre**: gli indici sono una copia ordinata delle voci. All'apertura lo Store controlla che corrispondano (una voce modificata fuori dall'app, un backup ripristinato) e li ripara da solo; `Store.rebuild_indexes()` li rifà da zero. Aggiornando dalla 0.1.1, la migrazione 2 li riempie la prima volta, con un backup prima come ogni migrazione.

## Collegamenti
Due modi di collegare una voce a un'altra:
1. un **blocco `link`** (per esempio "Con chi" nell'incontro): il collegamento punta all'id della voce;
2. **`[[Titolo]]`** dentro un testo: si risolve, senza badare a maiuscole e accenti, alla voce con quel titolo o alla persona con quel soprannome. Se ce ne sono più di una vince prima una persona, poi un titolo rispetto a un soprannome, poi la voce più vecchia. Se non c'è ancora nessuna voce con quel titolo il collegamento resta in attesa e **si collega da solo** quando la voce nasce; se la voce cambia titolo, i collegamenti si aggiornano.

Per ogni voce ZibaldOne sa quindi:
- **chi collega** (i suoi collegamenti in uscita);
- **chi la cita** (i collegamenti inversi): "tutto su Marco";
- **chi la nomina senza collegamento**: le voci che contengono il suo titolo o un soprannome senza `[[...]]`, per proporre di collegarle.

## Dove si usa
- CLI: `zbone search` e `zbone links` ([guida rapida](../utente/guida-rapida.md#cercare-e-collegare--zetesis)).
- App: la casella di ricerca di **Voci** cerca in tutti i blocchi, con il pezzo di testo trovato sotto il titolo; la pagina di una voce mostra **Citata da** e **La nominano senza collegamento**.
- Dalla 0.1.3 i collegamenti diventano il grafo; dalla 0.1.4 entrano nelle statistiche.

## Codice
- `core/search.py`: sintassi, normalizzazione, documento di una voce, estratti. Solo funzioni pure.
- `core/links.py`: collegamenti da blocchi e da `[[...]]`, nomi e soprannomi. Solo funzioni pure.
- `storage/database.py`: tabelle, migrazione 2, `search`, `outgoing`, `backlinks`, `unlinked_mentions`, `about`.
- Test: `tests/test_search.py`, `tests/test_links.py`, `tests/test_cli_insights.py`.
