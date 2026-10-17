---
tags:
  - profilo
  - design
date: 2026-10-16
---
# Design e palette

Torna a [[00 - START HERE]] · usato in [[Nexus Metrics]], [[Odyssey - Diario del Pendolare]], [[Python Starter Kit]].

> [!abstract] In una riga
> **Dark / neon / cyberpunk**: sfondo quasi nero bluastro, pannelli leggermente più chiari, accenti ciano e arancio, palette categoriale satura. Font di sistema (`Inter, Segoe UI, sans-serif`), niente font remoti.

## Palette "Nexus neon" (Python / Plotly / Streamlit)
| Ruolo | Colore |
|---|---|
| Background | `#0D0E15` |
| Panel | `#141521` |
| Grid / bordi | `#1E2035` |
| Testo | `#E6F7FF` |
| Testo secondario | `#8A94A8` |
| Accento (primary) | `#00E5FF` |

`CYBER_PALETTE` (serie categoriali, in ordine): `#B3F3F6` `#FF5500` `#FFFF00` `#FF0000` `#74EE15` `#FF007F` `#8A2BE2`.

Fonte: `Personal Projects/LoL/Nexus_Metrics/src/visualization/theme.py` e `.streamlit/config.toml`. Il [[Python Starter Kit]] ha una versione precedente con testo `#007ACC`.

## Palette Odyssey (web app HTML/CSS)
`--bg-base #0B081A`, `--bg-surface #1A153A`, `--bg-highlight #231C4C`, `--border-color #3E3863`, `--primary #FF8C00` (hover `#FF5500`), `--secondary #00FFFF`, `--accent #00FF66`, `--danger #FF3333`, `--text-main #FFFFFF`, `--text-muted #8E8A9F`. Raggi 8/10/12 px, transizioni 0.2s.

## Obsidian
- Grassetto viola `rgb(138, 92, 245)` con peso 850 (snippet `MarcaturaViolaBold.css`, copiato anche qui in `.obsidian/snippets`).
- Titoli colorati con `<span style="color:#007ACC">` e `#FF5500`; callout `[!abstract]`, `[!warning]`; diagrammi mermaid.

## Regole pratiche
- **Non** usare la palette crema/rosso del sito di AI 4 Restaurants: non è di Alex e non gli piace (2026-10-17). Il default è sempre il neon scuro.
- Grafici: template Plotly scuro con `colorway = CYBER_PALETTE`, griglie discrete, hover su pannello con bordo accento.
- Dashboard: Streamlit, tema scuro, server su `127.0.0.1`, telemetria spenta.
- Da migliorare: contrasto e accessibilità (alcuni neon, come `#FFFF00` su chiaro, sono difficili da leggere).
