# Changelog

Tutte le modifiche rilevanti di ZibaldOne. Formato ispirato a [Keep a Changelog](https://keepachangelog.com/it/1.1.0/), versioni [SemVer](https://semver.org/lang/it/).

## [Unreleased]

## [0.2.7] — 2026-10-24
### Aggiunto
- **Askesis · Abitudini**: pacchetto con i rituali (*Askesis*: ogni giorno o più volte a settimana, con quantità e traguardo facoltativi) e le pratiche (*Praxis*: un giorno segnato). Hexis, l'abitudine a testo libero di Delfi · Io, resta com'è.
- **Serie** di giorni di fila (o di settimane che raggiungono le volte volute); oggi non ancora segnato non spezza la serie. Il tono è neutro: numeri, mai rimproveri.
- Riquadro «Abitudini di oggi» in Oggi, schermata `/abitudini` (serie attuale e più lunga, ultimi 7 giorni, nuovo rituale) e riga nella pagina dell'area.
- `zbone abitudini` (da fare oggi e serie), `abitudini segna NOME [QUANTITÀ] [--giorno]`, `togli`, `serie`.
### Cambiato
- «In arrivo»: le abitudini escono; gli **obiettivi con traguardi** slittano alla 0.2.8.
### Documentazione
- [Le abitudini](docs/tecnica/abitudini.md); roadmap, requisiti, interfaccia e aree aggiornati; contratto Backend↔Frontend in `team/handoffs/`.

## [0.2.6] — 2026-10-24
### Aggiunto
- **Oikonomia · Finanze**: pacchetto con conti (*Oikos*), movimenti (*Chrematistica*), budget (*Giusto mezzo*), obiettivi di risparmio (*Formica*), debiti e crediti con le persone (*Schuld*), spese ricorrenti condivise (*Koinonia*) e liste della spesa (*Emporio*).
- **Il bilancio** (`/finanze`, da Aree → Finanze): saldo, mese per categoria con i budget, obiettivi, debiti e crediti, spese condivise da registrare, liste della spesa; **Spesa** ed **Entrata** rapide. Gli importi si leggono solo dopo il PIN.
- `zbone finanze` (riepilogo), `finanze spesa`, `entrata`, `debiti`, `salda`, `ricorrenti [--registra]`.
- Opzione `format` (`importo` o `saldo`) dei blocchi segreti: l'importo si normalizza (`1.234,50` → `1234.50`) prima di cifrare.
- Le mascotte disegnate da Alex (SVG) negli avatar.
### Documentazione
- [Le finanze](docs/tecnica/finanze.md), [ADR-0013](docs/decisioni/ADR-0013-importi-come-segreti.md); roadmap, requisiti, aree, blocchi, guida rapida, interfaccia e identità aggiornati.

## [0.2.5] — 2026-10-17
### Aggiunto
- **Voto a mezzi punti**: l'opzione `half` del voto a stelle (`4,5`); nel modulo la stella si tocca intera, poi mezza, poi si toglie.
- **Recensione con spoiler**: l'opzione `spoiler` del testo lungo nasconde il testo nella pagina della voce finché non lo apri.
- **Blocco Preferito** (*Philia*): un cuore per le cose a cui tieni di più.
- **Inizio e fine** dell'avanzamento: si scrivono da soli quando lo stato cambia, e si leggono nella pagina della voce.
- **Collezioni**: i riquadri *Preferiti*, *Lista dei desideri* e *Tempo speso* (somma dei blocchi in ore o minuti per raccolta).
- **Importa da un file** (Collezioni, o `zbone importa FONTE FILE [--prova]`): libri da Goodreads, film da Letterboxd, anime da MyAnimeList, videogiochi da Steam, con anteprima, date del file e senza doppioni.
### Cambiato
- Museion · Collezioni 1.2.0: mezzi punti nel voto, *Preferito*, *Recensione con spoiler* e le ore (*Ore di lettura*, *Ore di visione*, *Ore di gioco*) dove servono. Le voci di prima restano valide.
- `Store.add_entry` ha `stamp=False` per chi porta voci con date proprie.
### Corretto
- Un test dei backup con gli allegati dipendeva dall'ordine di due istantanee fatte nello stesso secondo.
### Documentazione
- [Svago avanzato](docs/tecnica/svago.md); blocchi, guida rapida, identità, aree, interfaccia, roadmap e requisiti aggiornati.

## [0.2.4] — 2026-10-17
### Aggiunto
- **Blocco Allegati** (*Mimesis*): foto, video, audio e documenti di una voce, scelti con la finestra del sistema. Nella pagina della voce le foto in miniatura, gli altri file con **Apri** (sul telefono dal menu Condividi).
- I file stanno nella cartella `media/`, una volta sola per contenuto (fino a 100 MB l'uno); quelli che nessuna voce usa più si cancellano da soli.
- **Backup**: una copia di ogni allegato accanto alle istantanee, cifrata con la cifratura attiva; verifica e ripristino li controllano e li rimettono. **Le Nuvole** li caricano e li riportano su un dispositivo nuovo.
- `zbone allegati` (stato), `allegati aggiungi`, `mostra`, `salva`, `togli`.
### Cambiato
- Stoa · Diario 1.1.0: *Foto del giorno* nell'Esame serale, *Allegati* nel Pensiero. Agorà · Persone 1.5.0: *Foto e file* nella Persona, *Foto* nel Simposio. Le voci di prima restano valide.
- `zbone entry add` salta i blocchi allegati.
### Documentazione
- [Gli allegati](docs/tecnica/allegati.md); backup, privacy, blocchi, guida rapida, persone, aree, interfaccia, identità, roadmap e requisiti aggiornati.

## [0.2.3] — 2026-10-17
### Aggiunto
- **Blocco Segreto** (*Echemythia*): un testo cifrato con la tua chiave prima di essere salvato, con la stessa cifratura dei backup. Due livelli: *protetto* (si apre con il PIN o la passphrase) e *massimo* (solo con la passphrase o il codice di recupero).
- **PIN** dei segreti (6–12 cifre): apre solo il livello protetto e si toglie da solo dopo 5 errori di fila.
- App: i segreti chiusi con **Apri** nella pagina della voce, che si richiudono da soli dopo 5 minuti; nel modulo un campo segreto lasciato vuoto resta com'è; il riquadro **Segreti · Arcana** in Impostazioni · Mnemosyne (PIN, apri e chiudi).
- Nuova Scuola **Adyton · Segreti** (`segreti`): *A se stesso*, il diario segreto, e *Ippocrate*, le note mediche.
- `zbone segreti` (stato), `segreti pin [--togli]`, `segreti apri [ID]`.
### Cambiato
- Agorà · Persone 1.4.0: L'Altro ha Indirizzo (protetto), Documenti e Salute (massimo). Le voci di prima restano valide.
- I segreti restano fuori da ricerca, collegamenti, statistiche, esportazioni e anonimizzatore: ovunque si legge «🔒 cifrato». `zbone entry show` non li mostra; `entry add` li chiede senza farli vedere.
- «In arrivo» in Personale: lo sblocco con l'impronta, più avanti.
### Documentazione
- [I segreti](docs/tecnica/segreti.md) e [ADR-0012](docs/decisioni/ADR-0012-blocchi-segreti.md); guida rapida, blocchi, persone, aree, privacy, interfaccia, roadmap e requisiti aggiornati.

## [0.2.2] — 2026-10-17
### Aggiunto
- **Legami tra persone**: Genitori, Fratelli e sorelle, Colleghi e Conosce nella Persona; ogni legame vale nei due sensi (i genitori di Luca hanno Luca tra i figli). Chi incontri nello stesso Simposio si lega da solo.
- **Albero di famiglia** (`/albero`): generazione per generazione intorno a te, dai ruoli (madre, nonno, figlia …) e dai Genitori e Fratelli scritti nelle persone.
- **Rete** (`/rete`, `/rete/<area>`): chi conosce chi, disegnato come il grafo e toccabile; per area, così Lavoro mostra chi lavora con chi.
- **Contatti in comune** e **forza del legame** (0–10, da quanto spesso e quanto di recente vi sentite, e dall'umore degli incontri): nella pagina della persona, nella rete e in `zbone persona show`.
- `zbone persona albero`, `zbone persona rete [NOME] [--area]`, `zbone persona lega ANNA genitore LUCA`.
### Cambiato
- Agorà · Persone 1.3.0: L'Altro ha i quattro blocchi dei legami. Le voci di prima restano valide.
- "Tutto di Marco" non elenca più le altre persone tra le voci che lo collegano: sono nei suoi Legami.
### Documentazione
- [Le persone](docs/tecnica/persone.md) con legami, albero e rete; guida rapida, aree, interfaccia, roadmap e requisiti aggiornati.

## [0.2.1] — 2026-10-17
### Aggiunto
- **Persone complete** (Agorà): legame e ruoli di base o tuoi (madre, capo, medico …) che mettono la persona nelle aree giuste da soli; telefono ed email controllati mentre li scrivi; social; "ogni quanto sentirvi".
- Contatti: ogni Simposio con la persona, con il nuovo blocco **Come** (chiamata, messaggi, uscita, visita …); ultimo contatto, ritmo medio e chi è "da sentire", in parole neutre e senza notifiche.
- **Tutto di Marco**: la pagina di una persona (`/persone/<id>`) con contatti, segna-contatto al volo (Chiamata, Messaggi, Di persona) e tutte le voci che la collegano, raggruppate per area; dalla voce Persona e dal nuovo riquadro **Persone** nelle pagine delle aree.
- `zbone persona` (`list`, `show`, `sentito`).
- Blocco testo: opzione `format` (`email`, `telefono`).
### Cambiato
- Agorà · Persone 1.2.0: L'Altro ha Ruoli, Telefono, Email, Social e Ogni quanto sentirvi ("Ruolo" ora si chiama Legame); Simposio ha Come. Le voci di prima restano valide.
- L'area del modello vale solo quando una voce non ne ha altre; l'indice delle aree si ricostruisce da solo all'apertura. Nei CSV la colonna `area` è l'area principale della voce.
### Documentazione
- [Le persone](docs/tecnica/persone.md); guida rapida, aree, blocchi, roadmap, requisiti e ADR-0011 aggiornati.

## [0.2.0] — 2026-10-17
### Aggiunto
- **Le 8 aree della vita** (Eudaimonia) come concetto dell'app: ogni modello e ogni voce può appartenere a un'area (Personale, Salute, Finanze, Famiglia, Sociale, Lavoro, Studio, Svago). L'area della voce vince su quella del modello; un blocco etichette `aree` mette una voce in più aree.
- Per ogni area: punteggio da 0 a 10 settimana per settimana con la tendenza, cose da fare (anche dalle liste delle sue voci), obiettivi, check-in, note e voci.
- App: **Oggi → Aree** e la pagina di ogni area (`/aree`, `/aree/<area>`), con la mascotte, il grafico, le cose da spuntare e aggiungere, gli obiettivi; Check-in, Obiettivo e Nota con l'area già scelta. Filtro per area in Voci, aree nella pagina di una voce, area nell'editor dei modelli.
- **«In arrivo»**: le pagine delle aree mostrano le funzioni delle prossime versioni (persone, albero genealogico, diario segreto, finanze, abitudini, la home su misura …) con la versione prevista.
- Nuova Scuola **Liceo · Aree** (`aree`): Prosoché (check-in di un'area), Telos (obiettivo), Opere e giorni (cose da fare). Il primo avvio la installa con Stoa · Diario.
- `zbone area` (le otto aree), `area show`, `area checkin`, `area todo`, `area fatto`; `--area` in `entry add/list/edit`, `template create` e `search`; `zbone template area`.
- Esportazioni: `areas:` nelle proprietà Markdown e la colonna `area` nei CSV.
- **Registro dei temi** in `core/brand.py` (dal team multi-thread): un tema è nomi, mascotte e citazioni; Filosofia è il tema di base e tutto funziona come prima. Aggiungere un tema è una sola `register_theme(...)`; l'app non sceglie ancora il tema.
### Cambiato
- Database, schema 3: colonna `area` nelle voci e indice `entry_areas`, riempiti da soli all'aggiornamento (con un backup prima).
- Collezioni, Io e Persone 1.1.0: i loro modelli hanno un'area (Svago, Salute, Personale, Sociale).
- Mascotte rinominate: Diggy (Salute), Ary (Famiglia), Hobbsy (Sociale).
### Documentazione
- [Le 8 aree](docs/tecnica/aree.md) e [ADR-0011](docs/decisioni/ADR-0011-aree-della-vita.md); guida rapida, roadmap, requisiti della fase 0.2, interfaccia e identità aggiornate.
- Cartella `team/`: stato, compiti e consegne del team multi-thread.

## [0.1.5] — 2026-10-17
### Aggiunto
- **Anonimizzatore** (Velo d'ignoranza), tutto locale: toglie nomi di persona (dalle voci Persona, con i soprannomi), email, telefoni, codice fiscale, partita IVA, IBAN, carte, URL, indirizzi IP e stradali, date di nascita, e mette segnaposto coerenti come `[PERSONA_1]`.
- Due modalità: pseudonimi reversibili (la tabella resta in memoria, per riportare la risposta di un modello ai nomi veri) e anonimato.
- Controlli veri dove esistono: codice fiscale, partita IVA, IBAN (mod 97), carte (Luhn).
- `zbone anon preview` e `zbone anon eval` (precisione e richiamo per tipo, su 92 frasi di prova: 96,7% e 95,6%).
- App: **Impostazioni → Anonimizzatore**, per provarlo su un testo o sull'ultima voce, senza salvare né inviare nulla.
### Documentazione
- [Anonimizzatore](docs/tecnica/anonimizzatore.md); guida rapida, privacy, interfaccia e ADR-0009 aggiornati.

## [0.1.4] — 2026-10-17
### Aggiunto
- **Statistiche** (Theoria) di una settimana o di un mese: scrittura e giorni di fila, umore da 1 a 5 giorno per giorno con la tendenza, medie delle 8 aree e degli altri punteggi, collezioni in corso e completate, persone più presenti, cose ancora aperte. Tutto riconosciuto dal tipo di blocco, quindi anche nei modelli fatti da te.
- **Revisione già compilata** della settimana (Hypomnemata) o del mese (Lettera a Lucilio): voto, area su cui concentrarsi, obiettivi dalle cose aperte, momenti belli e cose imparate dalle voci del periodo. Una bozza da rileggere, una per periodo.
- App: **Oggi → Statistiche**, settimana o mese con le frecce per i periodi passati, e il pulsante per preparare la revisione e completarla.
- `zbone stats` e `zbone review week|month` (`--save`, `--html` per una pagina con i grafici).
### Documentazione
- [Statistiche e revisioni](docs/tecnica/statistiche.md); guida rapida, blocchi e interfaccia aggiornati.

## [0.1.3] — 2026-10-17
### Aggiunto
- **Grafo** (Rizoma) delle voci e dei collegamenti, come in Obsidian: punti colorati per modello e grandi quanto i loro collegamenti, disposizione sempre uguale per gli stessi dati.
- App: schermata **Grafo** (da Voci, o **Nel grafo** dalla pagina di una voce per vederne i dintorni a 1–3 passi); filtri per modello, voci senza collegamenti e `[[Titoli]]` senza voce; si tocca un punto per aprire la voce; le voci più collegate in elenco.
- `zbone graph`: riepilogo, pagina HTML da aprire nel browser (`--html`, con zoom e nomi), dati in JSON (`--json`); filtri per modello, date, etichetta e dintorni di una voce; etichette e modelli come nodi su richiesta.
### Documentazione
- [Il grafo](docs/tecnica/grafo.md); guida rapida e interfaccia aggiornate; in [rilascio Android](docs/sviluppo/rilascio-android.md) cosa finisce dentro l'APK (Python 3.14, pacchetti dall'indice di Flet).

## [0.1.2] — 2026-10-17
### Aggiunto
- **Ricerca** (Zetesis) in tutti i blocchi delle voci: più parole insieme, "frase esatta", `parol*`, `-parola`; maiuscole e accenti non contano. Filtri per modello, etichetta e date. `zbone search`.
- Con SQLite FTS5 i risultati sono ordinati per pertinenza (titolo ed etichette pesano di più); senza FTS5 (alcuni Android) la stessa ricerca gira in modo semplice e lo dice.
- **Collegamenti** tra voci: dai blocchi "collegamento" e da `[[Titolo]]` nei testi (vale anche il soprannome di una persona). Un `[[Titolo]]` senza voce si collega da solo quando la voce nasce.
- `zbone links <id>`: chi collega, chi la cita e chi la nomina senza collegarla ("tutto su Marco").
- App: la casella di **Voci** cerca in tutti i blocchi e mostra il pezzo trovato; la pagina di una voce mostra **Citata da** e **La nominano senza collegamento**.
### Cambiato
- Database, schema 2: indici di ricerca, etichette, nomi e collegamenti, riempiti da soli all'aggiornamento (con un backup prima) e riparati all'apertura se non corrispondono alle voci.
### Documentazione
- [Ricerca e collegamenti](docs/tecnica/ricerca-e-collegamenti.md); guida rapida, architettura, blocchi e interfaccia aggiornate.

## [0.1.1] — 2026-10-17
### Aggiunto
- **Prima versione per i tester**: GitHub Actions costruisce l'APK Android a ogni tag `zibaldone-v*` (test prima, firma con la chiave della repo, client Google dai segreti) e lo allega a una *pre-release*.
- **Controllo degli aggiornamenti**: l'interfaccia chiede a GitHub una volta al giorno se c'è una versione nuova e lo dice con un avviso e il pulsante Scarica (su Android apre l'APK). In Impostazioni → Informazioni si spegne o si chiede subito.
- `zbone update` per controllare dalla CLI; `zbone update --auto/--no-auto` accende o spegne il controllo dell'app.
- `src/main.py` e la sezione `[tool.flet]` del `pyproject.toml` per `flet build`; pacchetto facoltativo `zibaldone[build]`.
### Cambiato
- Avviso privacy versione 5: dice del controllo degli aggiornamenti e di cosa vede GitHub (indirizzo IP e versione dell'app). Chi aveva accettato lo rivede una volta.
- I test non vanno mai in rete: il client HTTP vero risponde come se non ci fosse connessione.
### Documentazione
- [Guida per chi prova ZibaldOne](docs/utente/guida-tester.md): installare l'APK, primo avvio, dati, aggiornare, feedback.
- [Rilascio Android](docs/sviluppo/rilascio-android.md): chiave di firma, segreti della repo, come far uscire una versione.
- Distribuzione, privacy e ADR-0003 aggiornati.

## [0.1.0] — 2026-10-17
### Aggiunto
- **Interfaccia grafica** con Flet 1.0.4 e tema scuro neon, la stessa per Windows e Android: si apre con `zbone app` (finestra) o `zbone app --web` (browser).
- Cinque sezioni: Oggi (Hic et nunc), Voci (Pensieri), Collezioni (Museion), Modelli (Forme) con le Scuole, Impostazioni (Organon). Menu laterale sul PC e barra in basso sul telefono, che cambia da sola con la larghezza.
- Oggi: pensiero del giorno, i 3 momenti da scrivere o riaprire, check-in delle 8 aree, voci di oggi, serie di giorni.
- Moduli per ogni tipo di blocco, editor dei modelli, installazione dei pacchetti con il piano dei cambiamenti.
- Primo avvio guidato: avviso privacy, accesso con Google, dove tenere i backup, pacchetto Stoa · Diario.
- Organon: privacy e dati, promemoria, backup e cifratura (con codice di recupero), account e cloud, recupero da Drive o da una cartella.
- Backup del giorno e copia fuori dopo ogni salvataggio; promemoria come avviso in app mentre è aperta.
- Pacchetti facoltativi `zibaldone[ui]` e `zibaldone[web]`, con Flet fissato alla 1.0.4.
### Documentazione
- [Interfaccia grafica](docs/tecnica/interfaccia.md): struttura, regole, come aggiungere una schermata; guida rapida con l'app; immagini nel README.

## [0.0.9] — 2026-10-17
### Aggiunto
- **Promemoria** (Daimon) per i 3 momenti della giornata: mattina 08:30, metà giornata 13:30, sera 21:30, con giorni della settimana e ore di silenzio (22:30–08:00).
- Al massimo un promemoria per momento al giorno, mai se la voce di quel momento è già scritta; un controllo in ritardo lo manda comunque una volta, dentro la sua finestra.
- Dopo 3 promemoria ignorati di fila, ZibaldOne propone di diradarli (`--thin-out`) o di lasciarli come sono (`--keep`).
- Messaggi brevi e gentili, che ruotano; la serie di giorni si festeggia e perderla non porta rimproveri. Le notifiche non contengono mai ciò che scrivi.
- `zbone remind status/config/fire/test`.
- `zbone remind install/uninstall` su Windows: attività pianificate, così i promemoria arrivano anche ad app chiusa.
- Notifiche di sistema con il pacchetto facoltativo `zibaldone[notifiche]` (desktop-notifier); senza, il promemoria compare nel terminale.
### Cambiato
- Avviso privacy versione 4: le notifiche si vedono a schermo bloccato. Chi aveva accettato lo rivede una volta.
- Roadmap: le notifiche passano prima dell'interfaccia, che le usa. Interfaccia grafica ora 0.1.0, prima versione per i tester 0.1.1.
### Corretto
- Pacchetto Stoa · Diario 1.0.1: "Voto alla settimana" e "Obiettivi per la prossima settimana" (prima "al settimana", "il prossimo settimana"). Per aggiornarli: `zbone pack install diario`.
### Documentazione
- Guida rapida con i promemoria; ADR-0008 con le scelte fatte.

## [0.0.8] — 2026-10-17
### Aggiunto
- **Account e copie fuori** (Le Nuvole): `zbone account login/logout` con Google (OAuth per app desktop, PKCE, ritorno su 127.0.0.1) e `zbone account` per vedere chi sei.
- Al primo avvio l'accesso con Google è obbligatorio per usare il diario, quando l'app ha un client Google configurato; senza client resta tutto locale. Backup, export e privacy non chiedono mai l'accesso.
- Tre modalità: `zbone cloud use local`, `google` (spazio nascosto dell'app su Drive, ambito `drive.appdata`) o `folder PERCORSO` (chiavetta, OneDrive, Dropbox…).
- Dopo ogni backup automatico (e dopo `backup create`, `setup`, `passphrase`, `recover`) le istantanee cifrate nuove vengono copiate sulla destinazione, con la stessa durata del dispositivo. Le istantanee in chiaro non escono mai.
- `zbone cloud`, `cloud sync`, `cloud list`, `cloud forget`.
- **Dispositivo nuovo**: `zbone cloud recover [ID]` riporta i dati con passphrase, codice di recupero (`--code`) o account Google.
- **Recupero con l'account Google**, facoltativo: `zbone cloud recovery on/off`, proposto quando scegli Drive, con il compromesso spiegato.
- Token Google in `account-token.json`, protetti con DPAPI su Windows; mai in `settings.json`.
### Cambiato
- Avviso privacy versione 3: account Google e copie su Drive. Chi aveva accettato lo rivede una volta.
### Documentazione
- [Creare il client OAuth di Google](docs/sviluppo/google-cloud.md), passo passo e gratis in modalità test.
- [Copie fuori dal dispositivo](docs/tecnica/backup.md#copie-fuori-dal-dispositivo--le-nuvole-dalla-008); guida rapida con Le Nuvole; ADR-0007 con le scelte fatte.

## [0.0.7] — 2026-10-17
### Aggiunto
- **Cifratura dei backup** (Anello di Gige): `zbone backup setup` con passphrase e codice di recupero; da lì ogni istantanea è cifrata (X25519 + AES-256-GCM) e quelle già fatte vengono cifrate al loro posto.
- I backup automatici non chiedono la passphrase: cifrano con la chiave pubblica.
- `zbone backup passphrase` (cambia passphrase) e `zbone backup recover` (nuova passphrase con il codice di recupero).
- `zbone backup list --details` mostra note e contenuto delle istantanee cifrate, dopo la passphrase.
- Un'istantanea cifrata copiata altrove si apre con il solo codice di recupero, anche senza `keys.json`.
### Cambiato
- L'avviso privacy dice che il database resta in chiaro e che i backup si cifrano con `zbone backup setup`. È un rischio che si riduce, quindi non serve accettarlo di nuovo.
### Documentazione
- [Cifratura](docs/tecnica/backup.md#cifratura--anello-di-gige-dalla-007): chiavi, formato dei file, codice di recupero, limiti noti; ADR-0006 aggiornato.

## [0.0.6] — 2026-10-17
### Aggiunto
- **Storia e backup** (Mnemosyne): istantanee complete dei dati come commit, in `backups/` nella cartella dati.
- Un'istantanea automatica al giorno, dopo il primo comando che salva qualcosa, e una prima di ogni aggiornamento del database. Se non riesce, un avviso giallo; il comando che hai lanciato non fallisce.
- `zbone backup create/list/restore/verify/prune/config`. Il ripristino salva prima lo stato attuale, così si può annullare.
- Durata a tempo come restic: di base 7 giornaliere, 4 settimanali, 12 mensili.
- Verifica: impronta SHA-256, integrità di SQLite, versione dello schema.
- `zbone export markdown` (un file per voce, per Obsidian) e `zbone export csv` (un foglio per modello), dentro uno zip.
- Il motore di cifratura è già nel codice (`core/crypto.py`, `storage/keys.py`) ma si attiva con i comandi della 0.0.7.
### Cambiato
- **Nuova numerazione** ([ADR-0010](docs/decisioni/ADR-0010-numerazione-delle-versioni.md)): tutto scende di un livello (0.N → 0.0.N, 1.N → 0.1.N, "v2" → 0.2) e la 1.0 è l'app davvero usabile. Commit, tag e note delle versioni già fatte sono stati rinumerati.
- Avviso privacy versione 2: dice che le istantanee conservano anche le voci cancellate finché non scadono. Chi aveva accettato lo rivede una volta.
- Nuova dipendenza: `cryptography`.
### Corretto
- Nella guida rapida mancava il titolo della sezione sul pensiero del giorno.
### Documentazione
- [Storia e backup](docs/tecnica/backup.md); guida rapida con backup ed export; roadmap con la [strada verso la 1.0](docs/tecnica/roadmap.md#verso-la-10).

## [0.0.5] — 2026-10-17
### Aggiunto
- `zbone pack export`: salva uno o più modelli in un file `.zbpack.json` da condividere, con nome, autore, versione e licenza. Contiene solo la struttura, mai le voci.
- `zbone pack import`: installa un pacchetto ricevuto, con lo stesso piano e la stessa conferma di `pack install`.
- File di pacchetto controllati prima di tutto: massimo 1 MB, formato 1, campi conosciuti, blocchi esistenti.
- `scripts/version_watch.py`: resta acceso e, quando cambia `__version__`, aggiorna CHANGELOG e nota, fa commit e tag da solo. Il push si attiva con `--push`.
### Documentazione
- [Versionamento automatico](docs/sviluppo/versionamento.md): il watcher, il rilascio a mano, le regole.
- [Guida rapida](docs/utente/guida-rapida.md): condividere i modelli.

## [0.0.4] — 2026-10-17
### Aggiunto
- **Pacchetti integrati** con nomi di scuole filosofiche: `diario` (Stoa, 8 modelli), `collezioni` (Museion, 9), `io` (Delfi, 5), `persone` (Agorà, 2). Riprendono le idee della vecchia Journal App come modelli modificabili.
- `zbone pack list`, `zbone pack show`, `zbone pack install`: prima di installare mostra cosa cambierà (nuovo, aggiornato, già presente, copia) e chiede conferma.
- Un modello dell'utente con lo stesso nome tecnico non viene mai sovrascritto: il pacchetto lo installa come copia.
- Ogni modello installato ricorda da quale pacchetto e versione viene.
- **Identità**: nomi filosofici per blocchi, modelli e parti dell'app (per esempio "Aut-Aut · Scelta"), 8 mascotte, una per area della vita, più una proposta per l'app.
- `zbone pensiero` (una frase di un filosofo al giorno, con la fonte) e `zbone about`.
- Dopo il consenso l'app suggerisce `zbone pack install diario`.
### Documentazione
- [Identità](docs/brand/identita.md): nome, tono, nomi filosofici con le fonti, mascotte.
- [Guida rapida](docs/utente/guida-rapida.md) con i modelli pronti.

## [0.0.3] — 2026-10-17
### Aggiunto
- **Blocchi**: 12 tipi con regole e messaggi in italiano: `text`, `longtext`, `number`, `rating`, `tags`, `date`, `checklist`, `scale`, `choice`, `progress`, `bookmark`, `link`. Quelli previsti per la v0.0.4 sono arrivati già qui.
- **Modelli** (`BlockSpec`, `Template`) e **voci** (`Entry`) che si trasformano in JSON e ritorno senza perdere nulla e rifiutano i campi sconosciuti.
- Database SQLite `zibaldone.db` nella cartella dati, con migrazioni che si possono solo aggiungere (`PRAGMA user_version`).
- `zbone template create/list/show/delete/blocks`: modelli con le domande, in una riga (`--block`, `--option`) o da file JSON.
- `zbone entry add/list/show/edit/delete`: voci con le domande o con `--set`, filtri per modello e giorno, id abbreviati, collegamenti per titolo.
- Date scritte come `2026-10-17`, `17/10/2026`, `oggi`, `ieri`.
- `scripts/release.py`: rilascio di una versione (test, CHANGELOG, nota, commit e tag `zibaldone-vX.Y.Z`).
- La versione si scrive in un solo posto, `src/zibaldone/__init__.py`; `pyproject.toml` la legge da lì.
### Documentazione
- Requisiti di privacy, sicurezza e conformità ([ADR-0002](docs/decisioni/ADR-0002-local-first-e-privacy.md)).
- Piano di distribuzione e aggiornamenti per i tester ([ADR-0003](docs/decisioni/ADR-0003-distribuzione-e-aggiornamenti.md)).
- Interfaccia con Flet e dati in SQLite ([ADR-0004](docs/decisioni/ADR-0004-flet-e-sqlite.md)).
- Pacchetti di modelli condivisibili tra utenti, modelli pronti e futuri consigli nello stesso formato ([ADR-0005](docs/decisioni/ADR-0005-pacchetti-di-modelli.md)); roadmap aggiornata.
- Storia dei dati e backup cifrati a tempo, anche fuori dal dispositivo e leggibili solo dall'utente ([ADR-0006](docs/decisioni/ADR-0006-storia-e-backup-cifrati.md)).
- Accesso con Google obbligatorio, scelta tra solo locale e locale + Google Drive, destinazioni cloud intercambiabili ([ADR-0007](docs/decisioni/ADR-0007-account-google-e-destinazioni-cloud.md)).
- Setup Windows/PowerShell; parti IA rinviate.
- [Visione](docs/tecnica/visione.md): tutto in uno a moduli (diario, collezioni, documenti, finanze, password via Bitwarden, grafo, raccomandazioni), Windows + Android + Linux futuro, sincronizzazione PC ↔ telefono.
- [Roadmap fino alla v0.1.5](docs/tecnica/roadmap.md) e [confronto con la vecchia Journal App](docs/tecnica/confronto-journal-app.md).
- Notifiche che spronano a scrivere ([ADR-0008](docs/decisioni/ADR-0008-notifiche.md)) e anonimizzatore per i futuri modelli di IA ([ADR-0009](docs/decisioni/ADR-0009-anonimizzatore.md)).
- [Requisiti dello sprint v0.2](docs/tecnica/requisiti-v0.2.md) dai documenti della vecchia Journal App (8 aree).
- [Guida rapida](docs/utente/guida-rapida.md) con modelli e voci; [riferimento dei blocchi](docs/tecnica/blocchi.md); dati e migrazioni in [architettura](docs/tecnica/architettura.md).

## [0.0.2] — 2026-10-17
### Aggiunto
- Cartella dati per piattaforma (`%APPDATA%\ZibaldOne` su Windows), sostituibile con la variabile `ZIBALDONE_HOME`.
- Avviso privacy al primo avvio con consenso esplicito (sì/no); se rifiuti non viene salvato nulla.
- `zbone privacy`: avviso, cartella, spazio usato e stato del consenso. `zbone privacy accept` e `zbone privacy revoke`.
- `zbone data path`: stampa il percorso della cartella dati.
- `settings.json` con `schema_version`, scritto in modo atomico.
- Test della privacy e del salvataggio, sempre in una cartella temporanea.

## [0.0.1] — 2026-10-17
### Aggiunto
- Scheletro del progetto: pacchetto `zibaldone` in `src/`, `pyproject.toml`.
- CLI con due nomi: `zibaldone` e l'alias corto `zbone`.
- Comandi `help` (elenca tutti i comandi) e `version`.
- Test della CLI con pytest.
- Struttura `docs/` con guida utente, architettura, decisioni, note di versione e setup su Windows.
