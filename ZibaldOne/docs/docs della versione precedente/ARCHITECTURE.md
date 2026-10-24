# 🏗️ ARCHITETTURA PERSON-CENTRIC

## Overview

L'architettura del progetto è organizzata attorno a un concetto centrale: **Every person is a Person object**. Family members e social contacts sono specializzazioni di questa base universale.

---

## Class Hierarchy

```
Person (Base Class)
├── Profilo Core
├── Contatti Strutturati
├── Dati Sensibili (con Security)
├── Media Gallery
├── Relazioni Gerarchiche
└── Metadati

    ├→ Family_Member (extends Person)
    │   ├── Genealogical Info
    │   ├── Famiglia d'appartenenza
    │   └── Generational Level
    │
    └→ Social_Person (extends Person)
        ├── How/Where we met
        ├── Shared Interests
        └── Interaction History
```

---

## Struttura Daily_Journal Domains

### Family Domain
```python
family_domain = {
    "family_members_objects_dictionary": {
        "family_member_001": Family_Member("Marco Rossi"),  # Objects direttamente
        "family_member_002": Family_Member("Lucia Rossi"),
    },
    "family_member_interaction_events_by_member_dictionary": {
        "family_member_001": [
            {
                "event_type": "call",
                "timestamp": "2026-03-14",
                "notes": "Discussione su piani estivi"
            },
            # ... più eventi
        ]
    },
    "family_genealogical_tree_state_dictionary": {
        "tree_generation_levels_list": ["Grandparent", "Parent", "Self", "Child"],
        "tree_parentage_relationships_dictionary": {
            "family_member_001": "family_member_003",  # Marco è figlio di...
        },
    }
}
```

### Social Domain
```python
social_domain = {
    "social_people_objects_dictionary": {
        "social_person_001": Social_Person("Marco Bianchi"),
        "social_person_002": Social_Person("Lucia Bianchi"),
    },
    "social_person_interaction_events_by_person_dictionary": {
        "social_person_001": [
            {
                "event_type": "hangout",
                "timestamp": "2026-03-10",
                "location": "Caffè Centro",
                "notes": "Discussione su progetti"
            }
        ]
    },
    "social_network_graph_state_dictionary": {
        "network_connection_pairs_list": [
            ("social_person_001", "social_person_002"),  # Marco conosce Lucia
            ("social_person_002", "social_person_003"),  # Lucia conosce...
        ],
        "network_mutual_contact_groups_dictionary": {
            "group_001": ["social_person_001", "social_person_002"],  # Gruppo amici
        }
    }
}
```

---

## Query Examples (Future Implementation)

### Query 1: "Mostrami tutto di Marco"
```python
def get_person_complete_profile(daily_journal, person_identifier):
    """Return all data about a specific person across both family and social"""
    
    # Cerca in family
    if person_identifier in daily_journal.family_domain["family_members_objects_dictionary"]:
        person_object = daily_journal.family_domain["family_members_objects_dictionary"][person_identifier]
        events = daily_journal.family_domain["family_member_interaction_events_by_member_dictionary"].get(person_identifier, [])
        return {
            "person": person_object,
            "domain": "family",
            "events": events
        }
    
    # Cerca in social
    elif person_identifier in daily_journal.social_domain["social_people_objects_dictionary"]:
        person_object = daily_journal.social_domain["social_people_objects_dictionary"][person_identifier]
        events = daily_journal.social_domain["social_person_interaction_events_by_person_dictionary"].get(person_identifier, [])
        return {
            "person": person_object,
            "domain": "social",
            "events": events
        }
```

### Query 2: "Visualizza albero genealogico"
```python
def visualize_family_tree(daily_journal):
    """Generate family tree as graph from genealogical structure"""
    
    tree_state = daily_journal.family_domain["family_genealogical_tree_state_dictionary"]
    
    # tree_state contiene già:
    # - tree_generation_levels_list: generazioni da visualizzare
    # - tree_parentage_relationships_dictionary: relazioni padre-figlio
    
    # Questo è pronto per essere passato a libreria di graph viz tipo:
    # networkx, graphviz, plotly, etc.
```

### Query 3: "Chi è il mio contatto più frequente?"
```python
def get_most_frequent_contact(daily_journal, domain="social"):
    """Find most interacted-with person"""
    
    interaction_dict = daily_journal.social_domain["social_person_interaction_events_by_person_dictionary"]
    
    # Analizza frequenza events per ogni persone
    # Ritorna il person_identifier con più events
```

