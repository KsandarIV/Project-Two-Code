# 📔 DIARIO AGENDA PLANNER - Dichiarazione di Intenti

## Filosofia del Progetto

Questo progetto è un **viaggio di apprendimento Python** con l'obiettivo di creare un'applicazione interattiva per la gestione della quotidianità. La struttura è pensata per insegnare progressivamente concetti di programmazione (classi, serializzazione, interfacce, modularità) attraverso la costruzione di un tool pratico e personale.

---

## Vision Generale

### Scopo Primario
Creare un **diario-agenda-planner** che supporti la pianificazione e auto-consapevolezza quotidiana attraverso **3 checkpoint giornalieri**:
- **INIZIO GIORNATA** → Cosa devo fare oggi?
- **METÀ GIORNATA** → A che punto sono?
- **FINE GIORNATA** → Cosa ho fatto? Cosa ho imparato? Che devo fare domani?

### Estensione Temporale
Lo stesso sistema si replica e calibra su:
- **Giorno** (mandatorio - driver principale)
- **Settimana** (pianificazione settimanale)
- **Mese** (revisione e obiettivi mensili)
- **Anno** (visione e propositi annuali)

---

## Architettura dei Dati

### Aspetti della Vita (8 Domìni)
L'app traccia e gestisce questi aspetti in modo indipendente ma integrato:

1. **PERSONAL** → Il "Secondo Cervello" - Essenza dell'individuo, identità, valori, collezioni
2. **HEALTH** → Salute fisica e mentale
3. **FINANCE** → Gestione denaro, budget, spese
4. **FAMILY** → Relazioni familiari, reti genealogiche
5. **SOCIAL** → Vita sociale, amicizie, reti di contatti
6. **WORK** → Lavoro e carriera
7. **EDUCATION** → Formazione e studio
8. **RECREATION** → Intrattenimento, hobby

Ogni domìnio può avere:
- Check-in giornalieri (stato: buono/medio/scarso)
- Note e pensieri
- Goal specifici
- To-do list dedicata
- Metriche e score di progresso

---

### Sistema di Person-Centricity (NEW - 14 Marzo 2026)

#### Innovazione Architetturale
Introdotta una **classe base universal `Person`** che estende sia `Family_Member` che `Social_Person`:

##### Classe Person (Base Template)
Ogni persona nel network dell'utente è rappresentata da:
- **Profilo Core**: nome completo, data di nascita, genere, foto profilo
- **Sistema di Ruoli**: ruoli base codificati + ruoli personalizzati
  - Base (Friend, Colleague, Mentor, Counselor, Acquaintance, Other)
  - Custom (user-defined labels per flessibilità)
- **Contatti Strutturati**: phone, email, WhatsApp, Telegram, Instagram, Facebook, LinkedIn, Twitter, etc.
- **Profilo Sensibile**: dati delicati protetti da layer di sicurezza (indirizzo, numero identità, note mediche, allergie, contatti emergenza, info finanziari, stato relazionale)
- **Media e Scorciatoie**: foto, video, registrazioni audio, documenti + riferimenti ai contatti del dispositivo
- **Metadati di Relazione**: data ultima interazione, frequenza interazione (0-10), relationship type, date di anniversario

##### Genealogia e Reti Sociali
- **Family Tree Structure**: Parent/Sibling/Children relationships per visualizzazione grafica futura
- **Social Network Graph**: Connections per rappresentare reti sociali, mutual contacts, connection strength
- **Cross-domain Knowledge**: Se una persona compare sia in Family che in Social, il sistema mantiene coerenza

##### Security Layers
- Dati sensibili richiedono PIN/password separato
- Livelli di sicurezza configurabili (none, low, medium, high)
- Possibility di "hide" specifici attributi per utente

##### Estensioni di Person per Contesti Specifici

Oltre a `Family_Member` e `Social_Person`, il sistema riconosce che persone nello stesso network dell'utente possono avere ruoli e contesti primari diversi. Quindi introduciamo due nuove specializzazioni:

###### Work_Person
Per **relazioni nel contesto lavorativo** (manager, colleghi, clienti, partner, fornitori):
- Hanno una dimensione primariamente **professionale** ma possono avere anche aspetti sociali
- Traccia: ruolo professionale, organizzazione, dipartimento, aree di expertise
- Mantiene storico di progetti collaborativi e working style notes
- Può registrare se una relazione lavorativa è diventata anche amicizia sociale
- **NON rientra in social_domain** anche se ha elementi sociali, perché il contesto primario è lavoro

