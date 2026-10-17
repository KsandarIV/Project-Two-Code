# Guida rapida

ZibaldOne si usa in due modi, sugli stessi dati:
- **l'app**, con `zbone app` (una finestra) o `zbone app --web` (nel browser); su Android è l'app installata;
- **il terminale**, con il comando `zibaldone` oppure, più corto, `zbone`.

## L'app
Cinque sezioni, nel menu a sinistra sul PC e in basso sul telefono:

| Sezione | Cosa trovi |
|---|---|
| **Oggi** · Hic et nunc | il pensiero del giorno, i 3 momenti (mattina, metà giornata, sera) da scrivere o riaprire, il check-in delle 8 aree e la pagina di ogni area, le voci di oggi, la serie di giorni |
| **Voci** · Pensieri | tutte le voci, con filtri per titolo, modello e date; apri, modifica, cancella |
| **Collezioni** · Museion | libri, film, giochi, viaggi…: le voci dei modelli da collezione, con il loro stato |
| **Modelli** · Forme | i tuoi modelli, l'editor dei blocchi e le **Scuole**, cioè i pacchetti pronti da installare |
| **Impostazioni** · Organon | Parresia (privacy e dati), Daimon (promemoria), Mnemosyne (backup, cifratura e PIN dei segreti), Le Nuvole (account e cloud), Informazioni |

Al primo avvio l'app ti mostra l'avviso sulla privacy, ti fa entrare con Google (se l'app ha un client Google), ti chiede dove tenere i backup e ti propone il pacchetto Stoa · Diario. Dopo ogni salvataggio fa da sola il backup del giorno e la copia fuori, se l'hai scelta. Mentre l'app è aperta, i promemoria compaiono come avviso in alto.

Le pagine si possono aprire direttamente: `zbone app --route /scrivi/sera`.

## Il terminale: comandi di base
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

## Cercare e collegare · Zetesis
| Comando | Cosa fa |
|---|---|
| `zbone search cena lago` | le voci con tutte le parole, in tutti i blocchi; maiuscole e accenti non contano |
| `zbone search "cena al lago"` | la frase esatta |
| `zbone search perch* -lavoro` | parole che cominciano con "perch", senza "lavoro" |
| `zbone search marco --template sera --since 2026-10-01` | solo un modello, solo da un giorno (`--until` fino a un giorno) |
| `zbone search --tag viaggi` | le voci con un'etichetta, dalla più recente |
| `zbone links b29f` | i collegamenti di una voce: chi collega, chi la cita, chi la nomina senza collegarla |

Per collegare una voce a un'altra scrivi il suo titolo tra doppie quadre in un testo, per esempio `Cena con [[Marco]]`: vale il titolo o, per una persona, un soprannome. Se la voce non esiste ancora, il collegamento si fa da solo quando la scrivi. Anche il blocco "collegamento" dei modelli (per esempio "Con chi" nell'incontro) crea un collegamento.

Nell'app: la casella di ricerca in **Voci** usa le stesse regole, e la pagina di una voce mostra chi la cita. Come funziona dentro: [ricerca e collegamenti](../tecnica/ricerca-e-collegamenti.md).

## Il grafo · Rizoma
Tutte le voci e i loro collegamenti, come una mappa. Nell'app: **Voci → Grafo**, oppure **Nel grafo** dalla pagina di una voce; tocca un punto per aprire la voce.

| Comando | Cosa fa |
|---|---|
| `zbone graph` | riepilogo: quante voci e collegamenti, le più collegate, le voci sole |
| `zbone graph --html grafo.html` | una pagina da aprire nel browser, con zoom e nomi |
| `zbone graph --around b29f --depth 2` | solo le voci a due passi da una voce |
| `zbone graph -t persona -t incontro` | solo alcuni modelli (anche `--since`, `--until`, `--tag`) |
| `zbone graph --unresolved` | anche i `[[Titoli]]` che aspettano ancora una voce |
| `zbone graph --tag-nodes --shared-tags` | le etichette come punti, e le voci con etichette in comune collegate |
| `zbone graph --json grafo.json` | nodi, linee e posizioni, per altri programmi |

