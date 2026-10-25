# ZibaldOne: kanban e sprint (2026-10-25)

Colonne: **Backlog** · **In corso** · **In revisione** · **Fatto**. Un task fermo in attesa di Alex è **🔒 Bloccato** (con il motivo).
Thread: Frontend (`ui/`), Backend (core, cloud, cli, storage, test), DevOps/SecOps (`.github/`, `.gitignore`), Git master (merge, tag, worktree), Vibe Coding (versione, CHANGELOG, docs).
Fonti: `team/feature-e-prossimi-passi.md`, `docs/tecnica/roadmap.md`, `team/google-drive-auth.md`, `team/handoffs/0.2.9-piano.md` e le richieste di Alex in chat. Regole: una versione = una capacità (ADR-0010); push e tag solo con l'ok esplicito di Alex; merge uno alla volta.
Lo stato di ogni riga è quello che risulta dai documenti, non l'ho riprovato sull'app. Il contenuto delle versioni 0.3.x e 0.4.0 è una proposta.

## Sprint 0.2.9 (corrente): fix residui
Obiettivo: versione per i tester senza regressioni nelle schermate toccate da Alex.

| Task | Thread | Stato | Dipende da |
|---|---|---|---|
| Patch 0.2.9 (plurali, errore viste, `install_base_packs`, onboarding, docs) | Backend, Frontend, Vibe Coding | In revisione (patch `finale/` pronte) | merge in `main` |
| Merge 0.2.9 in `main` e tag `zibaldone-v0.2.9` | Git master | Backlog 🔒 tag e push solo con ok esplicito di Alex | patch 0.2.9 |
| Tasto indietro del telefono: torna alla schermata precedente | Frontend | Backlog | — |
| Bozza salvata al tasto indietro (non si perde il testo) | Frontend | Backlog | tasto indietro |
| Modelli con icona invertita: correggere | Frontend | Backlog | — |
| Collezioni come pagine figlie (navigazione e indietro) | Frontend | Backlog | tasto indietro |
| Scorciatoie ai modelli in home | Frontend | Backlog | — |
| Versioni nei pacchetti Scuole (campo versione e aggiornamento) | Backend | Backlog | — |
| Carosello delle aree dentro Modelli: trascinando a destra o a sinistra cambia area, come il cambio di desktop su Arch Linux | Frontend | Backlog | — |
| Barra con le 8 mascotte in fondo come scorciatoia tra le aree | Frontend | Backlog | carosello |
| Test per i fix sopra | Backend | Backlog | i fix UI |

## Sprint 0.3.0: release unica
| Task | Thread | Stato | Dipende da |
|---|---|---|---|
| `release.yml`: zip Windows, APK e wheel con `SHA256SUMS`, «prerelease» fino alla 1.0 | DevOps/SecOps | Backlog | 0.2.9 in `main`; repo pubblico per Releases |
| Repo pubblico, licenza, protezione del ramo `main`, segreti | Alex | Backlog 🔒 solo Alex | decisione sulla licenza |
| Nota di versione, CHANGELOG, guida tester | Vibe Coding | Backlog | release.yml |
| Tag e push | Git master | Backlog 🔒 ok esplicito di Alex | tutto sopra |

## Sprint 0.3.1: prova dei tester su Windows
| Task | Thread | Stato | Dipende da |
|---|---|---|---|
| Raccolta feedback dei tester e correzioni (nessuna feature nuova) | Vibe Coding | Backlog | 0.3.0 |
| Misura con migliaia di voci e movimenti | Backend | Backlog | — |
| Layout home 5×6 con blocchi ridimensionabili | Frontend | Backlog 🔒 da decidere se è una capacità propria (ADR-0010) o va in questa versione; serve contratto in `core/home` | decisione di Alex |
| Barra delle 8 mascotte configurabile: sopra o a lato, a scomparsa o fissa, a scelta dell'utente | Frontend | Backlog | barra in fondo (0.2.9), impostazioni |
| Import e condivisione WhatsApp dei modelli (thread già aperto) | Backend, Frontend | In corso (thread dedicato) | formato `.zbpack.json`, ADR-0005 |

## Sprint 0.3.2: Android e Google provati davvero
| Task | Thread | Stato | Dipende da |
|---|---|---|---|
| Client OAuth di Google, utenti di test, keystore Android | Alex | Backlog 🔒 solo Alex | — |
| Accesso Google per Drive: obbligatorio o «continua solo in locale»? | Backend, Frontend | Backlog 🔒 decisione di Alex (ADR-0007) | decisione |
| Google in produzione o in test (token a 7 giorni) | Backend | Backlog 🔒 decisione di Alex | decisione |
| Token in chiaro su Android e Linux: spazio protetto del sistema | Backend, DevOps/SecOps | Backlog | prima della 1.0 |
| APK installato su telefono; flusso OAuth loopback su Android | Frontend, DevOps/SecOps | Backlog | client OAuth |
| Ripristino su dispositivo nuovo | Backend | Backlog | Drive provato |

## Sprint 0.3.3: promemoria veri dall'app
| Task | Thread | Stato | Dipende da |
|---|---|---|---|
| Notifiche da app (Windows e Android) al posto di `zbone remind install` | Backend, Frontend | Backlog | 0.3.1 |

## Sprint 0.3.4: firma e aggiornamento in app
| Task | Thread | Stato | Dipende da |
|---|---|---|---|
| Firma contro SmartScreen | DevOps/SecOps | Backlog 🔒 decisione di Alex (costo) | decisione |
| Scarica e installa la versione nuova dall'app | Backend, Frontend | Backlog | firma, 0.3.0 |

## Sprint 0.4.0: una capacità nuova
| Task | Thread | Stato | Dipende da |
|---|---|---|---|
| Scelta tra Documenti e carte (raccomandata), Password con Bitwarden, sincronizzazione continua, Linux | Alex | Backlog 🔒 decisione di Alex | 0.3.x |
| Implementazione della capacità scelta | Backend, Frontend | Backlog | scelta |

## Decisioni di Alex ancora aperte
1. Home 5×6 ridimensionabile: versione in cui metterla.
2. Accesso Google obbligatorio o facoltativo; Google in produzione o in test.
3. Firma di Windows (a pagamento).
4. Licenza e repository pubblico.
5. Capacità della 0.4.0.

## Non verificato
Stato reale dei fix UI e delle patch 0.2.9 sul PC; se i thread di WhatsApp e Drive hanno già prodotto codice; l'assegnazione di versione dei task fuori roadmap è una mia proposta.
