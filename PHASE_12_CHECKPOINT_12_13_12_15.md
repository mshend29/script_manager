# Phase 12 — Checkpoint 12.13–12.15

> Branch: `phase-12-first-windows-release`
>
> PR: #77
>
> Baseline version: `0.1.0`

## 12.13 — Windows Installer UAT

**Status: ACCEPTED FOR v0.1.0 BASELINE**

User UAT confirmed on a real Windows PC:

- [x] Installer launches and completes normally.
- [x] Latest installer defaults to `C:\Program Files\Script Manager`.
- [x] UAC/admin install behavior is acceptable.
- [x] Installed application launches normally.
- [x] Uninstall completes normally.
- [x] Existing/old project can still be opened without issue.
- [x] Google Drive already-installed path does not block installation.

Automated Windows Package coverage additionally confirms:

- [x] `.smproj` association is machine-wide (`HKLM\Software\Classes`).
- [x] Installed EXE can open `.smproj` paths containing spaces and Unicode.
- [x] Project icon/open-command registration is correct.
- [x] Install-over-existing succeeds.
- [x] Uninstall removes app registration while leaving external project/data sentinels untouched.

Deferred, non-blocking baseline items:

- Google Drive missing/download/cancel/offline flow will be tested later in Windows Sandbox/VM rather than by removing Drive from the production PC.
- Windows SmartScreen/code signing is deferred to release hardening. Unsigned v0.1.0 may show `Unknown publisher` / `Windows protected your PC`.

## 12.14 — User Data & Upgrade Safety

**Status: COMPLETE**

Evidence:

- [x] Real-PC uninstall completed without issue.
- [x] Existing project remains usable.
- [x] CI verifies external `.smproj` survives uninstall.
- [x] CI verifies source/audio/delivery/backup sentinel files survive uninstall.
- [x] CI verifies install-over-existing and runtime-after-upgrade.
- [x] Installer contains no uninstall rule targeting project/source/audio/delivery/backup paths.

The installer owns the application installation tree and Windows registrations only; project and external production data remain outside that ownership boundary.

## 12.15 — Build Automation / Release Reproducibility

**Status: IN FINAL GATE**

Implemented:

- [x] Windows GitHub Actions build workflow.
- [x] Exact-pinned release dependencies.
- [x] PyInstaller frozen build.
- [x] Inno Setup 6.7.1 installer compile.
- [x] Application/installer version metadata verification.
- [x] Frozen + installed diagnostics smoke.
- [x] Machine-wide `.smproj` association smoke.
- [x] Install-over-existing / uninstall / external-data safety smoke.
- [x] Portable artifact upload.
- [x] Installer artifact upload.
- [x] SHA-256 generation added to PR packaging workflow.
- [x] SHA-256 artifact upload added to PR packaging workflow.
- [x] Tag release workflow validates `v<APP_VERSION>`.
- [x] Tag release workflow uses exact release requirements and Inno version.
- [x] Tag release workflow synchronized to machine-wide association and packaged diagnostics.
- [x] Tag release workflow generates SHA-256 before publishing.

12.15 becomes COMPLETE after the Windows Package run on the final reproducibility head confirms the checksum artifact is actually produced.

## Signing policy for v0.1.0

Code signing is intentionally **not** a v0.1.0 baseline blocker. No self-signed workaround will be added. A trusted signing provider / SignPath / Store path can be evaluated after the first baseline release and update-lifecycle validation.

## Publication guard

No `v0.1.0` tag and no GitHub Release may be created until explicit user approval is given after 12.16 Release Candidate review.
