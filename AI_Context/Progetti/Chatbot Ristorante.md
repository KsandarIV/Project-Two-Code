---
tags:
  - progetto
  - genai
  - its
stato: svolto al corso (Applicazioni dell'IA, ottobre 2026)
repo: https://github.com/KsandarIV/AI_4_Restaurants
date: 2026-10-17
---
# Chatbot Ristorante — AI 4 Restaurants

Torna a [[00 - START HERE]] · vedi [[Percorso ITS]], [[Mappa competenze]].

> [!abstract] In breve
> Progetto di gruppo ITS ("Traccia 3"): prenotazione tavoli per la *Trattoria Bella Napoli* con **chatbot** e **voicebot** che parlano, via LAN, con un backend **FastAPI + LangGraph + Ollama (gemma4:12b) + SQLite**. Tutti i modelli sono locali.

## Dove sta
- Repo: https://github.com/KsandarIV/AI_4_Restaurants · copia locale `C:\Users\okami\Desktop\AI_RES\AI_4_Restaurants` (fuori da `GitHubRepository`).
- Branch per membro (`BELLOMO`, `difra`, `Lavalle-fix`, …). Alex lavora su **`savov`** e **`casa_savov`**. Non toccare i branch degli altri.

## Parti di Alex
- **voice/**: voicebot `voicebot` (Python ≥3.10, ~3700 righe, 150+ test pytest, `mypy --strict`, `ruff`). Pipeline asyncio: WebSocket PCM16 → **VAD** → **faster-whisper** (STT) → BE via HTTP/SSE → **Piper** (TTS), con barge-in, anonimizzatore PII (`anonymizer.py`, `pii.py`), `toolguard.py`, `doctor` diagnostico, riepilogo finale letto da codice e non dall'LLM, sito con "orb" animato e pagine tecniche (`/tech`, `/test-voice`). Modelfile `gemma4-voice` per PC deboli.
- **lan/**: configurazione delle tre macchine (`lan_config.json`, `machine_setup.py`).
- **entrypoint/**: `avvia.py`, un comando per macchina (git pull ff-only, setup per ruolo, `.env`, firewall, attesa del BE, avvio).
- **setup/**: `setup_env.py`, `env_check.py`, requirements per ruolo e venv condiviso.

## Cosa dice del suo stile
- Documentazione molto curata: README per componente, `PRODUZIONE.md` con checklist della prova generale, tabelle "se un passo si ferma → cosa fare".
- Privacy by design: nome e telefono vanno solo a `POST /api/customers`, l'LLM vede un `customer_id` anonimo.
- Diagnostica e messaggi d'errore pensati per l'utente; niente falsi successi.
- Qui codice e documentazione tecnica del voicebot sono in **inglese**; README di gruppo in italiano.

- La palette del sito del ristorante (crema/rosso) **non è di Alex e non gli piace**: non va riusata.

## Rilevanza
Base diretta per il binario "app IA" dell'opzione 0 e per l'opzione 2 (coach ad agente) del [[2026-10-16 Brainstorming nuovo progetto]]: lo schema LangGraph + tool + SQLite + Ollama è già collaudato.