---

## Dati Sensibili: Security Architecture

### Esempio: Persona con Dati Sensibili
```python
marco = Family_Member("Marco Rossi")

marco.person_sensitive_data_profile_dictionary = {
    
    "sensitive_personal_number": "XXXXX",  # Numero documento
    
    "sensitive_home_address": "Via Roma 123, 00100 Roma",
    
    "sensitive_medical_notes": ["Allergia a penicillina", "Diabete tipo 2"],
    
    "sensitive_data_is_password_protected_boolean": True,
    
    "sensitive_data_security_level_string": "high"
}

# Access richiede: pin_unlock(marco.sensitive_data_profile_dictionary)
```

### Access Pattern (Future)
```python
def unlock_sensitive_data(person_object, user_provided_pin_string):
    """Unlock sensitive data with PIN"""
    
    if not person_object.person_sensitive_data_profile_dictionary["sensitive_data_is_password_protected_boolean"]:
        return person_object.person_sensitive_data_profile_dictionary
    
    # Validate PIN
    if validate_pin(user_provided_pin_string, person_object.stored_pin_hash):
        return person_object.person_sensitive_data_profile_dictionary
    else:
        raise PermissionError("PIN non corretto")
```

---

## Media & Device Shortcuts

Ogni persona può avere:
```python
person.person_media_gallery_dictionary = {
    "photos_file_paths_list": [
        "/path/to/photo1.jpg",
        "/path/to/photo2.jpg"
    ],
    "videos_file_paths_list": [...],
    "voice_recordings_file_paths_list": [...]
}

person.person_device_shortcuts_dictionary = {
    "phone_contact_reference_string": "marco@phone_app",
    "calendar_event_references_list": [
        "evento_001",
        "evento_002"
    ],
    "messaging_app_references_list": [
        "whatsapp_chat_marco",
        "telegram_group_amici"
    ]
}
```

---

## Relazioni Gerarchiche: Family Tree Example

```
Nonno         Nonna
  │             │
  └─────┬───────┘
        │
      Papà      Mamma
        │         │
        └────┬────┘
             │
           SELF      Fratello
             │          │
             └────┬─────┘
                  │
               Figli
```

Rappresentazione in dizionario:
```python
tree_parentage_relationships_dictionary = {
    "self": "father_id",        # Chi è mio padre
    "self": "mother_id",        # Chi è mia madre
    "father_id": "grandfather_id",
    "father_id": "grandmother_id",
}

# O più strutturato:
tree_parent_relationships = {
    "child_id": ["parent_id_1", "parent_id_2"]
}
```

---

## Reti Sociali: Graph Example

```
Marco ──── Lucia ──── Anna
  │          │         │
  └──────┬───┘         │
         │             │
      Simone ──────────┘

Connection pairs:
(Marco, Lucia)
(Marco, Simone)
(Lucia, Anna)
(Lucia, Simone)
(Anna, Simone)
```

---

## Workflow di Aggiunta Persona

```
1. User seleziona: "Aggiungi nuovo membro famiglia" o "Nuovo contatto social"

2. Sistema crea: Family_Member("Nome") o Social_Person("Nome")

3. User compila form:
   - Base info (nome, data nascita, etc.)
   - Contatti (phone, email, social)
   - Ruoli e custom tags
   - (Opzionale) Dati sensibili con PIN

4. Sistema genera: person_unique_identifier (es: "family_member_001")

5. Salva in: family_memb.../social_people_objects_dictionary

6. Se famiglia: aggiorna tree relationships

7. Se social: aggiorna network graph

8. Serialize to JSON per persistenza
```

---

## Future Extensibility

### Possibili Aggiunte
- **Import from Phone Contacts**: Auto-populate social_people_dictionary
- **Integrazioni Social Media**: Auto-populate Instagram, Facebook data
- **Backup/Export**: Export Person profiles come vCard o formato standard
- **Fuzzy Matching**: "Questa persona è lo stesso Marco in family e social?"
- **Analytics Dashboard**: "Network analysis", "Family tree complexity", "Contact frequency"
- **Timeline Visualization**: Interazioni nel tempo con una persona
- **Relationship Strength**: Calcola "how close" basato su frequency, recency, sentiment

---

*Documento creato: 14 Marzo 2026 - Versione 1.0*
