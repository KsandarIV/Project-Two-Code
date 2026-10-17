# I blocchi

Un **blocco** è un tipo di campo con le sue regole. Ogni modello è una lista ordinata di blocchi; ogni blocco ha una **chiave** (il nome tecnico, per esempio `voto`), un **tipo**, un'**etichetta**, se è **obbligatorio** e delle **opzioni**. Il codice è in `src/zibaldone/core/blocks.py`.

| Tipo | Cosa contiene | Opzioni | Come si scrive da terminale |
|---|---|---|---|
| `text` | una riga di testo | `max_length` (di base 300), `placeholder` | `Il nome della rosa` |
| `longtext` | testo su più righe | `max_length` (di base 50 000), `placeholder` | un testo qualsiasi |
| `number` | un numero | `min`, `max`, `unit`, `integer` | `12`, `3,5` |
| `rating` | voto a stelle | `max` da 3 a 10 (di base 5) | `4` |
| `tags` | etichette | `suggestions` | `romanzo, giallo` |
| `date` | un giorno | nessuna | `2026-10-17`, `17/10/2026`, `oggi`, `ieri` |
| `checklist` | cose da spuntare | `max_items` | `[x] correre; leggere; [ ] studiare` |
| `scale` | punteggio su una scala | `min`, `max`, `low_label`, `high_label` | `7` |
| `choice` | una voce da un elenco | `choices` (almeno 2), `values` (un numero per scelta) | `Buono` |
| `progress` | stato e contatore | `unit`, `total` | `in corso 150/320`, `completato`, `pausa` |
| `bookmark` | dove sei arrivato | `placeholder` | `pag. 150`, `S02E05` |
| `link` | collegamento ad altre voci | `template` (solo voci di quel modello), `multiple` | il titolo della voce o le prime lettere del suo id |

## Regole comuni
- Un blocco vuoto si salva come assente; un blocco obbligatorio vuoto blocca il salvataggio con un messaggio in italiano.
- Le opzioni sconosciute sono rifiutate: un modello con un errore di battitura non viene salvato a metà.
- Gli stati di `progress` sono: lista dei desideri, da iniziare, in corso, in pausa, completato, abbandonato. "Completato" porta il contatore al totale.
- `choice` con `values` dà un punteggio a ogni scelta (per esempio l'umore da 1 a 5), che userà la v0.1.4 per le statistiche.
- `link` salva gli id delle voci collegate. Dalla v0.1.2 i collegamenti diventeranno anche ricerca e grafo.

## Aggiungere un tipo nuovo
1. Una classe in `blocks.py` che estende `BlockType`, con `name`, `label`, `description`, `options` e i metodi `normalize`, `parse`, `to_text`.
2. Registrarla in `BLOCK_TYPES`.
3. Test in `tests/test_blocks.py`.

I modelli già salvati non cambiano: un tipo nuovo si aggiunge, non sostituisce.
