# ADR-0013 — Gli importi delle finanze sono segreti cifrati, sommati solo in memoria

- **Data**: 2026-10-24 · **Stato**: accettata (richiesta di Alex, fase 0.2, v0.2.6)
- **Contesto**: le finanze sono il modulo più delicato dello sprint ([requisiti](../tecnica/requisiti-v0.2.md)). Un saldo, uno stipendio o un debito con un amico non devono finire nella ricerca, nelle esportazioni, nelle statistiche o in un'IA. Eppure servono somme: saldo, spese del mese per categoria, budget, obiettivi.
- **Decisione**:
  - **Ogni importo è un blocco `secret`** ([ADR-0012](ADR-0012-blocchi-segreti.md)) al livello *protetto*, con l'opzione `format`: `importo` (zero o più) o `saldo` (può essere negativo). Si salva come `1234.50` cifrato; il Database lo normalizza prima di cifrare, quindi `12,5`, `€ 1.234,50` e `12.50` valgono come si legge.
  - **Le parole restano in chiaro**: che cosa, giorno, categoria, conto, persona. Così si cercano, si collegano e finiscono nel grafo; i numeri no.
  - **Le somme si fanno in memoria**: la schermata `/finanze` e `zbone finanze` aprono i segreti con il PIN, caricano le voci, sommano con `Decimal` (due decimali) e non scrivono nulla. Nessuna tabella di totali, nessuna cache su disco.
  - **Scrivere non chiede il PIN** (bastano le chiavi pubbliche): spesa e entrata rapide si scrivono da subito, leggere i totali chiede il PIN.
  - **Spese condivise**: pago sempre io. «Registra» scrive la mia quota come spesa e un debito «Mi deve» per ogni altra persona; il totale si divide in parti uguali al centesimo e il resto va a me.
  - **Debiti e crediti** sono voci a sé, collegate a una persona (compaiono nella sua pagina) e non entrano nel saldo: segnarli saldati non tocca i conti.
- **Conseguenze**:
  - Serve la cifratura dei backup attiva: senza, l'app lo dice e rimanda a Mnemosyne.
  - Con tanti movimenti aprire la schermata decifra tutto ogni volta: scrypt non c'entra (il PIN si controlla una volta), il costo è un AES-GCM per importo, trascurabile fino a decine di migliaia di voci. Se servisse, si potrà tenere una cache in memoria finché il caveau è aperto.
  - Nei backup, nelle Nuvole e nelle esportazioni gli importi viaggiano solo cifrati; un'esportazione CSV dei movimenti mostra «🔒 cifrato» al posto del numero.
  - Importi in una sola valuta (euro): le altre valute restano fuori dalla 0.2.
- **Alternative scartate**: importi in chiaro con la sola schermata protetta (un'esportazione o un'IA li leggerebbe); un database di totali separato (un secondo posto da proteggere e da tenere coerente); cifrare tutta la voce (si perderebbe la ricerca per «affitto» o «pizza»); fare i conti con `float` (gli arrotondamenti sui centesimi si accumulano).
