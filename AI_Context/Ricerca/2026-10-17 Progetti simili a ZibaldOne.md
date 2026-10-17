---
tags:
  - ricerca
  - zibaldone
date: 2026-10-17
---
# Progetti simili a ZibaldOne

Torna a [[Diario Componibile]] · [[00 - START HERE]].

> [!note] Metodo
> Ricerca breve: alcune ricerche web più ciò che so di questi strumenti. Le descrizioni sono sintetiche e vanno verificate sul sito prima di prendere decisioni importanti.

## 1. Note con "tipi" definiti dall'utente (i più vicini all'idea Lego)
| Strumento | Cosa fa di simile | Cosa prendere |
|---|---|---|
| **Tana** (supertag) | Un tag diventa un tipo con campi (es. `#libro` → autore, pagina, voto) | L'idea che un **modello** si applica a una voce con un gesto |
| **Anytype** | "Object types" e relazioni personalizzabili, locale e cifrato | Tipi + relazioni tra oggetti, local-first |
| **Capacities** | Oggetti tipizzati (Libro, Persona, Idea) collegati in un grafo, con daily note | Diario giornaliero come centro, oggetti attorno |
| **Notion** | Database con proprietà libere e template (molti template per libri e film) | Viste diverse sugli stessi dati (lista, tabella, galleria) |
| **Obsidian + Bases/Dataview** | Proprietà YAML nel frontmatter e viste-tabella sopra file Markdown | **I dati restano file Markdown leggibili**, fuori da ogni app |
| **Logseq** | Outliner con proprietà e journal giornaliero | Journal giornaliero di default |

## 2. Diari da terminale
| Strumento | Cosa prendere |
|---|---|
| **jrnl** (Python, testo semplice) | Sintassi rapida tipo `jrnl yesterday: ...`, tag con `@`, file di testo, cifratura opzionale |
| **dnote**, **taskwarrior**, **timewarrior** | CLI ben fatte con `help`, filtri e report; buon modello per `zbone` |

## 3. Tracker di media e collezioni
| Strumento | Cosa prendere |
|---|---|
| **Ryot**, **Yamtrack** (self-hosted) | Avanzamento libri, film, serie, giochi; import da servizi esterni |
| Goodreads, Letterboxd, Trakt | Dati ricchi ma chiusi e rigidi: è il limite che ZibaldOne vuole superare |

## 4. Diari con IA
| Strumento | Cosa prendere |
|---|---|
| **Day One** | Diario curato, audio e foto, ma cloud e abbonamento |
| **Rosebud**, **Reflectly**, **Mindsera** | Riflessioni guidate e analisi dell'umore con IA, quasi sempre su cloud |

## Dove si posiziona ZibaldOne
Nessuno degli strumenti sopra unisce tutte e quattro le cose:
1. **modelli a blocchi** creati dall'utente;
2. **diario** come centro;
3. **CLI + UI** sugli stessi dati;
4. **IA locale e privata** (trascrizione, emozioni) senza cloud.

È questo lo spazio del progetto.

## Lezioni da applicare subito
- **Formato dei dati aperto** (da Obsidian e jrnl): salvare ogni voce come **Markdown + frontmatter YAML** e usare SQLite solo come indice ricostruibile. Si apre anche in Obsidian, si versiona in git, sopravvive all'app (lezione dagli appunti persi). Proposta in [[Diario Componibile]].
- **Sintassi rapida da CLI** (da jrnl): `zbone add "letto fino a p.120" --libro "Così parlò Zarathustra"`.
- **Modelli pronti ma modificabili** (da Notion e Tana): Libro, Serie TV, Riflessione, Canzone come esempi iniziali.

## Fonti
- [Tana, supertags](https://thereport.substack.com/p/tana-the-21st-century-workspace) · [Supertags in Obsidian (forum)](https://forum.obsidian.md/t/supertags-in-obsidian/45439) · [LifeTracker](https://www.producthunt.com/p/lifetracker-track-anything-own-it/lifetracker-3) · [TagJournal](https://www.producthunt.com/products/tagjournal)
- [jrnl su PyPI](https://pypi.org/project/jrnl/2.4)
- [Anytype vs Logseq](https://openalternative.co/compare/anytype/vs/logseq) · [Logseq: tipi come Anytype o Tana](https://discuss.logseq.com/t/using-types-like-anytype-or-tana/12251)
- [Yamtrack](https://selfhostyourself.com/services/yamtrack) · [Ryot](https://github.com/felixonmars/ryot) · [Media tracking self-hosted](https://selfhostyourself.com/tags/media-tracking)
- [Migliori app di journaling con IA 2026 (Mindsera)](https://mindsera.com/articles/the-7-best-ai-journaling-apps-in-2026-tested) · [Confronto app IA (MyLifeNote)](https://blog.mylifenote.ai/the-7-best-ai-journaling-apps-in-2026/)
