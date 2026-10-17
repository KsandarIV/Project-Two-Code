# ✅ CHECKLIST SVILUPPO - DIARIO AGENDA PLANNER

## 🎯 PRIORITÀ E ORDINE DI SVILUPPO

### **FASE 1️⃣: FONDAZIONI DEL DATA LAYER** ← **INIZIA QUI**

#### Sprint 1.1: Espandere i Modelli di Dati
- [ ] **1.1.1** Creare classe `Weekly_Review` con struttura per 7 giorni
- [ ] **1.1.2** Creare classe `Monthly_Review` con struttura per 30/31 giorni
- [ ] **1.1.3** Creare classe `Yearly_Review` con struttura per 12 mesi
- [ ] **1.1.4** Aggiungere attributo `check_in_status` a `Daily_Journal` (inizio/metà/fine)
- [ ] **1.1.5** Aggiungere lista `goals` a ciascun domìnio
- [ ] **1.1.6** Aggiungere lista `todo_items` a ciascun domìnio
- [ ] **1.1.7** Aggiungere `score` (0-10) per ciascun domìnio

#### Sprint 1.2: Sistema di Serializzazione Robusto
- [ ] **1.2.1** Implementare `app_to_json()` - converti istanze in JSON
- [ ] **1.2.2** Implementare `json_to_app()` - carica JSON e ricrea istanze
- [ ] **1.2.3** Implementare `save_json(filename)` - salva su file
- [ ] **1.2.4** Implementare `load_json(filename)` - carica da file
- [ ] **1.2.5** Testare serializzazione/deserializzazione con dati di prova

---

### **FASE 2️⃣: LOGICA DEL CHECK-IN GIORNALIERO**

#### Sprint 2.1: Struttura Menu Base
- [ ] **2.1.1** Implementare `app_menu()` - menu principale
- [ ] **2.1.2** Implementare `day_menu()` - menu giornaliero
- [ ] **2.1.3** Creare funzione per selezionare domìnio
- [ ] **2.1.4** Creare funzione per selezionare checkpoint (inizio/metà/fine)

#### Sprint 2.2: Check-in Giornaliero
- [ ] **2.2.1** Implementare `check_daily_status()` - leggi stato attuale
- [ ] **2.2.2** Implementare funzione "Check-in Inizio Giornata"
- [ ] **2.2.3** Implementare funzione "Check-in Metà Giornata"
- [ ] **2.2.4** Implementare funzione "Check-in Fine Giornata"
- [ ] **2.2.5** Aggiungere attribuggio `timestamp` a ogni check-in
- [ ] **2.2.6** Creare file test: `test_daily_checkin.py`

#### Sprint 2.3: Funzioni di Utilità
- [ ] **2.3.1** Implementare `date_time()` - data e ora attuale
- [ ] **2.3.2** Implementare validazione di input (year/month/day)

---

### **FASE 3️⃣: TO-DO, GOAL E NOTE**

#### Sprint 3.1: To-Do List e Goal
- [ ] **3.1.1** Implementare `to_do_list()` - gestione to-do
- [ ] **3.1.2** Implementare `write_goals()` - set goal per domìnio
- [ ] **3.1.3** Implementare `write_thoughts()` - note e riflessioni
- [ ] **3.1.4** Struttura: ogni elemento ha titolo, descrizione, data_creazione, completato (bool)

#### Sprint 3.2: Score e Metriche
- [ ] **3.2.1** Implementare `score()` - assegna score 0-10 per domìnio
- [ ] **3.2.2** Calcolare score medio settimanale
- [ ] **3.2.3** Calcolare score medio mensile

---

### **FASE 4️⃣: SISTEMA DI TAG E FILTRI**

#### Sprint 4.1: Tag System
- [ ] **4.1.1** Implementare `tags()` - create/manage tag globali
- [ ] **4.1.2** Associare tag a to-do, goal, note
- [ ] **4.1.3** Implementare `filter_by_tags()` - filtra per tag

---

### **FASE 5️⃣: FUNZIONI SPECIFICHE PER DOMÌNI**

#### Sprint 5.1: Finanza Dettagliata
- [ ] **5.1.1** Implementare `money_manager()` - gestione finanze
- [ ] **5.1.2** Implementare `money_update_balance()` - aggiorna saldo
- [ ] **5.1.3** Implementare `money_goals()` - goal finanziari (risparmio, target)
- [ ] **5.1.4** Implementare `money_shopping_list()` - lista della spesa
- [ ] **5.1.5** Creare struttura dati per spese (categoria, importo, data)

#### Sprint 5.2: Multi-Temporale (Week/Month/Year)
- [ ] **5.2.1** Implementare `week_menu()` - review settimanale
- [ ] **5.2.2** Implementare `month_menu()` - review mensile
- [ ] **5.2.3** Implementare `year_menu()` - review annuale
- [ ] **5.2.4** Aggregare dati giornalieri per settimana/mese/anno

---

### **FASE 6️⃣: PRIVACY E SICUREZZA**

