# Setup su Windows (PowerShell)

ZibaldOne per ora è pensato **solo per Windows**. Tutti i comandi si lanciano da **PowerShell**.

```powershell
cd C:\Users\okami\Desktop\ProjectTwoCode\Project-Two-Code\ZibaldOne
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
zbone help
```

Se PowerShell blocca `Activate.ps1`, una volta sola: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Comandi utili
| Comando | Cosa fa |
|---|---|
| `zbone help` | elenco comandi |
| `zbone version` | versione installata |
| `zbone privacy` | avviso, cartella dati e consenso |
| `zbone data path` | percorso della cartella dati |
| `$env:ZIBALDONE_HOME = "$PWD\prova-dati"` | usa una cartella di prova invece di quella vera (solo in questa finestra) |
| `pytest` | tutti i test |
| `pytest -k help` | solo i test che contengono "help" |

## Rilascio di una versione
1. Aggiorna `version` in `pyproject.toml` e `__version__` in `src/zibaldone/__init__.py`.
2. Sposta le voci da `[Unreleased]` alla nuova versione nel `CHANGELOG.md`.
3. Scrivi `docs/versioni/vX.Y.Z.md`.
4. Commit e tag `vX.Y.Z` (li fa Alex), poi una release su GitHub per i tester (vedi [distribuzione](../tecnica/distribuzione.md)).
