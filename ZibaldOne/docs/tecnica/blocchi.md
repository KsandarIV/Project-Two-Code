# I blocchi

Un **blocco** è un tipo di campo con le sue regole. Ogni modello è una lista ordinata di blocchi; ogni blocco ha una **chiave** (il nome tecnico, per esempio `voto`), un **tipo**, un'**etichetta**, se è **obbligatorio** e delle **opzioni**. Il codice è in `src/zibaldone/core/blocks.py`.

| Tipo | Cosa contiene | Opzioni | Come si scrive da terminale |
|---|---|---|---|
| `text` | una riga di testo | `max_length` (di base 300), `placeholder`, `format` (`email` o `telefono`, dalla 0.2.1) | `Il nome della rosa` |
| `longtext` | testo su più righe | `max_length` (di base 50 000), `placeholder`, `spoiler` (nascosto nella voce finché non lo apri, dalla 0.2.5) | un testo qualsiasi |
| `number` | un numero | `min`, `max`, `unit`, `integer` | `12`, `3,5` |
| `rating` | voto a stelle | `max` da 3 a 10 (di base 5), `half` (anche mezzi punti, dalla 0.2.5) | `4`, `4,5` con `half` |
| `tags` | etichette | `suggestions` | `romanzo, giallo` |
| `date` | un giorno | nessuna | `2026-10-17`, `17/10/2026`, `oggi`, `ieri` |
| `checklist` | cose da spuntare | `max_items` | `[x] correre; leggere; [ ] studiare` |
| `scale` | punteggio su una scala | `min`, `max`, `low_label`, `high_label` | `7` |
| `choice` | una voce da un elenco | `choices` (almeno 2), `values` (un numero per scelta) | `Buono` |
| `progress` | stato e contatore | `unit`, `total` | `in corso 150/320`, `completato`, `pausa` |
| `bookmark` | dove sei arrivato | `placeholder` | `pag. 150`, `S02E05` |
| `link` | collegamento ad altre voci | `template` (solo voci di quel modello), `multiple` | il titolo della voce o le prime lettere del suo id |
| `favorite` | un cuore: preferito o no (dalla 0.2.5) | nessuna | `sì`, `no` |
| `media` | foto, video, audio e documenti allegati (dalla 0.2.4) | `max_items` (di base 50) | non da `--set`: `zbone allegati aggiungi VOCE FILE` |
| `secret` | testo cifrato con la tua chiave (dalla 0.2.3) | `level` (`protetto` di base, o `massimo`), `multiline`, `placeholder`, `format` (`importo` o `saldo`: un importo di denaro, dalla 0.2.6) | un testo qualsiasi; con `multiline`, `\n` va a capo |

## Regole comuni
- Un blocco vuoto si salva come assente; un blocco obbligatorio vuoto blocca il salvataggio con un messaggio in italiano.
- Le opzioni sconosciute sono rifiutate: un modello con un errore di battitura non viene salvato a metà.
- Gli stati di `progress` sono: lista dei desideri, da iniziare, in corso, in pausa, completato, abbandonato. "Completato" porta il contatore al totale. Dalla 0.2.5 il valore ha anche `started` e `finished`, i giorni di inizio e fine: li scrive il Database quando lo stato cambia, e un import porta quelli del suo file ([svago avanzato](svago.md)).
- `choice` con `values` dà un punteggio a ogni scelta (per esempio l'umore da 1 a 5): dalla v0.1.4 le statistiche lo usano per l'umore ([statistiche e revisioni](statistiche.md)).
- `secret` si salva solo cifrato e ovunque si legge «🔒 cifrato»: non entra nella ricerca, nei collegamenti, nelle esportazioni né nell'IA, e non può fare da titolo ([i segreti](segreti.md)).
- `media` salva solo i nomi dei file (`file`, `name`, `size`): i file stanno nella cartella `media/` e nei backup ([gli allegati](allegati.md)).
- `link` salva gli id delle voci collegate. Dalla v0.1.2 ogni collegamento (anche `[[Titolo]]` in un testo) è nella tabella `links`: chi cita chi, "tutto su Marco" ([ricerca e collegamenti](ricerca-e-collegamenti.md)); dalla 0.1.3 diventa il grafo.

## Aggiungere un tipo nuovo
1. Una classe in `blocks.py` che estende `BlockType`, con `name`, `label`, `description`, `options` e i metodi `normalize`, `parse`, `to_text`.
2. Registrarla in `BLOCK_TYPES`.
3. Test in `tests/test_blocks.py`.

I modelli già salvati non cambiano: un tipo nuovo si aggiunge, non sostituisce.
