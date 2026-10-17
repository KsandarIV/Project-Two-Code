"""Release ZibaldOne: bump the version, update the changelog, commit and tag.

Usage (PowerShell, from the ZibaldOne folder):
    py scripts/release.py 0.3.0          # explicit version
    py scripts/release.py minor          # 0.2.0 -> 0.3.0 (also: patch, major)
    py scripts/release.py minor --dry-run
    py scripts/release.py minor --push   # also push the commit and the tag

The commit contains every change inside the ZibaldOne folder. Tags are named
`zibaldone-vX.Y.Z` because the repository can hold other projects too.
"""

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple

PROJECT_DIR = Path(__file__).resolve().parent.parent
VERSION_FILE = PROJECT_DIR / "src" / "zibaldone" / "__init__.py"
CHANGELOG_FILE = PROJECT_DIR / "CHANGELOG.md"
NOTES_DIR = PROJECT_DIR / "docs" / "versioni"
TAG_PREFIX = "zibaldone-v"

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
VERSION_LINE = re.compile(r'^__version__ = "([^"]+)"$', re.MULTILINE)


class ReleaseError(Exception):
    """A release step failed; nothing after it was done."""


def parse_version(text: str) -> Tuple[int, int, int]:
    match = SEMVER.match(text.strip())
    if not match:
        raise ReleaseError(f"'{text}' non è una versione X.Y.Z")
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def next_version(current: str, requested: str) -> str:
    """Return the new version from 'patch' / 'minor' / 'major' or an explicit X.Y.Z."""
    major, minor, patch = parse_version(current)
    if requested == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if requested == "minor":
        return f"{major}.{minor + 1}.0"
    if requested == "major":
        return f"{major + 1}.0.0"
    if parse_version(requested) <= (major, minor, patch):
        raise ReleaseError(f"la nuova versione {requested} deve essere maggiore di {current}")
    return requested


def read_version(source: str) -> str:
    match = VERSION_LINE.search(source)
    if not match:
        raise ReleaseError("__version__ non trovato in src/zibaldone/__init__.py")
    return match.group(1)


def write_version(source: str, version: str) -> str:
    return VERSION_LINE.sub(f'__version__ = "{version}"', source, count=1)


EMPTY_NOTES = "- Nessuna nota scritta per questa versione."


def release_changelog(changelog: str, version: str, day: str, allow_empty: bool = False) -> str:
    """Move the [Unreleased] entries under a new [version] heading.

    If the version already has its own section, nothing changes. With
    allow_empty=True (automatic commits) a missing note becomes a placeholder.
    """
    heading = f"## [{version}]"
    unreleased = re.search(r"^## \[Unreleased\]\n(.*?)(?=^## \[|\Z)", changelog, re.MULTILINE | re.DOTALL)
    if heading in changelog:
        return changelog
    if not unreleased:
        raise ReleaseError("il CHANGELOG non ha la sezione [Unreleased]")
    body = unreleased.group(1).strip()
    if not body:
        if not allow_empty:
            raise ReleaseError("il CHANGELOG non ha voci in [Unreleased] né una sezione per questa versione")
        body = EMPTY_NOTES
    replacement = f"## [Unreleased]\n\n{heading} — {day}\n{body}\n\n"
    return changelog[: unreleased.start()] + replacement + changelog[unreleased.end():]


def notes_stub(version: str, day: str) -> str:
    return (
        f"# v{version}\n\n- **Data**: {day}\n- **Contiene**: vedi il [CHANGELOG](../../CHANGELOG.md).\n"
        "- **Criteri di accettazione**\n  - [x] `pytest` passa.\n"
    )


def run(command: List[str], dry_run: bool, cwd: Path = PROJECT_DIR) -> str:
    print("  $ " + " ".join(command))
    if dry_run:
        return ""
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ReleaseError(f"comando fallito: {' '.join(command)}\n{result.stdout}{result.stderr}")
    return result.stdout


