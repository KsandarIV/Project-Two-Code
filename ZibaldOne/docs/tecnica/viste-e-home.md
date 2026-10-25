# Viste salvate e home su misura

Dalla 0.2.8; dalla 0.3.1 la home è di nuovo l'elenco ordinabile (la griglia 5×6 della 0.3.0 è in pausa) e le viste si chiamano Lente.

## Le viste (Lente)
Il pacchetto **Lente · Viste** (id `theoria`, invariato) ha il modello `vista` (slug invariato): il nome *Theoria* resta alle statistiche. Chi aveva il modello con il vecchio nome lo trova rinominato; un nome scelto dall'utente non si tocca. Lente si spiega da sola e offre nove esempi da cui partire. Una vista è una ricerca con un nome e si compone di `modello` (vuoto = tutti), `area` (vuota = tutte), `testo` (come la ricerca), un filtro `campo` = `valore` su un blocco (per esempio `stato` = `In corso`; vale anche l'etichetta di uno stato o una voce di lista) e l'`ordine` («Più recenti» o «Titolo»).
- Le voci con blocchi segreti non sono mai filtro né risultato.
- App: **/viste** (elenco, «Nuova vista», esegui, elimina; installa il pacchetto se manca) e **/viste/<id>** (risultati).
- Terminale: `zbone viste`, `viste mostra NOME`, `viste salva NOME --modello libro --campo stato="In corso"`, `viste togli NOME`. NOME può essere le prime lettere.

## La home (Oggi)
Oggi è fatto di **riquadri fissi in lista**: `promemoria`, `citazione`, `aree`, `abitudini`, `ricorrenze`, `obiettivi`, `bilancio` e `vista:<id>` per ogni vista che vuoi vedere (prime 5 voci e «Vedi tutti»). Il layout è un piccolo `home.json` nella cartella dei dati (`storage/home_log.py`); chiavi sconosciute o viste cancellate si ignorano, un file rovinato dà il layout di base e non blocca l'apertura.
- App: in Oggi i riquadri si riordinano **trascinandoli**, senza pulsanti con le frecce. Impostazioni → **La tua home**: riordina, nascondi/mostra, «Ripristina».
- Terminale: `zbone home`, `home aggiungi|togli|sposta CHIAVE [POSIZIONE]|ripristina`.
- Un `home.json` della 0.3.0 (griglia, versione 2) si legge ancora: i riquadri passano in lista nell'ordine di lettura (riga, poi colonna).

## Ricorrenze, obiettivi, bilancio
- **Ricorrenze**: i compleanni (blocco `compleanno` delle persone) dei prossimi 30 giorni, con l'età che si compie; il 29 febbraio cade il 28 negli anni non bisestili. `zbone ricorrenze [--giorni N]`.
- **Obiettivi**: gli obiettivi attivi di tutte le aree, per scadenza (quelli senza scadenza in fondo), con avanzamento e giorni mancanti; riga anche nella pagina dell'area. `zbone area obiettivi [AREA]`.
- **Bilancio**: saldo e mese in corso da `core/finance`; si legge solo con il PIN, a conti chiusi il riquadro dice «Apri con il PIN» ([le finanze](finanze.md)).

## Limiti
Le ricorrenze sono solo compleanni (niente anniversari o cene); un solo filtro su un blocco per vista; i riquadri si ordinano ma non si ridimensionano. La griglia libera con riquadri ridimensionabili (0.3.0) è in pausa: si rivedrà per i blocchi nella composizione dei modelli.
