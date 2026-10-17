# Guida rapida

ZibaldOne si usa dal terminale con il comando `zibaldone` oppure, più corto, `zbone`.

## Comandi di base
| Comando | Cosa fa |
|---|---|
| `zbone help` | mostra tutti i comandi disponibili |
| `zbone version` | mostra la versione installata |
| `zbone privacy` | dove sono i tuoi dati, quanto spazio usano, rischi e stato del consenso |
| `zbone privacy revoke` | revoca il consenso (i file restano dove sono) |
| `zbone data path` | stampa il percorso della cartella dati |
| `zbone <comando> --help` | spiega un singolo comando |

La prima volta che usi un comando sui dati, ZibaldOne ti mostra un avviso sulla privacy e ti chiede se continuare. Se rispondi no, non salva nulla.

## Tre parole per capire tutto
- **Blocco**: un pezzo di informazione con le sue regole, per esempio un testo, un voto a stelle o delle etichette. Ci sono 12 tipi: li vedi con `zbone template blocks` e sono spiegati in [blocchi](../tecnica/blocchi.md).
- **Modello**: una ricetta fatta di blocchi, per esempio "Libro" con titolo, autore, voto e generi. Lo crei tu.
- **Voce**: un modello compilato, per esempio il libro che stai leggendo.

## Creare un modello
Con le domande (ZibaldOne ti chiede nome e blocchi uno alla volta):
```powershell
zbone template create
```
Oppure in una riga sola. Ogni `--block` è `chiave:tipo:Etichetta`, e un `!` finale lo rende obbligatorio. `--option` cambia una regola del blocco:
```powershell
zbone template create Libro --block "titolo:text:Titolo!" --block "autore:text" --block "voto:rating" --block "stato:progress:Lettura" --block "generi:tags" --option voto.max=5 --option stato.unit=pagine
```
| Comando | Cosa fa |
|---|---|
| `zbone template list` | i tuoi modelli, con quante voci ha ognuno |
| `zbone template show libro` | i blocchi di un modello (`--json` per vederlo come file) |
| `zbone template create --from-file libro.json` | crea un modello da un file JSON |
| `zbone template delete libro` | elimina un modello, solo se non ha voci |
| `zbone template blocks` | i 12 tipi di blocco con le loro regole |

## Scrivere una voce
Con le domande, blocco per blocco:
```powershell
zbone entry add libro
```
Oppure in una riga, con `--set blocco=valore`:
```powershell
zbone entry add libro --set "titolo=Il nome della rosa" --set autore=Eco --set voto=5 --set "stato=in corso 150/503" --set "generi=romanzo, giallo"
```
| Comando | Cosa fa |
|---|---|
| `zbone entry list` | le ultime voci (`--template libro`, `--day oggi`, `--since 2026-10-01`, `--until …`) |
| `zbone entry show b29f` | una voce intera; bastano le prime 4 lettere dell'id |
| `zbone entry edit b29f --set voto=4` | cambia un blocco; `--set voto=` lo svuota |
| `zbone entry edit b29f --day ieri` | sposta la voce a un altro giorno |
| `zbone entry delete b29f` | elimina la voce, dopo una conferma |

Le date si scrivono `2026-10-17`, `17/10/2026`, `oggi` oppure `ieri`.

## Dove finiscono i dati
Tutto va nel file `zibaldone.db` nella tua cartella dati (`zbone data path`). È un database SQLite: puoi copiarlo per farne una copia di sicurezza a mano, finché non arrivano i backup automatici della v0.0.6.
