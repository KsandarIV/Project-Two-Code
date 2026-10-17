# ADR-0011 — Le 8 aree della vita come dato di modelli e voci

- **Data**: 2026-10-17 · **Stato**: accettata (richiesta di Alex, fase 0.2)
- **Contesto**: la vecchia Journal App metteva tutto dentro gli "aspetti della vita" ([requisiti della fase 0.2](../tecnica/requisiti-v0.2.md)). In ZibaldOne fino alla 0.1.5 le 8 aree erano solo le scale del check-in *Eudaimonia*: un libro, un allenamento o una persona non sapevano a quale area appartenessero, e non c'era un posto dove vedere un'area intera.
- **Decisione**:
  - Le 8 aree sono **fisse** (Personale, Salute, Finanze, Famiglia, Sociale, Lavoro, Studio, Svago), con nomi alternativi per chi scrive (`health`, `soldi`, `amici` …). Non si aggiungono aree nuove: per il resto ci sono modelli ed etichette.
  - **Area come campo**, non come modello: `area` nel modello (vale per tutte le sue voci) e nella voce (vince su quella del modello). Una voce può stare in più aree con un blocco *etichette* che si chiama `aree`.
  - **Indice derivato** `entry_areas` nell'archivio, come gli indici di ricerca (schema 3): si riscrive a ogni salvataggio e si ricostruisce insieme agli altri indici quando vanno riparati, quindi non è mai la fonte dei dati.
  - Punteggi, cose da fare e obiettivi **si ricavano dalle voci** (tipo di blocco e nomi), senza tabelle nuove: un check-in o una lista restano voci normali, che si cercano, si esportano e finiscono nei backup.
  - I modelli per le aree (check-in di un'area, obiettivo, lista delle cose da fare) stanno in un **pacchetto** a parte, `aree` (Liceo), che si può modificare come gli altri.
  - Le funzioni non ancora pronte si mostrano come **«In arrivo»** con la versione prevista, in un elenco unico nel codice, controllato da un test.
- **Conseguenze**:
  - Chi non usa le aree non vede differenze: le voci senza area funzionano come prima.
  - Le versioni successive (persone, finanze, abitudini …) agganciano le loro voci a un'area con lo stesso campo, senza un'altra migrazione.
  - Cambiare l'area di un modello sposta tutte le sue voci che non hanno un'area propria.
- **Alternative scartate**: una tabella delle aree modificabile dall'utente (le 8 aree sono il cuore della richiesta e delle mascotte); un modello per area con i dati dentro (avrebbe separato i libri dalla Biblioteca); le aree come semplici etichette (nessun controllo sui nomi, nessuna area ereditata dal modello).
