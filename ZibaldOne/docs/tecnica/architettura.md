# Architettura

## Concetti
- **Blocco**: un tipo di campo con regole (`text`, `number`, `rating`, `tags`, `slider`, `bookmark`, …).
- **Modello**: una ricetta dell'utente, cioè una lista ordinata di blocchi con nome (es. "Libro").
- **Voce**: un'istanza di un modello con i valori compilati.

- **Pacchetto**: un file `.zbpack.json` con uno o più modelli, da condividere o importare; contiene solo struttura, mai voci ([ADR-0005](../decisioni/ADR-0005-pacchetti-di-modelli.md)).

Aggiungere un tipo nuovo non richiede codice: un modello è un dato, e quindi si può esportare e condividere.

## Moduli
```
src/zibaldone/
  core/      dominio: blocchi, modelli, voci, validazione (nessuna dipendenza esterna)
  storage/   persistenza nella cartella dati dell'utente (dalla v0.0.2)
  cli/       comandi Typer: zibaldone / zbone
  ui/        interfaccia grafica (dalla v0.0.8), sopra gli stessi moduli
  ai/        funzioni IA (rinviate: si definiranno molto più avanti)
```
Regola: `cli/` e `ui/` chiamano `core/` e `storage/`, mai il contrario.

## Moduli funzionali
Diario, Collezioni, Documenti, Finanze, Password, Grafo, Raccomandazioni: ognuno sarà un sottopacchetto in `src/zibaldone/modules/` che usa solo il cuore. Dettagli in [visione](visione.md).
