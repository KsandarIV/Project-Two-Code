# ADR-0005 — Pacchetti di modelli condivisibili

- **Data**: 2026-10-17 · **Stato**: proposta (idea di Alex, formato da confermare alla v0.0.5)
- **Contesto**: la configurazione di blocchi di un utente può piacere a un altro. L'app stessa fornirà configurazioni pronte, e un giorno potrà consigliarne. Serve un modo semplice per crearle e condividerle.
- **Decisione**:
  - Un **pacchetto** è un file che contiene uno o più **modelli** (blocchi, ordine, etichette, opzioni). Contiene **solo la struttura, mai le voci** dell'utente: condividere un pacchetto non condivide dati personali.
  - Formato: **JSON** leggibile, estensione `.zbpack.json`, con un'intestazione: `id`, `nome`, `versione` del pacchetto, `autore`, `licenza`, `descrizione`, `formato` (versione del formato dei pacchetti) e `blocchi_richiesti` (tipi di blocco usati).
  - **Un solo formato per tutte le fonti**: i modelli pronti dell'app, quelli esportati dagli utenti e, in futuro, quelli consigliati dall'app o presi da un catalogo usano lo stesso file.
  - Il pacchetto è **solo dati, mai codice**. All'import l'app controlla il formato, rifiuta tipi di blocco sconosciuti o campi non previsti, limita la dimensione e mostra un'anteprima prima di installare.
  - Un modello importato diventa una **copia dell'utente**: si può modificare senza toccare l'originale. Si conserva la provenienza (pacchetto, autore, versione) per gli aggiornamenti futuri.
- **Comandi previsti**: `zbone pack export <modelli> -o file`, `zbone pack import <file>` (con anteprima e conferma), `zbone pack list`, `zbone pack show <file>`.
- **Conseguenze**:
  - Dalla **v0.0.3** i modelli si descrivono in modo dichiarativo e serializzabile: un modello deve poter diventare JSON e tornare indietro senza perdite.
  - Dalla **v0.0.4** i modelli pronti dell'app (Libro, Diario del giorno, ...) sono pacchetti integrati, scritti nello stesso formato.
  - Alla **v0.0.5** export, import e anteprima dei pacchetti.
  - In futuro: condivisione via link o QR, un catalogo di pacchetti della comunità e i consigli dell'app (parte IA, rinviata). Un catalogo pubblico richiederà regole di moderazione e licenza.
- **Alternative scartate**: copiare i modelli a mano; condividere l'intero database (porterebbe con sé i dati personali); pacchetti con codice o script (rischio di sicurezza).
