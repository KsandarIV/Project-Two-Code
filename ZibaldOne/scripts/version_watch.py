"""Watch the ZibaldOne version and commit automatically when it changes.

The version lives in one place: `src/zibaldone/__init__.py` (`__version__`);
`pyproject.toml` reads it from there. Start the watcher once and leave it on:

    py scripts/version_watch.py            # watch, commit and tag on every change
    py scripts/version_watch.py --push     # also push commit and tag to GitHub
    py scripts/version_watch.py --once     # check now and exit (useful in scripts)

To keep it running in the background on Windows without a window:
    Start-Process pythonw -ArgumentList "scripts/version_watch.py" -WindowStyle Hidden

When `__version__` goes from 0.0.2 to 0.0.3 the watcher moves the [Unreleased]
changelog entries under 0.0.3 (unless that section already exists; with no
entries it writes a placeholder line to fill in later), creates
`docs/versioni/v0.0.3.md` if missing, commits the ZibaldOne folder with
"release: ZibaldOne v0.0.3" and adds the tag `zibaldone-v0.0.3`.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from release import (  # noqa: E402
    PROJECT_DIR,
    TAG_PREFIX,
    VERSION_FILE,
    ReleaseError,
    commit_release,
    git_root,
    parse_version,
    read_version,
    tag_exists,
)

POLL_SECONDS = 2.0
SETTLE_SECONDS = 3.0


def committed_version() -> Optional[str]:
    """The version in the last commit (HEAD), or None if there is none yet."""
    root = git_root()
    relative = VERSION_FILE.relative_to(root).as_posix()
    result = subprocess.run(["git", "show", f"HEAD:{relative}"], cwd=root, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    try:
        return read_version(result.stdout)
    except ReleaseError:
        return None


def check_and_release(push: bool = False, log: Callable[[str], None] = print) -> Optional[str]:
    """Commit and tag if the working version is newer than the committed one."""
    current = read_version(VERSION_FILE.read_text(encoding="utf-8"))
    previous = committed_version()
    if previous is None or current == previous:
        return None
    if parse_version(current) < parse_version(previous):
        log(f"La versione è scesa ({previous} -> {current}): nessun commit.")
        return None
    if tag_exists(git_root(), f"{TAG_PREFIX}{current}"):
        log(f"Il tag {TAG_PREFIX}{current} esiste già: nessun commit.")
        return None
    log(f"Versione cambiata: {previous} -> {current}. Faccio commit e tag…")
    tag = commit_release(current, push=push, allow_empty=True)
    log(f"Fatto: {tag}" + (" (inviato a GitHub)" if push else ""))
    return tag


def watch(push: bool, poll: float = POLL_SECONDS, settle: float = SETTLE_SECONDS) -> None:
    log = lambda message: print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)  # noqa: E731
    log(f"Controllo {VERSION_FILE.relative_to(PROJECT_DIR)}. Ctrl+C per fermare.")
    last_seen = VERSION_FILE.stat().st_mtime
    check_and_release(push, log)
    while True:
        time.sleep(poll)
        modified = VERSION_FILE.stat().st_mtime
        if modified == last_seen:
            continue
        # Wait until the file stops changing (editors save in several steps).
        time.sleep(settle)
        last_seen = VERSION_FILE.stat().st_mtime
        try:
            check_and_release(push, log)
        except ReleaseError as error:
            log(f"Errore: {error}")


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Commit e tag automatici quando cambia la versione di ZibaldOne.")
    parser.add_argument("--once", action="store_true", help="controlla una volta ed esci")
    parser.add_argument("--push", action="store_true", help="invia anche commit e tag a GitHub")
    args = parser.parse_args(argv)
    try:
        if args.once:
            check_and_release(args.push)
        else:
            watch(args.push)
    except ReleaseError as error:
        print(f"Errore: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nWatcher fermato.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