#### Sprint 6.1: Lock & Secret Journal
- [ ] **6.1.1** Implementare `pin()` - set/change PIN
- [ ] **6.1.2** Implementare `lock()` - lock app
- [ ] **6.1.3** Implementare `secret_journal()` - journal crittografato
- [ ] **6.1.4** Integrazione sistema PIN con JSON (memorizzare PIN hash, non plaintext)

---

### **FASE 7️⃣: FUNZIONI FUTURE (Per Futuri Sviluppi)**

#### Sprint 7.1: Funzioni Specifiche per Domini
- [x] **7.1.1** Recreation: Sistema modulare per Libro, Anime, VideoGame, Serie TV, Sport, Film, TabletopGame + Custom
- [ ] **7.1.2** Recreation: Implementare metodi di tracking (progress, bookmark, rating, counter)
- [ ] **7.1.3** Health: tracker abitudini (meditazione, esercizio, acqua)
- [ ] **7.1.4** Education: tracciamento progressi corsi
- [ ] **7.1.5** Social: tracker contatti, anniversari amici

#### Sprint 7.2: Backup e Export
- [ ] **7.2.1** Implementare `backup_data()` - export su file backup
- [ ] **7.2.2** Implementare restore da backup

---

### **FASE 8️⃣: INTEGRAZIONE E MAIN**

- [ ] **8.1** Implementare `main()` - loop principale dell'app
- [ ] **8.2** Testing completo end-to-end
- [ ] **8.3** Creare file README.md con istruzioni d'uso

---

## 📋 CONVENZIONI E STRUCTURE

```
App/
├── data_models.py          # Classi: Daily_Journal, Weekly_Review, Monthly_Review, Yearly_Review
├── serializer.py           # Funzioni: app_to_json, json_to_app, save_json, load_json
├── journeys.py             # Logica menu e check-in
├── finance.py              # Funzioni specifiche per FINANCE (future)
├── health.py               # Funzioni specifiche per HEALTH (future)
├── utils.py                # Utility: validazione, date_time, etc
├── main.py                 # Entry point: main()
├── Journalv1.json          # Data file (auto-generato)
└── tests/
    ├── test_data_models.py
    ├── test_serializer.py
    └── test_integration.py
```

---

## 🚀 **PUNTO DI PARTENZA - DA QUI COMINCI**

### STATO ATTUALE (14 Marzo 2026):
**FASE 1 è al 70% - Fondazioni Architetturali Quasi Complete**

✅ Completato:
- Person-Centric Architecture (Person, Family_Member, Social_Person, **Work_Person (NEW!)**, **Finance_Person (NEW!)**)
- Recreation Modulare System (7 categorie predefinite + custom)
- **Personal Collections & Philosophy**
  - Personal_Identity: Core traits, achievements, fears, legacy
  - Personal_Philosophy: Values, principles, beliefs, worldview
  - Personal Collections: Wardrobe, Library, Gaming, Music, Digital Archive
  - Self-Narrative: Autobiography, bucket list, long-term vision
- **Professional & Financial Contacts (NEW!)**
  - Work_Person: Traccia manager, colleghi, clienti nel work_domain
  - Finance_Person: Traccia professionisti finanziari e contatti che condividono finanze
  - Questi non rientrano in social_domain anche se possono avere dimensioni sociali
  - Work_domain ha work_contacts_objects_dictionary + professional_network_state
  - Finance_domain ha finance_contacts_objects_dictionary + financial_network_state
- Componenti generici (Counter, Progress, Bookmark, Rating, Tags)
- Genealogical Trees e Social Network structures
- Family, Social, Work, Finance, e Personal domain completamente ridisegnati

### Immediato (Prossima 1-2 ore):
1. **Completa `serializer.py`**:
   - Implementa serializzazione per Person, Recreation_Item, Book, etc.
   - Implementa serializzazione per Personal Collections, Philosophy, Identity
   - Implementa le 4 funzioni core (app→json, json→app, save, load)
   - Fai test con dati di prova

2. **Crea `utils.py`**:
   - Funzioni utility: `date_time()`, validazioni
   - Helper functions per Recreation tracking
   - Helper functions per Person queries
   - Helper functions per Personal Collections management

### Step 1-2 (Domani):
- Implementare `day_menu()` e `check_daily_status()`
- Creare il primo check-in funzionante

### Filosofia di Sviluppo:
- Ogni funzione deve essere **testabile indipendentemente**
- Priorità a **data layer** (modelli) prima di UI
- Usa **type hints** per imparare typing
- Commenti e docstring per documentare

---

## 📊 Status Progetto

| Fase | Status | % Completamento |
|------|--------|-----------------|
| 1️⃣ Data Layer | 🟢 Avanzato | 70% |
| 2️⃣ Serialization | 🟡 In Corso | 5% |
| 3️⃣ Check-in Daily | ⚪ Todo | 0% |
| 4️⃣ TodoGoal/Note | ⚪ Todo | 0% |
| 5️⃣ Tag System | ⚪ Todo | 0% |
| 6️⃣ Domini Specifici | ⚪ Todo | 0% |
| 7️⃣ Privacy | ⚪ Todo | 0% |
| 8️⃣ Future Features | ⚪ Future | 0% |
| 9️⃣ Integration | ⚪ Todo | 0% |

---

*Ultimo aggiornamento: 14 marzo 2026*