###### Finance_Person  
Per **relazioni nel contesto finanziario** (accountant, banchiere, assicuratore, partner che condivide finanze, roommate, amici con debiti/crediti):
- Possono essere **professionali** (commercialista, banchiere) o **personali** (partner che split rent, amico con debito)
- Traccia: ruolo finanziario, servizi forniti, conti condivisi, debiti/crediti, transazioni
- Mantiene storico di transazioni e accordi finanziari
- Registra recurring shared payments (es: affitto split, abbonamenti condivisi)
- **NON rientra in social_domain** anche se il contact potrebbe essere un amico, perché il tracking primario è la relazione finanziaria

**Vantaggio Architetturale**: Il sistema riconosce che una **stessa persona può comparire in multipli domini** (es: collega che è anche amico vs amico con cui splittiamo l'affitto vs professore che insegna corso vs manager che lavoriamo con nel medesimo tempo). Il sistema gestisce queste overlaps e mantiene coerenza dei dati.

---

### Sistema di Recreation Modulare (NEW - 14 Marzo 2026)

#### Innovazione Architetturale
Introdotto un **sistema modulare e scalabile per Entertainment/Hobbies**:

##### Recreation_Item (Classe Base)
Ogni entertainment item supporta:
- **Componenti Generici**: Counter, Progress, Bookmark, Rating, Tags
  - `Counter`: Traccia progresso (attuale/target/unlimited)
  - `Progress`: Stato completamento (not_started, ongoing, completed, paused, dropped)
  - `Bookmark`: Marca posizione corrente per riprendere
  - `Rating`: Valutazione e review con possibilità spoiler
  - `Tags`: Categorizzazione e tagging personalizzato

##### Categorie Predefinite (7 Specializzazioni)
1. **Book**: Titolo, autore, pagine, ISBN, lingua
2. **Anime**: Studio, episodi, stagioni, generi
3. **VideoGame**: Sviluppatore, piattaforma, playtime, achievements
4. **TVSeries**: Network, stagioni, episodi, generi
5. **Sport**: Tipo, ore praticate, skill level, personal records
6. **Movie**: Regista, genere, runtime, watch count
7. **TabletopGame**: Tipo (RPG, BoardGame, CardGame), players, duration

##### Categorie Custom
L'utente può creare qualsiasi categoria personalizzata (Fotografia, Knitting, Musica, etc.)
utilizzando la classe base Recreation_Item

##### Funzionalità Avanzate
- **Time Tracking**: Ore spese per categoria
- **Wishlist**: Item da aggiungere in futuro
- **Analytics**: Statistiche per categoria
- **Cross-item Recommendations**: Suggerimenti basati su rating e bookmark
- **Media Gallery**: Foto, video, documenti per ogni item
- **Device Shortcuts**: Link a contatti del cell, calendar events, note app

##### Workflow Esempio
1. User crea `Book("Il Signore degli Anelli")`
2. System generi counter automatico (pagine), progress tracker
3. User aggiorna: `book.current_page = 150`
4. System calcola percentuale e aggiorna bookmark
5. Quando finito: `progress.status = "completed"`, richiede rating
6. Rating si salva con timestamp per analytics future

---

### Personal Collections & Philosophy - Il "Secondo Cervello" (NEW - 14 Marzo 2026)

#### Visione Ontologica
Il PERSONAL domain non è solo "feelings e thoughts" momentanei, ma il **nucleo identitario** del progetto. Riconosce una verità filosofica profonda: 

> "L'individuo è definito non solo da ciò che pensa e sente, ma anche da ciò che possiede, colleziona, e a cui attribuisce valore."

Questo non è materialismo, ma riconoscimento che **gli oggetti portano significato**. La tua libreria riflette il tuo viaggio intellettuale. Il tuo guardaroba riflette come ti vuoi presentare al mondo. I tuoi giochi riflettono ciò che ti affascina.

#### Componenti del Personal Domain

**1. Personal_Identity**: Chi sono, stripped to essence
- Core traits, strengths, growth areas
- Proudest achievements, deepest fears
- Definition of success, definition of happiness
- Legacy I want to leave

**2. Personal_Philosophy**: Belief system and worldview
- Core values e life principles
- Guiding questions
- Heroes and influences
- Books that shaped me
- Moments of clarity

**3. Personal Collections**: Ciò che possegdo e che mi definisce
- **Wardrobe**: Come mi presento al mondo (abbigliamento, stile, identità)
- **Personal Library**: Viaggio intellettuale (libri, autori, generi preferiti)
- **Gaming Collection**: Evoluzione del gioco (skill, narrative, social connection)
- **Music Collection**: Soundtrack dell'esistenza (artisti, playlist, mood-based)
- **Digital Archive**: Memoria e documenti importanti (identità, certificati, memories)
- **Custom Collections**: Qualsiasi cosa l'utente voglia collezionare e tracciare

**4. Self-Narrative**: La storia che racconto di me
- Autobiography: Capitoli della vita, turning points
- Bucket list: Aspirazioni e sogni
- Long-term vision: Verso dove sto andando
- Habits & Growth: Abitudini che sto sviluppando, aree di crescita

#### Implicazioni Filosofiche

Questa architettura riconosce che:
- **Identità**: Non è statica, è un processo di auto-descrizione costante
- **Possesso**: Non è superficiale, ma un mezzo di auto-espressione
- **Filosofia**: Guida decisioni quotidiane e long-term
- **Collezioni**: Raccontano storie di chi siamo
- **Crescita**: È documentabile e tracciabile nel tempo

#### Query Future - Self-Discovery
```
"Chi sono veramente, secondo i miei dati?"
"Come è cambiata la mia identità negli ultimi 6 mesi?"
"Le mie azioni riflettono i miei valori dichiarati?"
"Quali libri hanno formato il mio worldview?"
"Quante ore ho investito nelle cose che contano veramente?"
"Il mio wardrobe riflette chi voglio essere?"
```

---

### Funzionalità Core (Fasi di Sviluppo)
- ✅ Modello di dati `Daily_Journal`
- Espandere modelli per `Weekly_Review`, `Monthly_Review`, `Yearly_Review`
- Sistema di serializzazione JSON robusto

### Fase 2: Gestione Giornaliera (Logic Layer)
- Checkpoint giornalieri (check-in, set goal, review)
- To-do list per giorno
- Note e riflessioni
- Score giornaliero (0-10 per domìnio)

### Fase 3: Funzioni Avanzate (Feature Layer)
- Tag system (filtraggio e ricerca)
- Money tracking dettagliato (budget, spese, goal finanziari)
- Lock e PIN per privacy
- Secret journal (per pensieri privati)

### Fase 4: Modularità e Combinabilità
- Funzioni riutilizzabili che l'utente può combinare
- Filtri e query personalizzate
- Widget modulari per dare forma all'esperienza

### Fase 5: Funzioni Specifiche per Domini 
- **FINANCE**: shopping list, goal finanziari, tracking spese
- **RECREATION**: bookmark film/serie/libri/giochi
- **HEALTH**: tracker abitudini, meditazione, esercizio
- **EDUCATION**: tracciamento progressi studio
- (future espansioni...)

### Fase 6: Visualizzazione e Gestione Person Networks (NEW)
- **Alberi Genealogici**: Generazione automatica di family tree grafici
- **Reti Sociali**: Visualizzazione delle connessioni sociali e mutual contacts
- **Query Person-centric**: "Mostrami tutto di Marco" - aggregazione dati da tutti i domini
- **Profili Person**: View dedicata per ogni persona con timeline interazioni
- **Security Layers**: Interface di gestione dati sensibili con PIN/password
- **Media Gallery**: Visualizzazione foto/video per ogni contatto
- **Relation Analytics**: Metriche su interazioni, frequenza contatti, engagement

### Fase 7: App Mobile
- Export della logica in JSON
- Interfaccia interattiva e responsive
- Sincronizzazione cross-device
- Offline mode con sync quando online

---

## Principi Guida

1. **Imparare facendo** → Ogni funzione è un'occasione per imparare
2. **Modularità** → Componenti indipendenti e ricomponibili
3. **Persistenza** → I dati sopravvivono tra sessioni (JSON)
4. **Flessibilità** → Strutture adattabili a logiche diverse
5. **Auto-consapevolezza** → L'app supporta la riflessione personale
6. **Privacy** → Funzioni di protezione per contenuti sensibili

---

## Stack Tecnologico Attuale

- **Linguaggio**: Python 3.x
- **Storage**: JSON (file)
- **Modellazione**: Classi Python (OOP)
- **Output**: CLI (versione attuale) → GUI/Mobile (futuro)

---

## Deliverables Finale (Long-term)

Un'applicazione mobile **altamente interattiva** che:
- Permette 3 check-in giornalieri intuitivi
- Mostra metriche e progressi nel tempo
- Offre funzioni specifiche per ogni domìnio
- Combina dati per fornire insights personali
- Supporta la pianificazione multi-temporale
- Protegge la privacy dell'utente

---

## Stato Attuale del Codice

### Completato ✅
- `data_models.py`: 
  - ✅ Classe `Daily_Journal` con 8 domìni modulari
  - ✅ Classe `Person` (base universal per Family_Member e Social_Person)
  - ✅ Classe `Family_Member` (extends Person con genealogia)
  - ✅ Classe `Social_Person` (extends Person con rete sociale)
  - ✅ Classi `Weekly_Review`, `Monthly_Review`, `Yearly_Review`
  - ✅ Struttura per alberi genealogici e reti sociali
  - ✅ Dati sensibili con security layers
  - ✅ Media gallery e device shortcuts
  - ✅ `Recreation_Item` (base class per hobbies/entertainment)
  - ✅ 7 Categorie specializzate: Book, Anime, VideoGame, TVSeries, Sport, Movie, TabletopGame
  - ✅ Componenti ricorrenti: Counter, Progress, Bookmark, Rating, Tags
  - ✅ Recreation_domain con tracking per categoria e wishlist
  - ✅ **Personal Collections (NEW)**:
    - ✅ `Personal_Collection` (base class)
    - ✅ `Wardrobe` - Stile e presentazione al mondo
    - ✅ `Personal_Library` - Viaggio intellettuale
    - ✅ `Personal_Gaming_Collection` - Evoluzione del gioco
    - ✅ `Personal_Music_Collection` - Soundtrack dell'esistenza
    - ✅ `Personal_Digital_Archive` - Memoria e documenti
  - ✅ **Personal_Identity** - Chi sono, essenza, legacy
  - ✅ **Personal_Philosophy** - Values, beliefs, worldview
  - ✅ Personal_domain completamente ridisegnato con visione ontologica
- `RECREATION_GUIDE.md` - Guida completa con esempi
- `ARCHITECTURE.md` - Documentazione Person-Centric architecture
- Struttura di base del progetto

### Da Implementare 🚧
- Logica di serializzazione JSON per Person objects (serializer.py)
- Logica di serializzazione JSON per Recreation_Item (serializer.py)
- Menu testuale interattivo
- Sistema di check-in giornaliero
- Gestione Person aggiunta/modifica/rimozione
- Gestione Recreation Item aggiunta/modifica/rimozione
- To-do list e goal tracking
- Tag e filtri
- Score e metriche
- Query person-centric ("Mostrami tutto di Marco")
- Query recreation-centric ("Mostrami tutti i libri in progresso")
- Alberi genealogici e reti sociali (visualizzazione)
- Layer di sicurezza per dati sensibili (PIN/password)
- Funzioni specifiche per domini (Health tracker, Finance manager, etc.)
- Tutte le funzioni elencate in `Journalv1.py`

---

## Road Map Visuale

```
[Core Models + Person System + Recreation] 
    ↓
[Save/Load JSON Serialization]
    ↓
[Daily Checks & Input]
    ↓
[Recreation Tracking] (Books, Games, Series, etc.)
    ↓
[To-Do & Goals]
    ↓
[Tags & Filtering]
    ↓
[Person-Centric Queries]
    ↓
[Genealogical Trees & Social Networks]
    ↓
[Money & Health Specifics]
    ↓
[Multi-temporal scales] (Week/Month/Year)
    ↓
[Metrics & Insights]
    ↓
[Security Layers & Sensitive Data]
    ↓
[UI/Mobile/Graph Visualization]
```

---

## Innovazioni Architetturali (14 Marzo 2026)

### Cambio di Paradigma: Person-Centric Architecture

Anziché trattare Family e Social come semplici liste, è stata introdotta una **architettura universale di Person** che permette:

1. **Modulazione**: Una sola classe `Person` serve come template per qualsiasi individuo
2. **Estensibilità**: `Family_Member` e `Social_Person` estendono Person con specifiche funzionalità
3. **Graph Readiness**: Strutture già preparate per genealogie e reti sociali
4. **Query-Friendly**: Access O(1) a "tutto quello che conosco di una persona"
5. **Security-First**: Layer di protezione per dati sensibili dalla struttura base
6. **Future-Proof**: Aggiungere foto, video, contatti, relazioni gerarchiche è già built-in
7. **Media + Shortcuts**: Ogni persona può linkare media e scorciatoie al device

### Implicazioni Future

- **Visualizzazioni Grafiche**: Alberi genealogici e reti sociali diventano triviali da generare
- **Cross-Domain Coherence**: Se una persona compare sia in Family che Social, il sistema lo sa
- **Analytics**: Metriche per "chi ho visto più spesso", "relazioni più forti", "gap di contatto"
- **Mobile Sync**: Sincronizzazione naturale con contatti del telefono
- **Data Portability**: Export formato standard per backup e transfer

---

### Cambio di Paradigma: Recreation Modulare Architecture (NEW - 14 Marzo 2026)

Anziché hardcoded lists (movies[], games[], books[]), è stata introdotta una **architettura modulare e scalabile** per hobbies/entertainment:

1. **Componenti Generici**: Counter, Progress, Bookmark, Rating, Tags riusabili per qualsiasi categoria
2. **Specializzazioni Predefinite**: 7 categorie con attributi specifici (Book, Anime, VideoGame, TVSeries, Sport, Movie, TabletopGame)
3. **Custom Categories**: L'utente può aggiungere qualsiasi hobby personalizzato
4. **Time Tracking Automatico**: Ogni categoria aggrega ore spese per analytics
5. **Wishlist Built-in**: Support nativo per "voglio fare questo dopo"
6. **Bookmark System**: Riprendere da dove si era rimasti senza perdere il punto
7. **Rating + Review**: Feedback conservato con timestamp per analytics

### Implicazioni Future - Recreation

- **Smart Recommendations**: "Hai finito questo libro in 10 giorni, ecco 3 simili..."
- **Time Analytics**: "Hai speso 120 ore su VideoGames, 45 su Serie TV..."
- **Binge Tracking**: Avvisi intelligenti se categoria riceve troppo tempo
- **Social Sharing**: Share review/rating su social media
- **Mobile Integration**: Import from Letterboxd (films), MyAnimeList, Goodreads, Steam
- **Habit Breaking**: "Ultimi 30 giorni: 0 sport, aumenta impegno!"
- **Cross-domain Suggestions**: Se leggi fantasy, consiglia anime fantasy

---

### Cambio di Paradigma Ontologico: Personal Collections & Philosophy (NEW - 14 Marzo 2026)

Riconoscimento che **l'individuo è definito da ciò che possiede, colleziona, e a cui attribuisce valore**:

1. **Personal_Identity**: Essence statement - Chi sono, stripped to core
   - Non una bio, ma narrative ontologica
   - Core traits, achievements, fears, legacy, definition of success
   
2. **Personal_Philosophy**: Belief system che guida la vita
   - Core values e life principles
   - Worldview e guiding questions
   - Heroes, books, moments di clarity

3. **Personal Collections**: Ciò che possegdo e che mi definisce
   - **Wardrobe**: Come mi presento al mondo (identità visuale)
   - **Library**: Viaggio intellettuale (libri che lettura, autori che mi toccano)
   - **Gaming Collection**: Evoluzione del gioco (skill, narrative, connection)
   - **Music Collection**: Soundtrack dell'esistenza (mood, artisti, memoria)
   - **Digital Archive**: Memoria custodita (documenti importanti, photos, voice recordings)
   - **Infinitely Extensible**: L'utente può creare qualsiasi collezione

4. **Self-Narrative**: La storia che racconto di me
   - Autobiography in capitoli
   - Bucket list aspirazioni
   - Long-term vision
   - Habits & growth tracking

### Implicazioni Filosofiche - Personal

- **Identity as Data**: Identità non è statica, è processo di auto-descrizione
- **Possession as Expression**: Guardaroba, libri, collezioni raccontano chi siamo
- **Philosophy as Guidance**: Valori documentati guidano decisioni
- **Collections as Memory**: Passato custodito parla di presente
- **Growth as Traceable**: Evoluzione documentata nel tempo

### Query Future - Self-Discovery

```
"Chi sono veramente, secondo i miei dati?"
"Come è cambiata la mia identità negli ultimi 6 mesi?"
"Quali valori dichiaro vs quali pratico?"
"Quali libri hanno formato il mio worldview?"
"Quanto tempo ho invertito nelle cose che contano?"
"Il mio guardaroba riflette chi voglio essere?"
"Qual è il tema dei miei ultimi 50 libri letti?"
```

---

*Questo documento rappresenta la **visione** del progetto e evolverà con il codice.*
