# Requisiti della v0.2 (prossimo sprint, dopo la v0.1.5)

Fonte: i documenti della vecchia Journal App in `GitHubRepository/Personal Projects/Journal App/docs/` (`PROJECT_MANIFEST.md`, `ARCHITECTURE.md`, `RECREATION_GUIDE.md`, `CHECKLIST_SVILUPPO.md`, `ROADMAP.md`, `STRUCTURE.md`). Alex li considera **sue richieste** per la v0.2 (2026-10-17). Le classi Python di allora diventano modelli, blocchi e viste di ZibaldOne.

## Sprint v0.2
| Versione | Capacità | Da quale richiesta |
|---|---|---|
| v0.2.0 ✅ | **Le 8 aree della vita come concetto dell'app** ([le 8 aree](aree.md)): ogni modello e ogni voce può appartenere a un'area (Personale, Salute, Finanze, Famiglia, Sociale, Lavoro, Studio, Svago); per ogni area check-in, note, obiettivi, to-do e punteggio 0-10 nel tempo | Manifest "Aspetti della vita", Checklist 1.1.5–1.1.7 |
| v0.2.1 ✅ | **Persone complete** ([le persone](persone.md)): una persona può stare in più aree (famiglia, sociale, lavoro, finanze) con ruoli base e personalizzati, contatti strutturati, eventi di interazione (chiamata, uscita …), data dell'ultimo contatto e frequenza; "Mostrami tutto di Marco" su tutte le aree | Architecture "Person-centric", Work_Person, Finance_Person |
| v0.2.2 ✅ | **Albero genealogico e rete sociale** ([le persone](persone.md#legami-albero-e-rete-dalla-022)): relazioni tipizzate tra persone (genitore di, fratello di, conosce, collega di), vista ad albero per la famiglia e a rete per gli amici, contatti in comune, forza della relazione | Architecture "Family tree", "Social network", Query 2–3 |
| v0.2.3 ✅ | **Dati sensibili cifrati e diario segreto** ([i segreti](segreti.md)): blocchi segreti cifrati con la chiave dell'utente (documenti, indirizzi, note mediche), livelli di sicurezza, sblocco con PIN (l'impronta più avanti), voci segrete escluse da ricerca e IA | Manifest "Security Layers", Checklist fase 6 |
| v0.2.4 ✅ | **Media** ([gli allegati](allegati.md)): foto, video, audio e documenti allegati alle voci e alle persone, inclusi nei backup cifrati | Manifest "Media e scorciatoie" |
| v0.2.5 ✅ | **Svago avanzato** ([svago avanzato](svago.md)): date di inizio e fine automatiche, voto con mezzo punto (8,5/10), recensione con avviso spoiler, preferiti, lista dei desideri, tempo speso per categoria, import da file esportati da Goodreads, Letterboxd, MyAnimeList, Steam | Recreation guide, Manifest "Recreation" |
| v0.2.6 ✅ | **Finanze** ([le finanze](finanze.md)) (modulo delicato, cifrato): saldo, spese e entrate per categoria, budget e obiettivi di risparmio, lista della spesa, debiti e crediti con le persone, spese condivise ricorrenti | Checklist 5.1, Finance_Person |
| v0.2.7 ✅ | **Abitudini** ([le abitudini](abitudini.md)): tracker (meditazione, esercizio, acqua) con serie di giorni; gli obiettivi per area con avanzamento passano alla 0.2.8 | Checklist 7.1.3, Manifest fase 5 |
| v0.2.8 ✅ | **Viste componibili** ([viste e home](viste-e-home.md)): filtri e ricerche salvate, home fatta di widget scelti dall'utente, query come "tutti i libri in corso" | Manifest fase 4 |
| v0.2.9 | **Import dalla vecchia Journal App**: i file JSON di allora diventano voci di ZibaldOne | Struttura `data/Journalv1_*.json` |

Le query "di scoperta di sé" del manifest ("Chi sono secondo i miei dati?", "Le mie azioni riflettono i miei valori?") e i consigli incrociati tra categorie vanno nella parte IA, dopo l'anonimizzatore.

## Possibili conflitti con il progetto attuale
1. **Dati sensibili protetti solo da PIN**: un PIN da solo non protegge i file. In ZibaldOne i dati sensibili saranno **cifrati davvero**; PIN e impronta servono solo a sbloccare la chiave (v0.2.3).
2. **Import automatico dai contatti del telefono e dai social (Instagram, Facebook), condivisione delle recensioni sui social**: va contro il local-first e porta nell'app dati di altre persone. Proposta: solo import da file e solo su richiesta, niente collegamento alle API dei social, condivisione solo come export manuale.
3. **Avvisi come "Ultimi 30 giorni: 0 sport, aumenta impegno!"**: contrasta con il tono gentile deciso per le notifiche ([ADR-0008](../decisioni/ADR-0008-notifiche.md)). Proposta: osservazioni neutre e disattivabili ("questo mese niente sport: vuoi un promemoria?").
4. **Voti con decimali (8,5/10)**: oggi il blocco voto usa interi. Si aggiunge un'opzione mezzo punto, senza rompere le voci esistenti.
5. **Una classe per tipo e un file JSON per giorno**: sostituiti da modelli e SQLite ([ADR-0004](../decisioni/ADR-0004-flet-e-sqlite.md)). Le persone e le collezioni non vivono "dentro un giorno" ma attraverso i giorni; il giorno è una vista. L'import della v0.2.9 porta comunque i vecchi dati.
6. **Note mediche e numeri di documento di altre persone**: sono categorie particolari di dati (art. 9 GDPR) di terzi. L'uso personale resta nell'esenzione domestica, ma vanno solo nei blocchi cifrati e mai nei testi mandati all'IA.

Nessun altro punto è in conflitto: aree, persone, svago, collezioni, identità, filosofia, revisioni di settimana, mese e anno, statistiche e grafo sono già nella direzione di ZibaldOne.
