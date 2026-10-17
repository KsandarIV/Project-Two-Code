# Confronto con la vecchia Journal App

La Journal App (`GitHubRepository/Personal Projects/Journal App`, solo lettura) aveva già una visione ricca: diario-agenda-planner con 3 momenti della giornata, 8 aree della vita, persone, svago e collezioni, identità e filosofia personale. Il suo limite era tecnico: una classe Python per ogni tipo (`Book`, `Anime`, `Wardrobe` …), ~6000 righe e un serializzatore scritto a mano.

ZibaldOne tiene la visione e cambia il mezzo: **ogni idea diventa un modello fatto di blocchi**, quindi un dato che l'utente può cambiare, copiare e condividere.

| Idea della Journal App | In ZibaldOne | Versione |
|---|---|---|
| 3 momenti: inizio, metà, fine giornata | modelli *Mattina*, *Metà giornata*, *Sera* nel pacchetto Diario | v0.0.4 |
| Scala giorno → settimana → mese → anno | modelli *Revisione settimanale/mensile/annuale* + statistiche che riassumono i giorni | v0.0.4, v0.1.4 |
| 8 aree: personale, salute, finanze, famiglia, sociale, lavoro, studio, svago | modello *Check-in aree* con un punteggio 0-10 per area | v0.0.4 |
| Goal, to-do, note e score per area | blocchi `checklist`, `longtext`, `scale` | v0.0.4 |
| Componenti Counter, Progress, Bookmark, Rating, Tags | blocchi `progress` (stato + contatore), `bookmark`, `rating` (con recensione), `tags` | v0.0.3–v0.0.4 |
| 7 categorie di svago (libro, anime, videogioco, serie, sport, film, gioco da tavolo) + custom | modelli del pacchetto Collezioni; l'utente crea quelli nuovi | v0.0.4 |
| Wishlist | stato `wishlist` del blocco `progress` | v0.0.4 |
| Collezioni personali (guardaroba, libreria, giochi, musica, archivio) | modelli del pacchetto Collezioni | v0.0.4 |
| Identità, filosofia, autobiografia, bucket list, abitudini | pacchetto Io | v0.0.4 |
| Persone (famiglia, sociale, lavoro, finanze) con dati sensibili | modello *Persona* con ruolo e area; i dati sensibili restano fuori finché non c'è la cifratura dei moduli delicati | v0.0.4, dopo v0.1.5 |
| "Mostrami tutto di Marco" | blocco `link` + collegamenti inversi | v0.1.2 |
| Alberi genealogici e reti sociali | vista a grafo | v0.1.3 |
| Analytics: mood trend, score medi, distribuzione svago | statistiche e revisioni | v0.1.4 |
| Backup, verifica integrità, storia | istantanee, verifica, ripristino | v0.0.6 |
| PIN e diario segreto | cifratura con passphrase | v0.0.7 |
| Export PDF/CSV, ricerca, tag | export Markdown/CSV (v0.0.6), ricerca (v0.1.2) | v0.0.6, v0.1.2 |
| App mobile con sincronizzazione | Flet su Android, backup su Drive | v0.0.8–v0.1.0 |

## Cosa non riprendiamo
- Una classe per tipo e un serializzatore a mano: i modelli sono dati.
- Dati sensibili delle persone (documenti, note mediche) prima della cifratura obbligatoria dei moduli delicati.
