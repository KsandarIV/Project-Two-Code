# Anonimizzatore · Velo d'ignoranza (dalla 0.1.5)

Il *velo d'ignoranza* è di John Rawls (*Una teoria della giustizia*, 1971): si decide senza sapere chi si è. Qui è il passaggio obbligato prima che un testo del diario arrivi a un modello di IA generativa: i dati personali spariscono e al loro posto restano segnaposto come `[PERSONA_1]`. Le scelte sono in [ADR-0009](../decisioni/ADR-0009-anonimizzatore.md).

## Cosa riconosce
| Tipo | Come | Segnaposto |
|---|---|---|
| Nomi di persona | dal dizionario personale: nomi, cognomi e soprannomi delle voci *Persona*, anche scritti senza accento ("Nicolò", "Nicolo", "Nicolo'"); i nomi corti o che sono anche parole comuni solo con la maiuscola | `[PERSONA_1]` |
| Email | forma `nome@dominio` | `[EMAIL_1]` |
| Telefoni | italiani (fissi e cellulari) e internazionali con prefisso | `[TELEFONO_1]` |
| Codice fiscale | con il carattere di controllo verificato | `[CODICE_FISCALE_1]` |
| Partita IVA | con la cifra di controllo | `[PARTITA_IVA_1]` |
| IBAN | con il controllo mod 97 | `[IBAN_1]` |
| Carte di pagamento | con l'algoritmo di Luhn | `[CARTA_1]` |
| Indirizzi web e IP | URL, IPv4 e IPv6 | `[URL_1]`, `[IP_1]` |
| Indirizzi stradali | "via", "piazza", "corso", "viale" … con il civico | `[INDIRIZZO_1]` |
| Date di nascita | solo quando il testo lo dice ("nato il 3/4/1990") | `[DATA_NASCITA_1]` |
| Luoghi | da un dizionario di luoghi (per ora solo da codice: `Anonymizer(terms={"LUOGO": […]})`) | `[LUOGO_1]` |

Lo stesso valore prende sempre lo stesso segnaposto, anche scritto in modi diversi: "Giulia" e il soprannome "Giuli" diventano entrambi `[PERSONA_1]`, "333 123 4567" e "+39 3331234567" lo stesso `[TELEFONO_1]`. Quando due riconoscimenti si sovrappongono vince il più lungo, poi quello che viene prima nel testo.

## Due modalità
- **Pseudonimi reversibili** (`pseudo`): la tabella segnaposto → originale resta **in memoria**, così la risposta di un modello si può riportare ai nomi veri (`restore`). Non si salva mai su disco.
- **Anonimato** (`anon`): la tabella non si conserva e il testo non è più riconducibile.

Attenzione (GDPR, considerando 26): un testo con pseudonimi è ancora un dato personale, perché con la tabella si torna ai nomi. L'anonimizzatore riduce il rischio, non lo azzera.

## Quanto funziona
`zbone anon eval` misura le regole su 92 frasi di prova scritte apposta, con 91 dati da trovare (confronto esatto: stesso tipo e stessi caratteri). Con la 0.1.5:

| | Precisione | Richiamo |
|---|---|---|
| Nomi di persona | 94,6% | 92,1% |
| Date di nascita | 83,3% | 83,3% |
| Tutti gli altri tipi | 100% | 100% |
| **Totale** | **96,7%** | **95,6%** |

Le regole preferiscono sostituire troppo piuttosto che troppo poco. I nomi sfuggono quando non sono nel dizionario: per questo l'app avvisa se non ci sono voci Persona. `zbone anon eval --errors` mostra le frasi sbagliate.

## Dove si usa
- **App**: **Impostazioni → Anonimizzatore** (Velo d'ignoranza): scrivi o incolla un testo, o prendi l'ultima voce, scegli la modalità e guarda cosa verrebbe sostituito. Nulla viene salvato né inviato.
- **CLI**: `zbone anon preview "testo"` (`--mode anon`, `--names "Anna, Bruno"` per un dizionario a mano) e `zbone anon eval` ([guida rapida](../utente/guida-rapida.md#anonimizzatore--velo-dignoranza)).
- **In futuro**: ogni funzione di IA (riassunti, consigli, riflessioni) passerà di qui per forza, prima di qualsiasi modello, anche locale. Un riconoscitore di nomi con un modello locale (per esempio spaCy italiano) potrà aggiungersi come rilevatore in più: `Anonymizer(detectors=…)`.

## Codice
- `core/anonymizer.py`: rilevatori, controlli (Luhn, mod 97, codice fiscale, partita IVA), dizionario dei nomi, sovrapposizioni, segnaposto e ripristino. Solo libreria standard.
- `core/anon_eval.py`: le frasi di prova etichettate e il calcolo di precisione e richiamo.
- `cli/anon_cmd.py`; nell'app `ui/views/anonymizer.py` e `ui/viewmodels.py` (`anonymize_preview`).
- Test: `tests/test_anonymizer.py`, `tests/test_cli_anon.py`, più quelli dell'interfaccia.
