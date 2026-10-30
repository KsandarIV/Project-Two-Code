---
name: zb-pr
description: Open a ZibaldOne pull request when code is ready. Use on 'open the PR'.
---

1. Run tests and ruff from `ZibaldOne/`; stop if red.
2. Check the layer rule and that app text is Italian.
3. Write the PR title (Conventional Commit, Italian subject) and body from `.github/pull_request_template.md`, starting with `Trello: <card URL>`.
4. Push the branch and open the PR. Never push to main.
5. Comment the PR link on the card (end with `— <Role> thread`) and move it to In review.
