---
tags:
  - brainstorming
  - decisione-aperta
date: 2026-10-16
stato: archiviato il 2026-10-17 (opzioni 0-2 in archivio, 3-4 scartate)
---
# Brainstorming nuovo progetto — 2026-10-16

> [!info] Archiviato
> Il 2026-10-17 Alex ha chiesto di ripartire da zero: opzioni 0, 1, 2 tenute in archivio, 3 e 4 non interessanti. Nuovo brainstorming: [[2026-10-17 Brainstorming da zero]].

Torna a [[00 - START HERE]] · gap da colmare in [[Mappa competenze]].

> [!abstract] Criterio di scelta
> Il progetto deve portare competenze già studiate al corso su **dati propri**, con **valutazione rigorosa** e documentazione, essere locale e gratuito, procedere a passi piccoli e restare presentabile in portfolio.

> [!note] Correzione 2026-10-17
> Alex ha già fatto in aula DL (CNN, Fashion-MNIST, digits, computer vision), GenAI (encoder-decoder, attention) e un'app chatbot + voicebot con backend e DB ([[Chatbot Ristorante]]). Il "gap ML/DL" è ridimensionato: le opzioni sotto sono riformulate come progetti di portfolio, non come corsi di recupero.

> [!warning] Aggiornamento 2026-10-16 sera
> Dal Drive del corso ([[Materiale ITS AIRO2527]]): il **Project Work Exprivia è dal 20 al 23 ottobre**, subito dopo il weekend. Un progetto che si possa riusare lì vale di più. Il tema del Project Work non è nel materiale condiviso, quindi la cosa più utile è un **kit generico** pronto per qualsiasi dataset.

## Opzione 0 — ML Project Kit (weekend) + Nexus come banco di prova ⭐⭐ nuova raccomandazione
Uno scheletro riusabile, provato sui dati di [[Nexus Metrics]] questo weekend e riusato al Project Work con il dataset che daranno.
- **Contenuto del kit** (due binari, perché il Project Work potrebbe essere un modello o un'app IA come il [[Chatbot Ristorante]])
  1. **Binario dati/ML**: `quality_report` + EDA con tema neon (dal [[Python Starter Kit]]); pipeline sklearn con cross-validation, baseline semplice, 2-3 modelli, metriche, calibrazione.
  2. **Binario app IA**: lo schema già usato nel chatbot ristorante (LLM + tool + backend + DB) reso generico, con un **set di test** di conversazioni e una metrica di successo per task.
  3. Pagina Streamlit "risultati" nel tema di [[Design e palette]].
  4. **Model card in stile AI Act**: scopo, dati, rischi, metriche, limiti, supervisione umana (art. 9-14). È ciò che distingue la consegna.
- **Weekend (17-18 ottobre)**: costruire il kit con il primo passo dell'opzione 1 (feature al minuto 15 e baseline). Così è testato su dati veri.
- **Project Work (20-23 ottobre)**: giorno 1 dati ed EDA, giorno 2 modelli, giorno 3 dashboard, giorno 4 model card e presentazione.
- **Dopo**: si torna all'opzione 1 completa (MLP in PyTorch) e poi all'opzione 2.

## Opzione 1 — Nexus Metrics: "Chi vince dai primi 15 minuti?" ⭐ consigliata dopo il Project Work
ML classico, poi un piccolo DL. Continua [[Nexus Metrics]] usando le **926 timeline già scaricate**.
- **Domanda**: dato lo stato della partita al minuto 10/15 (differenza oro, XP, kill, draghi, torri, vision), prevedo la vittoria?
- **Perché**: copre ciò che manca (feature engineering, leakage, cross-validation, metriche, calibrazione, interpretabilità). Si confronta col dataset Kaggle `high_diamond_ranked_10min` che hai già esplorato.
- **Primi passi**
  1. Nuovo modulo `src/analytics/timeline_features.py`: estrae le feature al minuto N da **una** timeline, con test su una timeline finta.
  2. Tabella `features_at_15.csv` per tutte le partite.
  3. Baseline: "vince chi ha più oro" e poi `LogisticRegression` con la Pipeline dello [[Python Starter Kit]], cross-validation stratificata.
  4. Confronto con RandomForest/XGBoost, curva di calibrazione, importanza feature.
  5. Fase DL (già studiato, qui applicato a dati propri): modello sequenziale (GRU o piccolo transformer con attention) sui minuti 1..15, confrontato onestamente con la logistica.
  6. Una pagina nella dashboard: "probabilità di vittoria al minuto N".

## Opzione 2 — Nexus Coach: RAG locale sulle tue partite
GenAI applicata, milestone 5 di [[Nexus Metrics]]. Riusa quanto fatto nel RAG Lab ([[Percorso ITS]]).
- **Domanda**: "Come vado con Jinx quando perdo la lane?" → risposta con citazione delle partite.
- **Primi passi**
  1. Generare un testo breve per partita da `matches.csv` (nessun dato grezzo).
  2. Embedding con sentence-transformers e ChromaDB locale.
  3. LLM locale via Ollama (es. un modello piccolo da 3-8B).
  4. Set di 20 domande con risposta attesa per valutare **retrieval** (recall@k) separato dalla **generazione** (grounding).
  5. Tab "Coach" nella dashboard.
- **Rischio**: domande numeriche si risolvono meglio con pandas che con RAG. Una versione più solida è un agente con tool (query pandas + retrieval), come negli Agenti LAB.

## Opzione 3 — Odyssey Analytics: prevedere i ritardi del pendolare
ML su dati personali reali da [[Odyssey - Diario del Pendolare]].
- **Domanda**: quanto dura il viaggio Casa→ITS dati giorno, ora, meteo, mezzo?
- **Primi passi**: export del foglio in CSV, EDA con [[Design e palette]], baseline (media per tratta), regressione con validazione temporale, poi dashboard.
- **Rischio**: poche righe se la raccolta è recente; va controllato prima quante tratte ci sono.

## Opzione 4 — Study Buddy: RAG sui tuoi appunti Obsidian
GenAI applicata, progetto nuovo e utile subito per gli esami.
- **Domanda**: "Spiegami la differenza tra VAE e GAN" con citazione della nota ITS da cui viene la risposta, più generazione di quiz.
- **Primi passi**: loader dei `.md` del vault `gitobsITS`, chunking per titolo, embedding + Chroma, Ollama, 20 domande di valutazione, poi un'interfaccia Streamlit neon.
- **Rischio**: dati piccoli e testuali; simile a quanto già fatto in aula, quindi meno nuovo per il portfolio.

## Percorso consigliato
**0 → 1 → 2**, confermato anche dopo la correzione del 2026-10-17. Il kit serve subito al Project Work. L'opzione 1 resta il miglior progetto di portfolio perché usa **dati solo tuoi** (926 timeline) e applica DL su sequenze. L'opzione 2 diventa più forte: con l'esperienza del [[Chatbot Ristorante]] puoi fare un coach ad agente (tool pandas + retrieval) invece di un RAG semplice. L'opzione 4 scende di priorità.

## Domande aperte per Alex
- Quale opzione?
- Quanto tempo a settimana?
- Va bene lavorare nel progetto Nexus esistente (nuovi moduli, senza toccare quelli vecchi)?

## Esito
_(da compilare quando si decide → poi registrare in [[Registro decisioni]])_
