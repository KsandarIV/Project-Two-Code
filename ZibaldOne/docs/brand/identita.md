# Identità di ZibaldOne

## Il nome
**ZibaldOne** viene dallo *Zibaldone di pensieri* di Giacomo Leopardi (1817–1832): un quaderno di migliaia di pagine dove trovava posto ogni pensiero, lettura, idea. **One** significa tutto in uno. Il comando è `zibaldone`, in breve `zbone`.

- Motto: *Tutto in uno, un pensiero alla volta.*
- Sottotitolo: *il tuo zibaldone di pensieri, fatto a blocchi.*
- Tono: gentile, curioso, socratico. L'app fa domande più che dare ordini, non colpevolizza, cita le fonti.

## I nomi filosofici
Ogni parte dell'app ha un nome filosofico accanto al nome semplice: l'interfaccia mostra entrambi (per esempio "Aut-Aut · Scelta"). I nomi tecnici dei comandi restano semplici (`zbone entry add sera`). Elenco completo con le fonti: `zbone about` o `src/zibaldone/core/brand.py`.

| Parte | Nome | Fonte |
|---|---|---|
| Blocchi | Atomi | Democrito |
| Modelli | Forme | Platone, Aristotele |
| Voci | Pensieri | Leopardi, Zibaldone; Pascal, Pensieri |
| Pacchetti | Scuole | Stoa, Accademia, Liceo, Giardino |
| Oggi | Hic et nunc | locuzione latina |
| Le 8 aree della vita | Eudaimonia | Aristotele, Etica Nicomachea |
| Ricerca | Zetesis | Sesto Empirico |
| Grafo | Rizoma | Deleuze e Guattari, Mille piani |
| Statistiche | Theoria | greco *theorein*, contemplare |
| Storia e backup | Mnemosyne | dea della memoria; Warburg |
| Cifratura | Anello di Gige | Platone, Repubblica II |
| Anonimizzatore | Velo d'ignoranza | Rawls, Una teoria della giustizia |
| Notifiche | Daimon | Platone, Apologia di Socrate |
| Trasparenza sui dati | Parresia | Foucault |
| Account e cloud | Le Nuvole | Aristofane |
| Impostazioni | Organon | Aristotele |
| IA futura | Maieutica | Platone, Teeteto |

### Tipi di blocco
| Blocco | Nome | Fonte |
|---|---|---|
| text | Aforisma | Ippocrate, Leopardi, Nietzsche |
| longtext | Saggio | Montaigne, Saggi |
| number | Misura | Protagora |
| rating | Giudizio | Kant, Critica del Giudizio |
| tags | Categorie | Aristotele, Categorie |
| date | Chronos | il tempo dei Greci |
| checklist | Regole | Descartes, Discorso sul metodo |
| scale | Giusto mezzo | Aristotele, Etica Nicomachea II |
| choice | Aut-Aut | Kierkegaard |
| progress | Divenire | Eraclito |
| bookmark | Anamnesi | Platone, Menone |
| link | Nesso | Hume |
| favorite | Philia | Aristotele, Etica Nicomachea |
| secret | Echemythia | il silenzio dei pitagorici |
| media | Mimesis | Aristotele, Poetica |

### Pacchetti e modelli pronti
| Pacchetto | Modelli |
|---|---|
| **Stoa · Diario** | Meditazione del mattino (Marco Aurelio), Meriggio (Nietzsche), Esame serale (Seneca), Eudaimonia (8 aree, Aristotele), Pensiero (Leopardi), Hypomnemata (settimana, Foucault), Lettera a Lucilio (mese, Seneca), Almanacco (anno, Leopardi) |
| **Museion · Collezioni** | Biblioteca di Babele (libri, Borges), Caverna (film, Platone), Eterno ritorno (serie, Nietzsche), Anima mundi (anime, Platone), Homo ludens (videogiochi, Huizinga), Alea (giochi da tavolo, Caillois), Mens sana (sport, Giovenale), Armonia delle sfere (musica, pitagorici), Maschera (guardaroba, Pirandello) |
| **Delfi · Io** | Conosci te stesso, Arché (la mia filosofia), Confessioni (capitoli di vita, Agostino), Conatus (desideri, Spinoza), Hexis (abitudini, Aristotele) |
| **Agorà · Persone** | L'Altro (persona, Levinas), Simposio (incontro, Platone) |
| **Liceo · Aree** | Prosoché (check-in di un'area, l'attenzione a sé degli stoici), Telos (obiettivo, Aristotele), Opere e giorni (cose da fare, Esiodo) |
| **Adyton · Segreti** | A se stesso (diario segreto, Marco Aurelio), Ippocrate (note mediche) |
| **Oikonomia · Finanze** | Oikos (conto), Chrematistica (spesa o entrata, Aristotele), Giusto mezzo (budget, Aristotele), Formica (obiettivo di risparmio, la favola), Schuld (debito, Nietzsche), Koinonia (spesa condivisa), Emporio (lista della spesa) |

## Le mascotte
Una per ogni area della vita, più una dell'app (da decidere quale sarà la principale).

| Mascotte | Animale | Area | Da chi viene |
|---|---|---|---|
| Leopy | passero | Personale | Leopardi, *Il passero solitario* |
| Hegy | nottola | Studio | Hegel: la nottola di Minerva vola al crepuscolo |
| Archy | riccio | Lavoro | Archiloco: il riccio sa una sola cosa, ma grande |
| Monty | gatta | Svago | Montaigne, *Saggi* II, 12 |
| Diggy | cane | Salute | Diogene il cinico e la vita semplice |
| Mandy | ape | Finanze | Mandeville, *La favola delle api* |
| Ary | cicogna | Famiglia | Aristotele: la cicogna accudisce i genitori anziani |
| Hobbsy | lupo | Sociale | Hobbes, *homo homini lupus* |
| Zibby | chimera | l'app (proposta) | Platone, *Repubblica* IX: l'anima come creatura composta |

Stile visivo: icone al tratto, luminose, sul tema neon scuro di Alex (sfondo `#0D0E15`, accento `#00E5FF`); ogni mascotte ha il suo colore della palette `CYBER_PALETTE`. I disegni sono da fare.

## Il pensiero del giorno
L'app mostra ogni giorno una citazione breve e famosa, sempre con autore e opera (`zbone pensiero`). Si aggiungono solo citazioni di cui si conosce la fonte.
