# ADR-0009 — Anonimizzatore per i futuri modelli di IA

- **Data**: 2026-10-17 · **Stato**: accettata (richiesta di Alex)
- **Contesto**: più avanti ZibaldOne userà modelli di IA generativa (consigli di lettura, riassunti, riflessioni). Un diario contiene nomi, contatti, luoghi e dati delicati. Prima che un testo arrivi a qualsiasi modello, anche locale, i dati personali vanno tolti.
- **Decisione**:
  - Un modulo `core/anonymizer.py`, **tutto locale**, che sostituisce i dati personali con segnaposto coerenti: `[PERSONA_1]`, `[EMAIL_1]`, `[TELEFONO_1]`, `[LUOGO_1]` …
  - **Due modalità**:
    - **pseudonimi reversibili**: la tabella segnaposto → valore resta sul dispositivo, così la risposta del modello può essere riportata ai nomi veri;
    - **anonimato**: la tabella si butta, il testo non è più riconducibile.
  - **Cosa riconosce** (prima versione, regole verificabili): email, telefoni italiani e internazionali, codice fiscale (con carattere di controllo), partita IVA, IBAN (controllo mod 97), carte di pagamento (algoritmo di Luhn), URL, indirizzi IP, indirizzi stradali italiani ("via", "piazza", "corso" …), date di nascita esplicite, e **nomi di persona** presi dalle voci *Persona* dell'utente e da un dizionario personale (con soprannomi).
  - **Più avanti**: riconoscimento di nomi e luoghi con un modello NER locale (per esempio spaCy italiano), come estensione opzionale.
  - **Misurato**: un piccolo insieme di frasi di prova etichettate e il comando `zbone anon eval` che calcola **precisione e richiamo** per tipo di dato.
  - **Trasparente**: `zbone anon preview "testo"` mostra cosa verrebbe sostituito prima di usarlo.
- **Conseguenze**:
  - Ogni futura funzione IA passa obbligatoriamente dall'anonimizzatore.
  - **GDPR**: i dati pseudonimizzati restano dati personali (considerando 26): l'anonimizzatore riduce il rischio, non lo azzera. La tabella dei pseudonimi va protetta come il resto dei dati (cifrata quando la cifratura è attiva).
  - Le regole sbagliano: meglio sostituire troppo che troppo poco (si privilegia il richiamo).
- **Alternative scartate**: mandare i testi così come sono; affidarsi solo a un modello NER (meno prevedibile e più pesante su Android).

## Nota 2026-10-17 (0.1.5)
Messo in pratica come deciso: `core/anonymizer.py` con le regole elencate sopra, `core/anon_eval.py` con 92 frasi di prova (precisione 96,7%, richiamo 95,6% al rilascio), `zbone anon preview/eval` e la prova nell'app in Impostazioni → Anonimizzatore. Il modello NER locale resta per dopo. Dettagli in [anonimizzatore](../tecnica/anonimizzatore.md).