Come funziona: [il grafo](../tecnica/grafo.md).

## Statistiche e revisioni · Theoria
Come è andata la settimana o il mese: quante voci, l'umore giorno per giorno, le 8 aree, le collezioni in corso, le persone più presenti, le cose ancora da fare. Nell'app: **Oggi → Statistiche**, con le frecce per i periodi passati.

| Comando | Cosa fa |
|---|---|
| `zbone stats` | i numeri di questa settimana (`--month` per il mese, `--date 2026-09-15` per un altro periodo) |
| `zbone stats --html theoria.html` | una pagina con i grafici, da aprire nel browser |
| `zbone review week` | la revisione della settimana, con una proposta già compilata |
| `zbone review month --save` | prepara la revisione del mese e la salva come voce, da completare con `zbone entry edit` |

La proposta è una bozza: il voto viene dai voti alle giornate, l'area su cui concentrarti è la più bassa, gli obiettivi sono le cose ancora aperte, i momenti belli sono presi dalle tue voci. Nell'app il pulsante **Revisione della settimana** fa lo stesso e apre il modulo per completarla. Come funziona: [statistiche e revisioni](../tecnica/statistiche.md).

## Le otto aree · Eudaimonia
Personale, Salute, Finanze, Famiglia, Sociale, Lavoro, Studio e Svago: ogni modello e ogni voce può appartenere a un'area. I libri vanno da soli in Svago, lo sport in Salute, la mamma in Famiglia e il capo in Lavoro; a una voce puoi dare un'altra area. Ogni area ha la sua pagina: il punteggio da 0 a 10 settimana per settimana, le cose da fare, gli obiettivi, le voci, e le novità **in arrivo**. Nell'app: **Oggi → Aree**, oppure tocca un'area in Oggi.

| Comando | Cosa fa |
|---|---|
| `zbone area` | le otto aree a colpo d'occhio, con l'ultimo punteggio |
| `zbone area show salute` | un'area: punteggio nel tempo, cose da fare, obiettivi, voci |
| `zbone area checkin salute -p 7 --bene "dormo di più"` | il check-in di una sola area (Prosoché) |
| `zbone area todo salute prenotare il dentista` | aggiunge una cosa da fare all'area |
| `zbone area fatto salute 1` | spunta la cosa da fare numero 1 di `zbone area show` |
| `zbone entry add obiettivo --area salute` | un obiettivo (Telos) dell'area |
| `zbone entry list --area svago` | le voci di un'area (anche in `zbone search`) |
| `zbone entry edit b29f --area lavoro` | sposta una voce in un'altra area (`--area nessuna` per toglierla) |
| `zbone template area libro studio` | sceglie l'area di tutte le voci di un modello |

Il punteggio viene dal check-in delle 8 aree (Eudaimonia) e dai check-in di una sola area. I modelli per le aree (check-in, obiettivo, cose da fare) sono nella Scuola **Liceo · Aree**: l'app la installa al primo avvio, oppure `zbone pack install aree`. Come funziona: [le 8 aree](../tecnica/aree.md).

## Le persone · Agorà
Per ogni persona scrivi il legame (Famiglia, Amico, Collega …), i ruoli (madre, capo, medico, o uno tuo), telefono, email e ogni quanto vorresti sentirvi. I ruoli la mettono da soli nell'area giusta. Ogni Simposio con lei è un contatto: chiamata, messaggi, un'uscita. Nell'app la trovi nel riquadro **Persone** della sua area, oppure con **Tutto di Marco** dalla sua voce: contatti, ritmo e tutte le voci che la riguardano, area per area.

