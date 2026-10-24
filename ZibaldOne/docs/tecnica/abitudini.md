# Le abitudini (Askesis)

Dalla 0.2.7. Il pacchetto **Askesis · Abitudini** (`askesis`) ha due modelli:

- **Rituale** (*Askesis*): `nome`, `ogni` («Ogni giorno» o «Più volte a settimana»), `volte` (a settimana, 1–7, di base 3), `unita` (per esempio «bicchieri»; vuota = fatto sì/no), `traguardo` (la quantità del giorno che conta come fatto), `promemoria`, `attivo`. L'area si sceglie per voce (di base Salute).
- **Pratica** (*Praxis*): un giorno segnato di un rituale, con una quantità facoltativa. Il giorno della voce è il giorno segnato; al più una pratica per rituale e giorno.

Niente è cifrato: le abitudini non sono dati sensibili. Hexis (`abitudine` in Delfi · Io) non cambia.

## Le serie
Le calcola `core/habits.py` in memoria, riusando `core/stats.streaks`:
- **Ogni giorno**: i giorni di fila con una pratica (che arriva al traguardo, se c'è). Oggi non ancora segnato **non** spezza la serie.
- **Più volte a settimana**: le settimane (lunedì–domenica) di fila con almeno `volte` pratiche.
- Si leggono la serie attuale, la più lunga e le pratiche della settimana. Il tono resta neutro ([ADR-0008](../decisioni/ADR-0008-notifiche.md)): numeri, mai rimproveri.

## Nell'app
- **Oggi**: riquadro «Abitudini di oggi» con i rituali attivi non ancora fatti; un tocco segna o toglie.
- **`/abitudini`**: tutti i rituali con serie attuale e più lunga e gli ultimi 7 giorni; «Nuovo rituale»; installa il pacchetto se manca.
- **Pagina dell'area**: i rituali di quell'area con la serie.

## Dal terminale
```
zbone abitudini                        # da fare oggi e serie
zbone abitudini segna acqua 8          # NOME può essere le prime lettere
zbone abitudini segna meditazione --giorno 2026-10-23
zbone abitudini togli acqua
zbone abitudini serie
```
Un nome ambiguo dà un errore con l'elenco; un giorno nel futuro non si segna.

## Limiti
Niente promemoria che suonano davvero (la scelta `promemoria` è registrata, il collegamento ai promemoria arriva dopo); niente grafico nel tempo; gli obiettivi con avanzamento sono della 0.2.8.
