# ZibaldOne: rules for Claude

ZibaldOne is a local-first personal app: Python 3.12, Flet UI, SQLite, Windows + Android. Free and open source: never propose paid or premium features.
Code is in `ZibaldOne/src/zibaldone/` (core, storage, cli, cloud, notify, packs, ui). Tests in `ZibaldOne/tests/`.

## Before you start
1. Read the card you are working on (Trello, link given by the coordinator).
2. Read `ZibaldOne/docs/tecnica/mappa-codice.md` if it exists, then only the modules you need.
3. Use the `zb-card` skill to write the plan and the branch name.

## Commands (run from `ZibaldOne/`)
- Install: `pip install -e ".[dev,ui]"`
- Tests: `python -m pytest -q`
- Lint: `ruff check --select E9,F63,F7,F82 src tests scripts`

## Code rules
- `core` never imports `ui`, `cli` or `storage`.
- Code, names, comments, docstrings: English. App text, user docs, Novità, commit subjects: Italian.
- Smallest complete change (ponytail). No features the card does not ask for.
- Secrets never in the repo, chat or Trello.

## Git rules
- One card = one branch `<type>/<card#>-<slug>` = one PR. Types: feat, fix, docs, ci, chore, refactor, test, release.
- Conventional Commits, Italian subject: `fix(ui): il tasto indietro torna alla pagina precedente`.
- PR body starts with `Trello: <card URL>`; fill `.github/pull_request_template.md`. Use the `zb-pr` skill.
- Never push to `main`, never merge, never tag, never delete branches or files. Alex merges every PR (squash).
- Never run git on Alex's PC.

## Public repo: what may be committed
Only technical, explanatory, testing and usage docs (README, CHANGELOG, guides, version notes, ADRs, dev guides). Never work plans, team files, requirements, research, AI context or personal data.

## Skills
Repo skills in `.claude/skills/`: `zb-card`, `zb-pr`, `zb-release`, `zb-feedback`. The others Alex uses (agent-skills, context7, 21mcp, later strix) are global on his PC; cloud threads do not see them.

## Talking to Alex
English, short, plain (Italian is fine if he writes it). One message when the PR is green or when you are blocked. End with what you skipped or did not check, and the risks.
