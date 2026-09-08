# Phase 12 — Checkpoint 12.01

Status: **12.01 COMPLETE**

## Frozen Baseline

- Source branch created from `main`.
- Baseline `main` commit: `66343552b111fe6326e5564635aa84f807e82031`.
- Baseline source contains merged Help/User Guide PR #76.
- Application version: `0.1.0`.
- Database schema version: `11`.
- Project format ID: `SMPROJ`.
- Project format version: `1`.
- Project extension: `.smproj`.

## Automated Gate

GitHub Actions run #569 on Phase 12 roadmap head:

- Python compile: **success**.
- Full regression suite: **433 passed, 62 skipped**.
- Qt runtime suite: **59 passed**.
- UI scale smoke 100%: **3 passed**.
- UI scale smoke 125%: **3 passed**.
- UI scale smoke 150%: **3 passed**.

## Release Baseline Decision

The first packaged Windows release remains `v0.1.0`.

Splash Screen and About redesign are intentionally excluded from this baseline so they can be used to validate a real installed update from `v0.1.0` to the next release.

## Next

Proceed to **12.02 — Packaging Readiness Audit** before adding PyInstaller/Inno Setup implementation.
