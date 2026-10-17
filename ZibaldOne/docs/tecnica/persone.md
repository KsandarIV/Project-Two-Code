# Le persone · Agorà (dalla 0.2.1)

L'*agorà* era la piazza dove ci si incontrava. Una persona è una voce del modello *L'Altro* (`persona`); ogni *Simposio* (`incontro`) che la collega è un contatto con lei. Da qui vengono le sue aree, l'ultimo contatto, il ritmo e la pagina con **tutto di Marco**, area per area.

![Una persona sul telefono](../immagini/persona-telefono.png)

## Cosa ha una persona
| Blocco | Cosa contiene |
|---|---|
| Nome, Soprannomi | il titolo e i nomi con cui la citi (`[[Marchino]]`) |
| Legame (`ruolo`) | Famiglia, Amico, Collega, Mentore, Conoscente, Altro |
| Ruoli (`ruoli`) | ruoli di base (madre, capo, medico, commercialista …) o tuoi, quanti vuoi |
| Aree | altre aree a mano |
| Telefono, Email | controllati mentre li scrivi (blocco testo con `format`); nell'app si toccano per chiamare o scrivere |
| Social, Compleanno, Note | come prima |
| Ogni quanto sentirvi (`frequenza`) | ogni settimana … ogni anno |

## In quali aree sta
Legame e ruoli di base mettono la persona nell'area giusta da soli: la madre in Famiglia, il capo in Lavoro, il medico in Salute, il commercialista in Finanze (l'elenco è in `core/roles.py`). I ruoli tuoi non danno un'area: per quelli c'è il blocco Aree. Sociale, l'area del modello, vale solo per chi non ne ha un'altra. Questa regola vale dalla 0.2.1 e l'indice delle aree si ricostruisce da solo all'apertura ([ADR-0011](../decisioni/ADR-0011-aree-della-vita.md)).

## Contatti e ritmo
- Un contatto è un Simposio che collega la persona; il blocco **Come** dice se era una chiamata, dei messaggi, un'uscita, una visita … (i Simposi di prima della 0.2.1 contano come "Incontro").
- **Ultimo contatto**: il giorno dell'ultimo Simposio con lei. **Ritmo**: la media dei giorni tra gli ultimi 10 contatti.
- **Da sentire**: chi ha un "Ogni quanto sentirvi" e non senti da almeno quel tempo. Le parole restano neutre ("potrebbe essere il momento di farsi vivi"), come vuole [ADR-0008](../decisioni/ADR-0008-notifiche.md); non arrivano notifiche.
- Segnare un contatto al volo (Chiamata, Messaggi, Di persona) crea un Simposio con il titolo già scritto ("Chiamata con Anna") nell'area principale della persona.

## Tutto di Marco
La pagina di una persona raccoglie ogni voce che la collega (blocchi collegamento e `[[Marco]]`) e la raggruppa per l'area di quella voce: gli incontri in Famiglia, il libro che ti ha prestato in Svago, le voci senza area in fondo. Sotto, i testi che la nominano senza collegarla.

## Dove si usa
- **App**: nella pagina di un'area, il riquadro **Persone** (chi è da sentire ha il segno); toccando una persona si apre `/persone/<id>`. Dalla pagina di una voce Persona, **Tutto di Marco**.
- **CLI**: `zbone persona` (chi è da sentire per prima), `zbone persona list --area famiglia`, `zbone persona show marco`, `zbone persona sentito marco --tipo chiamata --nota "..."` ([guida rapida](../utente/guida-rapida.md#le-persone--agorà)).

## Codice
- `core/roles.py` (ruoli e aree), `core/people.py` (persone, contatti, ritmo, pagina, `log_contact`), `core/areas.py` (`entry_areas` con i ruoli), `storage/database.py` (`AREA_RULES`).
- `ui/views/people.py`, `ui/viewmodels.py` (`person_view`, `people_rows`), `cli/person_cmd.py`, `packs/persone.zbpack.json` (Agorà 1.2.0).
- Test: `tests/test_people.py`, `tests/test_ui_views.py`.
