---
name: zb-release
description: Prepare a ZibaldOne release PR. Use on 'prepare release X.Y.Z' (DevOps & Release only).
---

1. Check every card of the version list is Done.
2. Bump `__version__` in `ZibaldOne/src/zibaldone/__init__.py`.
3. CHANGELOG entry from the merged PR titles.
4. `ZibaldOne/src/assets/novita/X.Y.Z.json`, written for users, in Italian.
5. `ZibaldOne/docs/versioni/vX.Y.Z.md` (release notes; the workflow fails without it).
6. Regenerate the code map (`docs/tecnica/mappa-codice.md`).
7. Open the PR from `release/X.Y.Z`. Merging it is Alex's yes: release.yml creates the tag and the prerelease.
8. Watch release.yml; report the release link or the failing job.
