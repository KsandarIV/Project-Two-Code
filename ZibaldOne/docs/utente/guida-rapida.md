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

## Modelli pronti
ZibaldOne ha quattro **pacchetti** di modelli già pronti, ognuno con il nome di una scuola filosofica. Installarli non tocca le tue voci e puoi modificarli come i tuoi.

| Pacchetto | Cosa contiene |
|---|---|
| `diario` · Stoa | mattina, metà giornata e sera; il check-in delle 8 aree della vita; pensieri liberi; revisioni di settimana, mese e anno |
| `collezioni` · Museion | libri, film, serie, anime, videogiochi, giochi da tavolo, sport, musica, guardaroba |
| `io` · Delfi | identità, filosofia personale, capitoli di vita, desideri, abitudini |
| `persone` · Agorà | le persone della tua vita e gli incontri con loro |

| Comando | Cosa fa |
|---|---|
| `zbone pack list` | i pacchetti pronti e se sono già installati |
| `zbone pack show diario` | i modelli di un pacchetto, senza installarlo |
| `zbone pack install diario` | mostra cosa cambierà, chiede conferma e installa |

Se hai già un modello con lo stesso nome tecnico, il pacchetto lo installa come copia (`persona_2`) e non tocca il tuo. Se reinstalli lo stesso pacchetto non succede nulla; se il pacchetto è più nuovo, i suoi modelli vengono aggiornati.

Per esempio, la sera:
```powershell
zbone pack install diario
zbone entry add sera
```

## Condividere i tuoi modelli
Un modello che ti piace si può mandare a un amico come file `.zbpack.json`. Il file contiene **solo la struttura** dei modelli (blocchi, etichette, regole): nessuna delle tue voci.

```powershell
zbone pack export libro film --name "Le mie letture" --author Alex   # crea le_mie_letture.zbpack.json
zbone pack show le_mie_letture.zbpack.json                          # chi lo riceve guarda cosa c'è dentro
zbone pack import le_mie_letture.zbpack.json                        # e lo installa, con la conferma
```
| Opzione di `export` | Cosa fa |
|---|---|
| `--output`, `-o` | dove salvare il file |
| `--name` | il nome del pacchetto (di base il nome del modello) |
| `--author` | il tuo nome o nickname |
| `--description` | a cosa serve |
| `--version` | la versione del pacchetto, per esempio `1.1.0` quando lo migliori |
| `--license` | la licenza, di base `CC-BY-4.0` (chi lo usa ti cita) |

Un file più grande di 1 MB, scritto male o con blocchi sconosciuti viene rifiutato prima di toccare qualsiasi cosa. Un pacchetto non contiene codice: non può fare nulla oltre ad aggiungere modelli.

## Storia e backup · Mnemosyne
ZibaldOne salva da solo una copia completa dei tuoi dati una volta al giorno, la prima volta che salvi qualcosa. Ogni copia (un'**istantanea**) è come una foto: puoi tornarci quando vuoi.

| Comando | Cosa fa |
|---|---|
| `zbone backup create --note "prima del trasloco"` | salva subito un'istantanea, con una nota |
| `zbone backup list` | le istantanee, dalla più recente |
| `zbone backup restore fd8a31` | torna a quell'istantanea; prima salva lo stato attuale, così puoi annullare |
| `zbone backup verify` | controlla che l'ultima istantanea sia integra (`--all` tutte) |
| `zbone backup config` | backup automatico e durata (di base 7 giornaliere, 4 settimanali, 12 mensili) |
| `zbone backup prune` | cancella le istantanee scadute (`--dry-run` per vedere prima) |

Le istantanee stanno nella cartella `backups` dentro la cartella dati. Una voce che cancelli resta nelle istantanee finché non scadono. Dettagli: [storia e backup](../tecnica/backup.md).

### Cifrare i backup · Anello di Gige
```powershell
zbone backup setup
```
Scegli una passphrase (almeno 10 caratteri) e scrivi su carta il **codice di recupero** che ZibaldOne ti mostra una volta sola. Da quel momento ogni istantanea è cifrata, anche quelle che c'erano già. I backup automatici non ti chiedono nulla: la passphrase serve solo per ripristinare o verificare.

- `zbone backup passphrase`: cambia la passphrase.
- `zbone backup recover`: hai dimenticato la passphrase? Ne scegli una nuova con il codice di recupero.

Senza passphrase e senza codice di recupero nessuno può aprire i backup, nemmeno chi ha creato l'app.

## Account e copie fuori · Le Nuvole
Al primo avvio ZibaldOne ti chiede di entrare con il tuo **account Google**: si apre il browser, scegli l'account e lasci spuntato Drive. Serve a sapere chi sei su questo dispositivo; il diario resta qui. Poi scegli dove tenere i backup:

| Comando | Dove vanno le copie |
|---|---|
| `zbone cloud use local` | solo su questo dispositivo |
| `zbone cloud use google` | anche sul tuo Google Drive, in uno spazio nascosto dell'app (non vede gli altri tuoi file) |
| `zbone cloud use folder E:\` | anche in una cartella: una chiavetta, o la cartella di OneDrive o Dropbox |

Fuori vanno **solo istantanee cifrate**: prima serve `zbone backup setup`. Dopo, ogni backup automatico viene copiato da solo.

| Comando | Cosa fa |
|---|---|
| `zbone account` | con quale account sei entrato |
| `zbone account logout` | esci da questo dispositivo; diario e backup restano |
| `zbone cloud` | dove vanno le copie e com'è andata l'ultima |
| `zbone cloud sync` | copia adesso |
| `zbone cloud list` | le istantanee che ci sono fuori |
| `zbone cloud recover` | **telefono o PC nuovo**: riporta qui i dati (la più recente, o un ID) |
| `zbone cloud recovery on` | recupero con l'account Google, senza passphrase (vedi sotto) |
| `zbone cloud forget` | cancella tutte le copie fuori e torna a solo locale |

**Recupero con l'account Google.** Quando scegli Drive, ZibaldOne ti propone di poter riavere i backup su un dispositivo nuovo solo entrando con Google, senza passphrase: comodo come in tutte le app. Il prezzo è che chi riesce a entrare nel tuo account Google può aprirli. Se non lo attivi, per il recupero servono la passphrase o il codice di recupero. Lo togli quando vuoi con `zbone cloud recovery off`.

Backup, export e privacy funzionano sempre, anche senza account: riavere i tuoi dati non dipende mai da Google.

## Esportare
- `zbone export markdown`: uno zip con un file per voce, da aprire in Obsidian.
- `zbone export csv`: uno zip con un foglio per modello, da aprire in Excel.

Il file esportato non è cifrato: chi lo apre legge le tue voci.

## Il pensiero del giorno e i nomi
- `zbone pensiero`: una frase di un filosofo, diversa ogni giorno, con la fonte.
- `zbone about`: da dove viene il nome, le mascotte delle 8 aree e i nomi filosofici di ogni parte dell'app ([identità](../brand/identita.md)).

## Dove finiscono i dati
Tutto va nel file `zibaldone.db` nella tua cartella dati (`zbone data path`), un database SQLite. Le istantanee stanno nella sottocartella `backups`. Se scegli Drive o una cartella, lì vanno solo copie cifrate delle istantanee e il file delle chiavi, che senza passphrase (o codice di recupero) non serve a nulla.
