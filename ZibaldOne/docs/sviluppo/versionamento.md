# Versionamento automatico

La versione di ZibaldOne sta in **un solo posto**: `src/zibaldone/__init__.py` (`__version__ = "X.Y.Z"`). `pyproject.toml` la legge da lì. Le versioni seguono [SemVer](https://semver.org/lang/it/) e ogni versione ha un tag `zibaldone-vX.Y.Z` (il prefisso serve perché la repo può contenere altri progetti).

## Il watcher: commit automatico quando cambia la versione
Si avvia una volta e resta acceso. Appena `__version__` cambia (per esempio da 0.2.0 a 0.3.0):
1. sposta le voci di `[Unreleased]` del CHANGELOG sotto `[0.3.0]` (se la sezione non esiste già; se non ci sono voci scrive una riga da completare);
2. crea `docs/versioni/v0.0.3.md` se manca;
3. fa il commit della cartella `ZibaldOne` con il messaggio `release: ZibaldOne v0.0.3`;
4. aggiunge il tag `zibaldone-v0.0.3`.

```powershell
cd C:\Users\okami\Desktop\ProjectTwoCode\Project-Two-Code\ZibaldOne
py scripts/version_watch.py            # resta in ascolto (Ctrl+C per fermarlo)
py scripts/version_watch.py --push     # in più invia commit e tag a GitHub
py scripts/version_watch.py --once     # controlla una volta ed esce
# in background, senza finestra:
Start-Process pythonw -ArgumentList "scripts/version_watch.py" -WindowStyle Hidden
```

Il watcher non fa nulla se la versione scende o se il tag esiste già. Il push è spento di base: si attiva con `--push`.

## Rilascio a mano
Per cambiare versione e fare il commit in un colpo solo, con i test prima:
```powershell
py scripts/release.py minor            # 0.3.0 -> 0.4.0 (anche: patch, major, oppure 0.4.0)
py scripts/release.py minor --dry-run  # mostra cosa farebbe
py scripts/release.py minor --push
```

## Regole
- Una capacità nuova per versione, descritta nel CHANGELOG sotto `[Unreleased]` mentre ci si lavora.
- Un test (`tests/test_release.py`) controlla che la versione corrente abbia la sua sezione nel CHANGELOG e la sua nota in `docs/versioni/`.
- Il database ha un suo numero di schema (`PRAGMA user_version`), indipendente dalla versione dell'app: cambia solo quando serve una migrazione.
