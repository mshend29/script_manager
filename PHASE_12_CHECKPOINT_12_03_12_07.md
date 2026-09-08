# Phase 12 Checkpoint — 12.03 through 12.07

> Status: **12.03–12.07 implementation gates complete**
>
> Branch: `phase-12-first-windows-release`
>
> Accepted implementation head: `21d15fa53259a75cba1c8b81df45ade016d788a7`
>
> Release target remains **v0.1.0**.

## 12.03 — Windows Prerequisite Model — COMPLETE

Locked contract:

- Google Drive installation, running state, and filesystem readiness are separate states.
- Script Manager never assumes a fixed Google Drive letter such as `G:`.
- Existing Google Drive installations are skipped by the installer prerequisite page.
- Silent/CI installation never downloads or installs third-party software automatically.
- `/SKIPDRIVEPREREQ=1` is the narrow CI/managed deployment bypass.
- Google login and credentials always remain owned by Google Drive/user.
- Offline, cancelled, or managed-PC installation paths retain a manual fallback.

## 12.04 — Google Drive Prerequisite Detection — COMPLETE

Implementation:

- `services/windows_prerequisite_service.py`
- `tests/test_phase12_windows_prerequisite_detection.py`

Detection uses Google's documented Windows uninstall registration and checks both registry views. Folder names and fixed drive letters are not accepted as installation evidence.

## 12.05 — Official Google Drive Download / Install Flow — AUTOMATED COMPLETE

Implementation:

- `packaging/ScriptManager.iss`
- `tests/test_phase12_installer_prerequisite_contract.py`

Installer behavior:

- official `dl.google.com` installer endpoint only;
- Google installer downloaded to Inno Setup temporary storage;
- Google binary is not committed or bundled with Script Manager;
- user explicitly chooses `Install Google Drive & Lanjut` or manual setup;
- Google install result is checked when possible;
- download/install failures keep a manual fallback;
- CI bypass prevents GitHub-hosted runners from installing Google Drive.

Remaining gate:

- real-PC interactive UAT for missing/existing/cancel/offline Google Drive paths. This will be combined with installer UAT later in Phase 12.

## 12.06 — Google Drive First-Run Readiness UX — COMPLETE

Implementation:

- `GoogleDriveReadinessService`
- `dialogs/google_drive_readiness_dialog.py`
- `app/google_drive_readiness_controller.py`
- `tests/test_phase12_google_drive_readiness.py`
- `tests/test_phase12_qt_google_drive_readiness.py`

Readiness states:

1. `NOT_INSTALLED`
2. `INSTALLED_NOT_RUNNING`
3. `RUNNING_NOT_READY`
4. `READY`
5. diagnostic/error states

UX:

- one readiness notice per application version when setup is incomplete;
- always-available `Bantuan → Status Google Drive` action;
- `Buka Google Drive`;
- `Periksa Lagi`;
- official Google Drive help link;
- no credential/token access;
- no fixed drive-letter assumption.

The existing direct PROJECT-workspace startup contract remains preserved; no delayed Recent Projects-style startup dialog mechanism was reintroduced.

## 12.07 — PyInstaller / Frozen Build Configuration — COMPLETE

Release build hardening:

- windowed `ScriptManager.exe` (`console=False`);
- app icon and Windows version/product metadata embedded;
- runtime `resources/` included;
- no project/source/test dataset inclusion in the frozen spec;
- UPX disabled so output does not depend on developer-machine UPX availability;
- developer build contract remains `pyinstaller>=6.22,<7`;
- release/CI build uses exact `requirements-release.txt` lock:
  - `PySide6==6.11.2`
  - `openpyxl==3.1.5`
  - `pyinstaller==6.22.2`
- Windows Package and Release workflows use the same exact release dependency lock.

## Automated acceptance evidence

### Engine Tests #598

Run ID: `34179907342`

- Python compile: success
- full regression suite: **457 passed, 66 skipped**
- Qt runtime: success
- Phase 11 scale smoke: success

### Windows Package #77

Run ID: `34179907402`

All steps succeeded:

- exact release dependency install;
- Windows-native Google Drive readiness probe;
- PyInstaller build;
- frozen `ScriptManager.exe --smoke-test`;
- portable ZIP generation and upload;
- Inno Setup compile;
- silent installer install;
- installed frozen executable smoke test;
- `.smproj` association/icon/open-command verification;
- uninstall;
- installer artifact upload.

Artifacts from accepted head `21d15fa53259a75cba1c8b81df45ade016d788a7`:

- `ScriptManager-windows` — artifact ID `10038545368`
- `ScriptManager-windows-installer` — artifact ID `10038559453`

## Next

**12.08 — Portable Build v0.1.0 UAT**

The portable artifact must now be exercised on a real user Windows PC without Python/VS Code before 12.08 can be marked COMPLETE.
