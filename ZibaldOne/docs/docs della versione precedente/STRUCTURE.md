# 📁 Struttura Organizzata - App

**14 Marzo 2026 - FASE 1 & 2 COMPLETE**

## Layout Finale

```
App/
├── 🚀 main.py                 # ENTRY POINT - Avvia qui: python main.py
├── 📖 README.md              # Documentazione completa
├── 📦 __init__.py            # Package root
│
├── 📂 core/                  # Data & Logic Layer
│   ├── __init__.py          # Exports: Daily_Journal, save/load, utils
│   ├── data_models.py       # ~3100 linee - Tutte le classi
│   ├── serializer.py        # ~1500 linee - JSON persistence
│   └── utils.py             # ~550 linee - 40+ utility functions
│
├── 📂 ui/                    # User Interface Layer
│   ├── __init__.py
│   └── menu.py              # ~850 linee - Menu interattivo completo
│
├── 📂 data/                  # Data Files (journals saved here)
│   ├── .gitkeep             # marker for git
│   └── Journalv1.json       # Example journal file
│
├── 📂 docs/                  # Documentation
│   ├── README.md            # Questo file
│   ├── CHECKLIST_SVILUPPO.md
│   ├── PROJECT_MANIFEST.md
│   ├── ARCHITECTURE.md
│   ├── RECREATION_GUIDE.md
│   └── PYTHON_BASICS.md
│
├── 📂 archive/               # Old Code (backup)
│   ├── data_models_old.py
│   └── Journalv1.py
│
└── 📂 LavoriInCorso.ipynb    # Notebook sperimentale
```

## Come Usare

### 1. Avvia l'applicazione
```bash
cd App
python main.py
```

### 2. Importa in Python
```python
from core import Daily_Journal, load_daily_journal_from_json_file
from core import Family_Member, Work_Person

# Carica journal
journal = load_daily_journal_from_json_file("data/Journalv1_2026-03-14.json")

# Aggiungi persona
mom = Family_Member("Mamma")
```

### 3. Da da notebook/script
```python
import sys
sys.path.insert(0, "App")

from core import Daily_Journal, generate_unique_identifier
from ui import main_application_menu
```

## File Stats

| Modulo | Linee | Funzioni | Classi |
|--------|-------|----------|--------|
| **core/data_models.py** | ~3100 | - | 50+ |
| **core/serializer.py** | ~1500 | 50+ | - |
| **core/utils.py** | ~550 | 40+ | - |
| **ui/menu.py** | ~850 | 15+ | - |
| **TOTALE** | **~6000** | **100+** | **50+** |

## Principali Funzioni

### core.data_models
- `Person`, `Family_Member`, `Social_Person`, `Work_Person`, `Finance_Person`
- `Recreation_Item` (+ 7 specializzazioni)
- `Personal_Collection` (+ 5 specializzazioni)
- `Daily_Journal` (8 domains)

### core.serializer
- `load_daily_journal_from_json_file(filename)` - Carica journal da disco
- `save_daily_journal_to_json_file(journal, filename)` - Salva su disco
- Supporto polimorfico per tutte le classi

### core.utils
- **Date**: `is_valid_date()`, `get_current_date_string()`
- **ID**: `generate_unique_identifier()`
- **Query**: `get_person_by_identifier()`, `get_all_people_in_domain()`
- **Network**: `find_shared_contacts_between_people()`
- **Validation**: `is_valid_name_string()`, `is_valid_score_integer()`
- **UI**: `clear_console()`, `print_section_header()`, `format_list_for_menu()`

### ui.menu
- `main_application_menu()` - Entry point
- `date_selector_menu()` - Seleziona data
- 8 domain-specific menus (personal, health, finance, family, social, work, education, recreation)
- `view_all_people_menu()`, `view_all_recreation_items_menu()`

## Flusso Applicazione

```
main.py
  └─> ui.menu.main_application_menu()
      ├─ Load/Create journal
      ├─ Select domain to check-in
      ├─ Add data to domain
      └─ Save to data/Journalv1_YYYY-MM-DD.json
```

## Cambiamenti dalla Versione Precedente

✅ **Organizzazione Gerarchica**
- Prima: tutti i file nella root
- Dopo: Struttura cartelle logica (core/, ui/, data/, docs/)

✅ **Import Statements**
- Prima: `from data_models import ...`
- Dopo: `from core.data_models import ...` (più esplicito)

✅ **Entry Point**
- Prima: eseguire individualmente ogni modulo
- Dopo: `python main.py` univoco

✅ **Documentazione**
- Aggiunto README.md completo
- Tutti i doc centralizzati in docs/

## Prossimi Passi

1. **FASE 3 - Persistenza avanzata**
   - Weekly/Monthly/Yearly serialization
   - Export CSV/PDF
   - Backup automatico

2. **FASE 4 - Visualization**
   - Grafici progress
   - Network graphs (famiglia, social)
   - Timeline

3. **TEST & QA**
   - Unit tests
   - Integration tests
   - Performance tests

---

**Status:** App funzionante e pronta per uso
**Data:** 14 Marzo 2026