| Comando | Cosa fa |
|---|---|
| `zbone persona` | le persone con l'ultimo contatto, prima chi è da sentire |
| `zbone persona list --area famiglia` | solo le persone di un'area (`--da-sentire` solo chi è da sentire) |
| `zbone persona show marco` | tutto di Marco: contatti, ritmo, voci per area, chi lo nomina |
| `zbone persona sentito marco --tipo chiamata --nota "il progetto nuovo"` | segna che vi siete sentiti (anche `-d ieri`) |
| `zbone persona lega anna genitore luca` | Anna è genitore di Luca (anche `figlio`, `fratello`, `collega`, `conosce`) |
| `zbone persona albero` | la famiglia generazione per generazione |
| `zbone persona rete` | i legami più forti; `rete marco` chi conosce Marco e chi avete in comune, `--area lavoro` solo un'area |

Nella voce di una persona scrivi anche i suoi **Genitori**, **Fratelli e sorelle**, **Colleghi** e chi **Conosce** tra le tue persone: basta da una parte sola. Con i ruoli (madre, nonno …) l'app disegna l'**Albero** di famiglia; la **Rete** mostra chi conosce chi, anche solo perché vi siete visti insieme. Si aprono dalla pagina della persona o dal riquadro Persone di un'area.

"Da sentire" vuol dire solo che è passato il tempo che hai scelto: nessuna notifica, nessun rimprovero. Come funziona: [le persone](../tecnica/persone.md).

## Modelli pronti
ZibaldOne ha sei **pacchetti** di modelli già pronti, ognuno con il nome di una scuola filosofica. Installarli non tocca le tue voci e puoi modificarli come i tuoi.

| Pacchetto | Cosa contiene |
|---|---|
| `diario` · Stoa | mattina, metà giornata e sera; il check-in delle 8 aree della vita; pensieri liberi; revisioni di settimana, mese e anno |
| `collezioni` · Museion | libri, film, serie, anime, videogiochi, giochi da tavolo, sport, musica, guardaroba |
| `io` · Delfi | identità, filosofia personale, capitoli di vita, desideri, abitudini |
| `persone` · Agorà | le persone della tua vita, con ruoli, contatti e legami (indirizzo e documenti cifrati), e gli incontri con loro |
| `aree` · Liceo | il check-in di una sola area, gli obiettivi e le cose da fare di ogni area |
| `segreti` · Adyton | il diario segreto e le note mediche, cifrati |

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

### I segreti · Arcana
Con la cifratura attiva puoi scrivere **segreti**: il diario segreto (*A se stesso*), le note mediche (*Ippocrate*), l'indirizzo e i documenti di una persona. Si cifrano prima di essere salvati e non entrano mai nella ricerca, nelle esportazioni o nell'IA. Scriverli non chiede nulla; per rileggerli tocca **Apri** nella pagina della voce.

- **Protetto** (il diario, gli indirizzi): si apre con il **PIN** o con la passphrase.
- **Massimo** (documenti, salute): solo con la passphrase.

Il PIN (da 6 a 12 cifre) si sceglie in **Impostazioni · Mnemosyne** o con `zbone segreti pin`; dopo 5 errori di fila si toglie da solo. I segreti si richiudono dopo 5 minuti senza usarli.

| Comando | Cosa fa |
|---|---|
| `zbone pack install segreti` | il diario segreto e le note mediche |
| `zbone entry add diario_segreto` | scrivi senza che il testo si veda |
| `zbone segreti` | quante voci hanno segreti e se il PIN c'è |
| `zbone segreti apri 3f2a` | mostra la voce con i segreti in chiaro, solo sullo schermo |

Come funziona: [i segreti](../tecnica/segreti.md).

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

## Promemoria · Daimon
ZibaldOne ti ricorda di scrivere nei 3 momenti della giornata: mattina (08:30), metà giornata (13:30) e sera (21:30). Un promemoria arriva al massimo una volta per momento, mai se hai già scritto la voce di quel momento e mai nelle ore di silenzio (22:30–08:00). Se ne ignori 3 di fila, ZibaldOne ti propone di diradarli; non li spegne mai da solo. Le notifiche non mostrano mai ciò che scrivi.

