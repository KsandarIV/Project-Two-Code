---
tags:
  - studio
  - its
  - ai-context
date: 2026-10-16
fonte: Google Drive condiviso "MATERIALE DIDATTICO AIRO2527" (proprietario cdamato@laziodigital.it), letto in sola lettura
---
# Materiale ITS AIRO2527

Torna a [[00 - START HERE]] · vedi [[Percorso ITS]], [[Mappa competenze]], [[2026-10-16 Brainstorming nuovo progetto]].

Corso ITS "Data Science & IA" (codice IARO/AIRO 2527), Lazio Digital, cofinanziato UE/Regione Lazio. Lezioni da novembre 2025, orario 9-13 e 14-18.

## Cosa c'è nella cartella condivisa
14 cartelle, 26 file. Alcune cartelle (Matematica e statistica, Probabilità e statistica, Inglese, DevOps) risultavano vuote alla lettura via connettore, e non c'erano materiali di Data Science, ML, Data Visualization, Deep Learning, GenAI e Applicazioni IA.

> [!warning] Correzione di Alex (2026-10-17)
> Il Drive letto **non rappresenta tutto il corso**. In aula sono stati studiati anche: deep learning e reti neurali, **CNN**, GenAI, architetture **encoder-decoder**, transformer e *Attention Is All You Need*; esercitazioni su **Fashion-MNIST**, **digits** e computer vision. Nelle ultime due settimane (Applicazioni dell'IA) varie applicazioni, tra cui un progetto di **chatbot e voicebot per le prenotazioni di un ristorante**, collegati a un backend con database (sviluppato con Claude in un'altra sessione, vedi [[Chatbot Ristorante]]). Per questi moduli la fonte è la repo (`Git-ITS—PC/`, `Obsidian/gitobsITS/`) e Alex stesso.

| Cartella | Contenuto utile |
|---|---|
| 0_CALENDARIO DIDATTICO | 6 calendari PDF da nov 2025 a ott 2026 (sotto la sequenza dei moduli) |
| PROGRAMMAZIONE PYTHON (BIP) | `notebook_fondamenti_programmazione.ipynb` (Python 3.14, kernel "corso_ITS"): dict, liste, tuple, while/for, funzioni, default args, scope, lambda/map/filter, file I/O con `with`, import, comprehension, enumerate. `esercizi_no_soluzione.md`: 40 esercizi su stringhe, liste, tuple, dizionari, file txt/JSON, `os` (consiglio del docente: test con `assert`, stimare la complessità). `esercizi_debug_completi_soluzioni.ipynb`: 29 esercizi "correggi il bug" (flatten, dedup, trasposta, sort con key, merge di dict annidati, camelCase→snake_case, JSON) |
| BASI DI DATI (Exprivia) | `02_SQL Language.pptx` (67 MB, non letta). `Esercitazione SQL-MONGO.rtf`: progetto **GreenWheel** (car sharing di monopattini/bici): scegliere SQL o MongoDB, modellare veicoli/utenti/corse (con percorso GPS), popolare (5 veicoli, 3 utenti, 10 corse), 3 query (batteria <20%, spesa utente ultimo mese, coordinate ultima corsa) e relazione sulla scelta |
| ANALISI MATEMATICA | Marcellini-Sbordone (teoria + 2 volumi di esercizi), `SimulazioneTestAnalisi.pdf` (14 domande a risposta multipla: sup/inf, induzione, iniettività/suriettività, dominio, limiti, discontinuità) |
| DIRITTO INFORMATICO | Dispense 1 (cybersecurity, triade RID/CIA, crittografia simmetrica/asimmetrica, GDPR/NIS/ISO 27001, risk management), 2 (GDPR: titolare, incaricati, amministratore di sistema, DPO), slide **AI Act** (approccio a rischio, pratiche vietate art. 5, alto rischio art. 6, data governance art. 9-10, logging, supervisione umana art. 14, GPAI, sanzioni fino a 35 M€ o 7%) e slide su cyberspazio e sicurezza nazionale |
| SICUREZZA SUL LAVORO | Formazione generale e specifica (PDF) |
| INFORMATICA DI BASE | Solo due link a Google Docs del docente (Lepera) |

## Sequenza dei moduli (dai calendari)
- **Nov 2025 - gen 2026**: Inglese tecnico (English House), Soft skills (Orienta), Matematica e statistica, Informatica di base, Diritto informatico, Sicurezza sul lavoro.
- **Feb - inizio mar 2026**: Analisi matematica, Algebra lineare, Probabilità e statistica.
- **9 mar - 3 apr 2026**: Programmazione Python (BIP).
- **6 - 17 apr**: Fondamenti e tecniche DevOps (Exprivia).
- **20 apr - 8 mag**: Basi di dati relazionali e non (Exprivia).
- **18 mag - 19 giu**: Data Science (Olidata).
- **22 giu - 3 lug**: Machine Learning e Data Visualization (Exprivia).
- **lug - metà set**: nessun calendario nella cartella; Deep Learning (reti neurali, CNN, Fashion-MNIST, digits, computer vision) e GenAI (encoder-decoder, attention, transformer) con BIP.
- **21 - 25 set**: Sviluppo applicazioni di IA su piattaforme mobile (BIP).
- **28 set - 2 ott**: AI 4 Security (Leonardo).
- **5 - 19 ott**: Applicazioni dell'IA (Exprivia).
- **20 - 23 ott 2026**: **Project Work Exprivia** (la settimana prossima).
- **26 - 30 ott 2026**: Project Management (ItalDigit).

## Cosa conta per il prossimo progetto
- Il **Project Work Exprivia (20-23 ottobre)** arriva prima della scadenza del brainstorming (18 ottobre): conviene che l'idea scelta possa servire anche lì, o almeno non entrarci in conflitto.
- Il corso copre bene la base e anche ML, DL e GenAI applicata (vedi correzione sopra). Il valore aggiunto di un progetto personale è quindi **dati propri, valutazione rigorosa e documentazione**, non imparare da zero DL o GenAI. Vedi [[Mappa competenze]].
- Un progetto che documenti rischio, dati e supervisione umana in stile **AI Act** (art. 9-14) è un plus spendibile nei colloqui e coerente col modulo di diritto.
- L'esercizio GreenWheel è un buon modello di "consegna" ITS: dataset piccolo, schema, query e una relazione che motiva le scelte.
