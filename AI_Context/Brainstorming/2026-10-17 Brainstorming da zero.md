---
tags:
  - brainstorming
  - decisione-aperta
date: 2026-10-17
stato: deciso il 2026-10-17 → B ora, poi A e D
---
# Brainstorming da zero — 2026-10-17

Torna a [[00 - START HERE]] · idee precedenti in [[2026-10-16 Brainstorming nuovo progetto]] (archivio) · regole di partenza in [[Standard nuovo progetto]].

> [!abstract] Criteri di Alex
> Progetto **nuovo**, a **passi piccoli**: scheletro iniziale e poi complessità crescente. Scalabile da subito, **versionato dal giorno 0**, comandi CLI tipo `nomeapp help`, poi interfaccia grafica, documentazione tecnica e user friendly in `docs/`. Deve stare dentro le sue conoscenze ma fargli imparare cose nuove. Ambiente: Windows + **WSL** (cartelle Linux collegate al desktop).

## A. Wardrobe Consultant (idea di Alex) ⭐ consigliata
Guardaroba come database, outfit manuali o consigliati dall'IA, consigli di shopping, prova virtuale, poi parte social.
- **Punto di partenza già esistente**: `Desktop\wardrobe` ha 36 capi fotografati (codici C camicie, P, T, S, G) e un CSV `ID, Categoria, Descrizione, Colore/Toni, Occasione`.
- **Cosa impari**: embedding di immagini (CLIP o un modello vision locale in Ollama), raccomandazione, un problema di ottimizzazione vero per lo shopping ("quale capo sblocca più outfit nuovi" = copertura su un grafo di compatibilità), poi GenAI per la prova virtuale.
- **Scala a fasi**
  - v0.1: `wardrobe help`, `wardrobe import` (dal CSV + foto), `wardrobe list --categoria camicia`, SQLite.
  - v0.2: `wardrobe outfit` con regole semplici (colori, occasione) e salvataggio outfit fatti a mano.
  - v0.3: UI (Streamlit neon) con galleria e outfit builder.
  - v0.4: auto-tagging delle foto con un modello vision locale (categoria, colore, materiale).
  - v0.5: "must have": il capo che massimizza i nuovi outfit compatibili.
  - v1.x: foto al volo di un capo in negozio → quanti outfit sblocca. Più avanti: prova virtuale e social.
- **Rischio**: la prova virtuale è difficile e pesante. Va tenuta come fase lontana, non come promessa iniziale.

## B. Diario componibile "a Lego" (idea di Alex)
Diario con **blocchi** che l'utente compone: slider, etichette, segnalibri per pagina, liste, testo, audio, testi di canzoni.
- **Idea tecnica**: il cuore è un motore di *schemi*: l'utente definisce un tipo di collezione ("Libro": titolo, autore, pagina attuale, segnalibri) e l'app genera form e viste. Ripartire da zero, prendendo dalla vecchia [[Journal App]] solo le idee.
- **Cosa impari**: architettura a plugin, schema design, trascrizione audio con Whisper (già usato nel [[Chatbot Ristorante]]), analisi emotiva locale del testo. Il tuo `ScannerLibri` (ISBN → Open Library / Google Books) può diventare un blocco.
- **Fasi**: v0.1 `diario new-type`, `diario add`, `diario list` su file JSON/SQLite; v0.2 blocchi base; v0.3 UI; v0.4 audio → testo; v0.5 stati emotivi con IA.
- **Rischio**: è facile che si allarghi troppo, come la vecchia versione. Servono confini rigidi per ogni versione.

## C. CryptoCTF Lab (dalla tua esperienza al CyberGame)
Toolkit Linux/WSL per le CTF di crittografia, in vista della prossima edizione.
- `ctf identify <testo>`: **classificatore ML** che riconosce codifica o cifrario (base64, hex, Caesar, Vigenère, XOR, ROT, parametri RSA). Il dataset lo generi tu in modo sintetico, come facevi con [[FakeUni]]. Prima n-gram + modello classico, poi una piccola rete sui byte.
- `ctf solve`: solver automatici per i casi classici; poi un agente (stile LangGraph) che prova gli strumenti in sequenza.
- **Cosa impari**: ML su dati sintetici, DL su sequenze, agenti con tool, packaging Linux.
- Base esistente: la tua pipeline in `CG—TOOLS` (incompleta, da leggere).

## D. Worldbuilding Forge (per scrittori e master GDR)
Personaggi, razze, luoghi, eventi, linee temporali collegati in un grafo.
- **IA utile davvero**: RAG sul tuo canone, **controllo di coerenza** ("questo capitolo contraddice ciò che hai scritto sulla razza X?"), generatore di nomi per razza con una piccola rete addestrata da te.
- **Lezione dalla perdita dei tuoi appunti**: tutto come Markdown in git, compatibile con Obsidian, backup dal primo giorno.
- Può ospitare un giorno il mondo di *Project One*.

## Idee lontane da te (per allargare l'orizzonte)
- **E. Mappa degli argomenti filosofici**: da un testo (Seneca, Nietzsche, Stirner) l'IA estrae premesse e conclusioni e costruisce un grafo; gli embedding mostrano dove si collocano le tue riflessioni tra stoicismo, esistenzialismo e anarchismo. NLP e grafi.
- **F. Hum-to-score**: canticchi una melodia, l'app la trascrive in note (pitch detection, audio DSP) e ti aiuta con rime e metrica per i testi. Elaborazione del segnale, mondo nuovo.
- **G. Agente con reinforcement learning** in un piccolo gioco di strategia scritto da te (Gymnasium). RL è la grande area di ML che non hai ancora toccato.

## Raccomandazione
**A (Wardrobe)**: hai già foto e dataset, è visivo e motivante, e ogni versione aggiunge uno strato nuovo (DB → regole → UI → vision → ottimizzazione → GenAI). **C** è un ottimo progetto parallelo e più corto, se vuoi prepararti al CyberGame.

## Esito (2026-10-17)
Alex sceglie **A, B, D**, partendo dalla **B** perché è la più gestibile e c'è già mezzo lavoro da ricalibrare → [[Diario Componibile]]. C non scelta per ora.

## Domande aperte (superate)
- A, B, C, D o una lontana?
- Nome e percorso della nuova repo.
- Percorso WSL di `CG—TOOLS` (dal desktop si vede solo il collegamento).