def git_root() -> Path:
    output = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=PROJECT_DIR, capture_output=True, text=True)
    if output.returncode != 0:
        raise ReleaseError("questa cartella non è dentro una repository git")
    return Path(output.stdout.strip())


def tag_exists(root: Path, tag: str) -> bool:
    output = subprocess.run(["git", "tag", "--list", tag], cwd=root, capture_output=True, text=True).stdout
    return bool(output.strip())


def commit_release(version: str, dry_run: bool = False, push: bool = False, allow_empty: bool = False) -> str:
    """Changelog, version note, commit and tag for a version already written in __init__.py."""
    day = date.today().isoformat()
    tag = f"{TAG_PREFIX}{version}"
    root = git_root()
    project = PROJECT_DIR.relative_to(root).as_posix() or "."
    if tag_exists(root, tag):
        raise ReleaseError(f"il tag {tag} esiste già")
    changelog = release_changelog(CHANGELOG_FILE.read_text(encoding="utf-8"), version, day, allow_empty)
    notes = NOTES_DIR / f"v{version}.md"
    if not dry_run:
        CHANGELOG_FILE.write_text(changelog, encoding="utf-8")
        if not notes.exists():
            notes.write_text(notes_stub(version, day), encoding="utf-8")
    run(["git", "add", "--", project], dry_run, cwd=root)
    run(["git", "commit", "-m", f"release: ZibaldOne v{version}"], dry_run, cwd=root)
    run(["git", "tag", "-a", tag, "-m", f"ZibaldOne v{version}"], dry_run, cwd=root)
    if push:
        run(["git", "push", "origin", "HEAD"], dry_run, cwd=root)
        run(["git", "push", "origin", tag], dry_run, cwd=root)
    return tag


def release(requested: str, dry_run: bool, run_tests: bool, push: bool, assume_yes: bool) -> str:
    source = VERSION_FILE.read_text(encoding="utf-8")
    current = read_version(source)
    version = next_version(current, requested)
    tag = f"{TAG_PREFIX}{version}"
    root = git_root()
    project = PROJECT_DIR.relative_to(root).as_posix() or "."
    if tag_exists(root, tag):
        raise ReleaseError(f"il tag {tag} esiste già")

    print(f"ZibaldOne {current} -> {version} (tag {tag}){' [prova, non cambio nulla]' if dry_run else ''}")
    status = subprocess.run(["git", "status", "--short", "--", project], cwd=root, capture_output=True, text=True).stdout
    print("Modifiche che entrano nel commit:\n" + (status or "  (nessuna oltre alla versione)\n"))
    if not dry_run and not assume_yes:
        if input("Procedo? (sì/no) ").strip().lower() not in ("s", "si", "sì", "y", "yes"):
            raise ReleaseError("annullato")
    if run_tests:
        print("Lancio i test…")
        run([sys.executable, "-m", "pytest", "-q"], dry_run)
    if not dry_run:
        VERSION_FILE.write_text(write_version(source, version), encoding="utf-8")
    commit_release(version, dry_run, push)
    print(f"Fatto: v{version}" + ("" if push else f". Per pubblicare: git push origin HEAD; git push origin {tag}"))
    return version


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Rilascia una nuova versione di ZibaldOne con commit e tag automatici.")
    parser.add_argument("version", help="patch, minor, major oppure una versione X.Y.Z")
    parser.add_argument("--dry-run", action="store_true", help="mostra cosa farebbe senza cambiare nulla")
    parser.add_argument("--no-tests", action="store_true", help="salta i test (sconsigliato)")
    parser.add_argument("--push", action="store_true", help="invia commit e tag a GitHub")
    parser.add_argument("--yes", action="store_true", help="non chiedere conferma")
    args = parser.parse_args(argv)
    try:
        release(args.version, args.dry_run, not args.no_tests, args.push, args.yes)
    except ReleaseError as error:
        print(f"Errore: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