| Comando | Cosa fa |
|---|---|
| `zbone remind status` | promemoria, voci di oggi, serie di giorni e suggerimenti |
| `zbone remind config --moment sera --time 22:00` | cambia l'orario di un momento |
| `zbone remind config --moment mattina --off` | spegne un momento (`--on` lo riaccende; senza `--moment` vale per tutti) |
| `zbone remind config --days feriali` | solo dal lunedì al venerdì (anche `weekend`, `lun,mer,ven`, `lun-ven`) |
| `zbone remind config --quiet-start 23:00 --quiet-end 07:30` | ore di silenzio |
| `zbone remind config --moment sera --thin-out` | un giorno sì e uno no |
| `zbone remind test` | una notifica di prova |
| `zbone remind install` | **Windows**: i promemoria arrivano anche ad app chiusa (`uninstall` per toglierli) |

Per le notifiche di sistema sul PC installa il pacchetto facoltativo: `pip install -e ".[notifiche]"`. Senza, il promemoria compare nel terminale.

## Anonimizzatore · Velo d'ignoranza
Prima che un testo arrivi a un'intelligenza artificiale, ZibaldOne toglie nomi, email, telefoni, codici, IBAN, carte e indirizzi e mette dei segnaposto come `[PERSONA_1]`. Tutto qui sul dispositivo. Per ora si può provare; le funzioni di IA arriveranno più avanti e passeranno tutte da qui.

| Comando | Cosa fa |
|---|---|
| `zbone anon preview "Ieri ho visto Giulia, mi ha scritto a giulia@example.com"` | mostra il testo pulito e cosa è stato sostituito |
| `zbone anon preview "…" --mode anon` | anonimato: senza la tabella per tornare indietro |
| `zbone anon eval` | quanto funzionano le regole, su frasi di prova |

I nomi di persona li riconosce dalle tue voci **Persona** (con i soprannomi): più persone hai scritto, meglio funziona. Nell'app: **Impostazioni → Anonimizzatore**. Come funziona: [anonimizzatore](../tecnica/anonimizzatore.md).

## Esportare
- `zbone export markdown`: uno zip con un file per voce, da aprire in Obsidian (le aree della voce sono nelle sue proprietà).
- `zbone export csv`: uno zip con un foglio per modello, da aprire in Excel (con la colonna dell'area).

Il file esportato non è cifrato: chi lo apre legge le tue voci.

## Aggiornamenti
L'app guarda una volta al giorno se è uscita una versione nuova e, se c'è, te lo dice con un pulsante **Scarica**. Chiede solo a GitHub, senza account: GitHub vede l'indirizzo IP e la versione dell'app, nient'altro.

| Comando | Cosa fa |
|---|---|
| `zbone update` | controlla adesso |
| `zbone update --no-auto` | spegne il controllo automatico dell'app (`--auto` lo riaccende) |

Nell'app: **Impostazioni → Informazioni**. Chi prova l'app sul telefono trova i passi nella [guida per i tester](guida-tester.md).

## Il pensiero del giorno e i nomi
- `zbone pensiero`: una frase di un filosofo, diversa ogni giorno, con la fonte.
- `zbone about`: da dove viene il nome, le mascotte delle 8 aree e i nomi filosofici di ogni parte dell'app ([identità](../brand/identita.md)).

## Dove finiscono i dati
Tutto va nel file `zibaldone.db` nella tua cartella dati (`zbone data path`), un database SQLite. Le istantanee stanno nella sottocartella `backups`. Se scegli Drive o una cartella, lì vanno solo copie cifrate delle istantanee e il file delle chiavi, che senza passphrase (o codice di recupero) non serve a nulla.
