# Script Manager v0.1.0 — Release Candidate

> Phase 12 / milestone 12.16
>
> Status: **FINAL CI GATE**
>
> Branch: `phase-12-first-windows-release`
>
> PR: #77

## Frozen baseline identity

- Application: `Script Manager`
- Version: `0.1.0`
- Windows target: x64-compatible
- Project extension: `.smproj`
- Project format ID: `SMPROJ`
- Project format version: `1`
- Database schema version: `11`
- Windows file type display name: `Script Manager Project`
- Default installed location: `C:\Program Files\Script Manager`
- Installer scope: administrative / machine-wide application and file association
- Portable format: PyInstaller onedir ZIP
- Installer format: Inno Setup 6.7.1 EXE

## Release candidate acceptance evidence

### Application/runtime

- [x] Python compile gate passes.
- [x] Full regression suite passes.
- [x] Qt runtime smoke passes.
- [x] Phase 11 scale smoke passes at 100%, 125%, and 150%.
- [x] PyInstaller frozen application builds from clean Windows CI.
- [x] Frozen runtime smoke passes.
- [x] Packaged diagnostics smoke passes.
- [x] Windows application/version identity is verified from the real EXE.

### Project format / association

- [x] `.smproj` open command is quoted safely.
- [x] Spaces and Unicode path smoke passes on frozen and installed EXE.
- [x] Machine-wide `.smproj` ProgID registration passes.
- [x] Project icon registration passes.
- [x] Existing project UAT passes on a real Windows PC.

### Installer / upgrade / data safety

- [x] Inno Setup compiler gate passes.
- [x] Installer identity/version metadata is verified from the real Setup EXE.
- [x] Installer defaults to Program Files.
- [x] Real-PC install/launch/uninstall UAT accepted.
- [x] Install-over-existing smoke passes.
- [x] Uninstall removes application files/registrations.
- [x] External `.smproj` survives uninstall.
- [x] Source/audio/delivery/backup sentinels survive uninstall.
- [x] Existing project remains usable after installer testing.

### Distribution/reproducibility

- [x] Exact release dependencies are pinned in `requirements-release.txt`.
- [x] Windows Package produces portable ZIP.
- [x] Windows Package produces installer EXE.
- [x] Windows Package generates SHA-256 checksums.
- [x] Release workflow rejects a tag that does not match `APP_VERSION`.
- [x] Release workflow rebuilds portable + installer from the release tag.
- [x] Release workflow generates checksums before publication.
- [x] Release workflow verifies the published release through the updater path.

## Deferred items — not blockers for v0.1.0 baseline

- Windows Authenticode/code signing and SmartScreen reputation.
- Google Drive missing/download/cancel/offline UAT on Sandbox/VM.
- Splash Screen redesign.
- About redesign.
- Silent auto-update.
- macOS packaging/signing/notarization.
- Multi-user concurrent `.smproj` access.

The current repository license remains Apache License 2.0; Phase 12 does not change licensing.

## Draft GitHub Release Notes

### Script Manager 0.1.0

First packaged Windows baseline for Script Manager, an application for managing short-form vertical drama scripts, dialogue recording workflow, character/talent resolution, tracking/stem status, and delivery.

#### Highlights

- Single-file `.smproj` project format backed by SQLite.
- New Project, Open/Recent, Save/Save As, Duplicate, Recover, and Project Settings workflows.
- Source Excel Sync pipeline with scan/fingerprint, inspect, parse, normalize, character/talent resolution, validation, and transactional project commit.
- Script/NASKAH and DIALOG workspace flows with persisted recording status and character/talent mapping.
- TRACKING and DELIVERY workflow support, including revision-aware naming behavior.
- Backup/recovery, diagnostics, audit history, local crash logging, and offline Help/User Guide.
- Manual Check for Updates through GitHub Releases.
- Windows `.smproj` file association with project icon and direct project opening.
- Portable Windows ZIP and Program Files installer.
- Google Drive for desktop prerequisite/readiness guidance for Drive-backed workflows.

#### Windows installation

The installer defaults to:

```text
C:\Program Files\Script Manager
```

Installation requires Windows administrator/UAC approval because the application and `.smproj` association are installed machine-wide.

Google Drive for desktop is used for workflows that point to Google Drive folders. Existing Google Drive installations are detected; Google account login remains entirely inside Google Drive.

#### Known baseline note

v0.1.0 is currently unsigned. Windows SmartScreen may display `Unknown publisher` / `Windows protected your PC`. Trusted code signing is intentionally deferred to later release hardening.

#### Data safety

Uninstalling Script Manager does not intentionally remove project `.smproj` files, project backups, source Excel files, audio/stem material, or delivery output stored outside the application install directory.

## Publication guard

**Do not create or push tag `v0.1.0` and do not publish a GitHub Release until the user explicitly approves publication.**

When approval is given, publication should happen only after PR #77 has been accepted/merged according to the project release procedure.
