---
tags:
  - progetto
  - attivo
stato: v0.2.0 pronta (2026-10-17), da taggare; prossima v0.3
repo: C:\Users\okami\Desktop\ProjectTwoCode\Project-Two-Code\ZibaldOne
date: 2026-10-17
---
# Diario Componibile — ZibaldOne

> [!info] Nome
> **ZibaldOne** (scelto da Alex il 2026-10-17). Comando `zibaldone`, alias corto **`zbone`**. Ricerca sui concorrenti: [[2026-10-17 Progetti simili a ZibaldOne]].

Torna a [[00 - START HERE]] · regole in [[Standard nuovo progetto]] · idea B di [[2026-10-17 Brainstorming da zero]] · predecessore [[Journal App]].

> [!important] Visione allargata (Alex, 2026-10-17)
> Non solo diario: **tutto in uno personale** a moduli (diario, collezioni, appunti, documenti e carte, portafoglio e finanze, password tramite Bitwarden, grafo stile Obsidian, raccomandazioni di lettura basate su letture e riflessioni). **Windows + Android**, Linux in futuro; stessi dati su PC e telefono. Codice agile, scalabile e compartimentato. Dettagli nella repo: `ZibaldOne/docs/tecnica/visione.md`.

> [!abstract] Visione iniziale
> Un diario in cui l'utente **costruisce i propri strumenti a blocchi**, come con i Lego: un libro può avere solo un segnalibro, un altro uno slider di avanzamento e note per pagina; una pagina di diario può avere un umore, una riflessione, un audio o il testo di una canzone. Niente struttura rigida.

## Cosa prendiamo dalla vecchia Journal App (senza toccarla)
- **Componenti generici** già pensati bene: Counter, Progress, Bookmark, Rating, Tag → diventano i primi **blocchi**.
- I **3 checkpoint** giornalieri (inizio, metà, fine giornata) e la scala giorno → settimana → mese → anno, come **modelli** pronti, non come codice fisso.
- Le sezioni "Personal Philosophy / Identity" come modelli opzionali.

## Cosa lasciamo
- La gerarchia di classi rigida (`Book`, `Anime`, `VideoGame`... una classe per tipo): è proprio ciò che rende l'app non componibile.
- File giganti (`data_models.py` ~3100 righe) e un serializer a mano da 1500 righe.
- Il modulo persone con dati sensibili: troppo grande per l'inizio.

## Concetto chiave
- **Blocco** (`Block`): un tipo di campo con regole, per esempio `text`, `number`, `slider`, `rating`, `tags`, `checklist`, `bookmark`, `date`, poi `audio`, `isbn`.
- **Modello** (`Template`): una ricetta creata dall'utente, ovvero una lista di blocchi con nome. Esempi: "Libro", "Serie TV", "Riflessione", "Canzone".
- **Voce** (`Entry`): un'istanza di un modello con i valori compilati. Le voci possono collegarsi tra loro (una riflessione che cita un libro).
- Così aggiungere un tipo nuovo **non richiede codice**: è un dato.

## Architettura iniziale
```
src/zibaldone/
  core/      # blocchi, modelli, voci, validazione (nessuna dipendenza esterna)
  storage/   # voci come file Markdown + YAML (fonte di verità), SQLite come indice ricostruibile
  cli/       # comandi: zibaldone / zbone help, version, template ..., entry ...
  ui/        # dalla v0.3, sopra gli stessi moduli
  ai/        # dalla v0.5: trascrizione audio, analisi emotiva, tutto locale
tests/
docs/  utente/ tecnica/ decisioni/ versioni/ sviluppo/
```
Python 3.10+, `pyproject.toml`, CLI con Typer (help automatico), pytest. Sviluppo su **Windows/PowerShell** (niente WSL). Tester su **Android**: interfaccia con **Flet** e dati in **SQLite** con export Markdown (D-004, 2026-10-17).

> [!warning] Requisiti di Alex (2026-10-17)
> Sicurezza e dati solo in locale con avviso trasparente; Google Drive opzionale; patch e aggiornamenti a distanza per i tester Android; conformità a leggi italiane ed europee; IA rinviata. Documenti nella repo: `docs/tecnica/privacy-e-sicurezza.md`, `docs/tecnica/distribuzione.md`, `docs/tecnica/roadmap.md` (la roadmap aggiornata vive lì).

## Roadmap a passi piccoli
La roadmap aggiornata vive nella repo (`docs/tecnica/roadmap.md`). In breve: v0.2 cartella dati e avviso privacy · v0.3 modelli e voci con 4 blocchi · v0.4 altri blocchi e modelli pronti · v0.5 **pacchetti condivisibili** · v0.6 **storia e backup** (istantanee come commit) · v0.7 **cifratura** e backup fuori dal dispositivo (D-006) · v0.8 interfaccia Flet · v0.9 APK ai tester. Poi sincronizzazione, grafo, moduli delicati, Linux, IA.

> [!tip] Pacchetti di modelli (D-005)
> Una configurazione di blocchi si esporta in un file `.zbpack.json` e si passa ad altri. Lo stesso formato serve per i modelli pronti dell'app e, in futuro, per quelli che l'app consiglia. Solo struttura, mai dati personali. ADR-0005 nella repo.

Ogni versione: criteri di accettazione scritti prima, test, nota in `docs/versioni/`, voce nel CHANGELOG, tag git (che crea Alex).

## Decisioni aperte
- Formato dei dati e UI: decisi in D-004 (SQLite con export Markdown, Flet).
- Formato dei pacchetti: proposto in ADR-0005, da confermare alla v0.5.
