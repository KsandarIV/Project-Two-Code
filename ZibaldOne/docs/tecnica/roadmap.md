# Roadmap fino alla 1.0

Numerazione ([ADR-0010](../decisioni/ADR-0010-numerazione-delle-versioni.md)): prima della 1.0 ogni versione `0.fase.capacità` aggiunge **una sola** capacità, con test, nota in `docs/versioni/` e voce nel CHANGELOG. Piattaforme: **Windows** (CLI e desktop) e **Android** (tester). Interfaccia con **Flet**, dati in **SQLite** ([ADR-0004](../decisioni/ADR-0004-flet-e-sqlite.md)). Le idee della vecchia Journal App sono riprese come **modelli**, non come codice fisso ([confronto](confronto-journal-app.md)).

## Fase 0.0: fondamenta
| Versione | Capacità | Stato |
|---|---|---|
| v0.0.1 | Scheletro: `help`, `version`, docs, test, CHANGELOG | ✅ |
| v0.0.2 | Cartella dati e trasparenza: avviso e consenso al primo avvio, `zbone privacy`, `zbone data path` | ✅ |
| v0.0.3 | **Modelli e voci**: tutti i 12 blocchi (`text`, `longtext`, `number`, `rating`, `tags`, `date`, `checklist`, `scale`, `choice`, `progress`, `bookmark`, `link`); modelli serializzabili; database SQLite con migrazioni; `zbone template …`, `zbone entry …` | ✅ |
| v0.0.4 | **Modelli pronti** e **identità**: pacchetti integrati Diario (3 momenti della giornata, 8 aree, revisioni), Collezioni, Io, Persone; nomi filosofici, mascotte e pensiero del giorno ([identità](../brand/identita.md)) | ✅ |
| v0.0.5 | **Pacchetti condivisibili** `.zbpack.json`: `zbone pack export/import` ([ADR-0005](../decisioni/ADR-0005-pacchetti-di-modelli.md)); commit e tag automatici a ogni versione ([versionamento](../sviluppo/versionamento.md)) | ✅ |
| v0.0.6 | **Storia e backup**: istantanee come commit, ripristino annullabile, durata a tempo, verifica; export Markdown e CSV ([ADR-0006](../decisioni/ADR-0006-storia-e-backup-cifrati.md)) | ✅ |
| v0.0.7 | **Cifratura**: passphrase e codice di recupero, backup sempre cifrati (AES-256-GCM + scrypt) | ✅ |
| v0.0.8 | **Account e cloud**: accesso con Google, scelta solo locale o locale + Drive, destinazioni intercambiabili, recupero con account Google, portare i dati su un altro dispositivo ([ADR-0007](../decisioni/ADR-0007-account-google-e-destinazioni-cloud.md)) | ✅ |
| v0.0.9 | **Notifiche** che spronano a scrivere: promemoria ai momenti della giornata, ore di silenzio, serie di giorni, toni gentili ([ADR-0008](../decisioni/ADR-0008-notifiche.md)) | ✅ |

## Fase 0.1: app per i tester
| Versione | Capacità | Stato |
|---|---|---|
| v0.1.0 | **Interfaccia grafica** Flet con tema neon: Oggi, Voci, Collezioni, Modelli, Impostazioni; stesso codice per Windows e Android | ⬜ |
| v0.1.1 | **Prima versione per i tester**: APK costruito da GitHub Actions, controllo aggiornamenti, guida tester | ⬜ |
| v0.1.2 | **Ricerca e collegamenti**: ricerca a testo pieno, filtri per tag e modello, collegamenti tra voci e "tutto su Marco" | ⬜ |
| v0.1.3 | **Grafo** stile Obsidian delle voci e dei collegamenti | ⬜ |
| v0.1.4 | **Statistiche e revisioni**: andamento dell'umore, punteggi delle aree per settimana e mese, collezioni in corso, revisione della settimana | ⬜ |
| v0.1.5 | **Anonimizzatore** per preparare i testi ai futuri modelli di IA generativa: pseudonimi reversibili, tutto in locale ([ADR-0009](../decisioni/ADR-0009-anonimizzatore.md)) | ⬜ |

> Ordine aggiornato il 2026-10-17: le notifiche (prima 0.1.1) vengono prima dell'interfaccia, perché l'interfaccia le usa (promemoria in app e serie di giorni). Interfaccia e prima versione per i tester scalano di una posizione.

## Fase 0.2: le 8 aree
Le richieste della vecchia Journal App (8 aree, persone complete, albero genealogico, dati sensibili cifrati, media, finanze, abitudini, viste componibili): [requisiti della fase 0.2](requisiti-v0.2.md).

## Verso la 1.0
La **1.0** è l'app davvero usabile, non un traguardo di calendario. Arriva dopo la fase 0.2, quando tutte queste cose sono vere:
- Alex e i tester la usano ogni giorno per almeno 4 settimane senza perdere dati e senza dover aprire il terminale.
- Si installa e si aggiorna da sola su Android e Windows; il primo avvio (accesso, privacy, modelli pronti) dura pochi minuti.
- Scrivere la voce della sera richiede pochi tocchi; cercare e ritrovare una voce è immediato.
- I backup automatici sono cifrati e un ripristino su un altro dispositivo è stato provato davvero.
- Nessun errore aperto che fa perdere dati o blocca l'app; la guida per chi la usa è completa.
- Licenza scelta e informativa privacy pubblicata.

## Dopo la 1.0
- Sincronizzazione continua PC ↔ telefono (oltre al ripristino da Drive della v0.0.8).
- Moduli delicati: Documenti e carte, Portafoglio e finanze, Password con Bitwarden (cifratura obbligatoria).
- Altri cloud configurabili (OneDrive, Dropbox, Nextcloud); pacchetti via link o QR e catalogo della comunità.
- Linux.
- **IA**: raccomandazioni di lettura da letture e riflessioni, configurazioni consigliate, trascrizione audio, emozioni, blocco ISBN. Sempre dopo l'anonimizzatore.

Moduli e principi: [visione](visione.md).
