# ZibaldOne: rules for Claude

ZibaldOne is a local-first personal app: Python 3.12, Flet UI, SQLite, Windows + Android. Free and open source.
Code is in `ZibaldOne/src/zibaldone/` (core, storage, cli, cloud, notify, packs, ui). Tests in `ZibaldOne/tests/`.

## Before you start
Read `ZibaldOne/docs/tecnica/mappa-codice.md` if it exists, then only the modules you need.

## Commands (run from `ZibaldOne/`)
- Install: `pip install -e ".[dev,ui]"`
- Tests: `python -m pytest -q`
- Lint: `ruff check --select E9,F63,F7,F82 src tests scripts`

## Code rules
- `core` never imports `ui`, `cli` or `storage`.
- Code, names, comments, docstrings: English. App text, user docs, Novità, commit subjects: Italian.
- Smallest complete change. No features nobody asked for.
- Secrets never in the repo.

## Git rules
- Branch `<type>/<number>-<slug>` (types: feat, fix, docs, ci, chore, refactor, test, release), one PR per branch.
- Conventional Commits, Italian subject: `fix(ui): il tasto indietro torna alla pagina precedente`.
- Fill `.github/pull_request_template.md`.
- Never push to `main`, never tag, never delete branches or files.

## Public repo: what may be committed
Only technical, explanatory, testing and usage docs (README, CHANGELOG, guides, version notes, ADRs, dev guides). Never work plans, team files, requirements, research, AI context or personal data.

## Skills
Repo skills in `.claude/skills/`: `zb-card`, `zb-pr`, `zb-release`, `zb-feedback`.
