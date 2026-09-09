# Phase 12 — Packaging Readiness Audit

Status: **12.02 COMPLETE**

Baseline: `66343552b111fe6326e5564635aa84f807e82031`

This audit was performed before changing the Windows packaging implementation.

---

## 1. Executive Result

Script Manager is **not starting packaging from zero**.

The repository already contains a substantial Windows release foundation:

- `requirements-build.txt` with PyInstaller;
- `packaging/ScriptManager.spec`;
- `packaging/ScriptManager.iss`;
- `.github/workflows/windows-package.yml`;
- `.github/workflows/release.yml`;
- frozen executable smoke test;
- portable ZIP build;
- per-user Inno Setup installer;
- `.smproj` file association;
- installer silent-install smoke test;
- SHA-256 generation;
- GitHub Release publishing;
- published-release verification through the updater.

Therefore Phase 12 should **harden and extend the existing pipeline**, not replace it.

---

## 2. Existing Packaging Strengths

### 2.1 Frozen-resource support already exists

`core/resource_paths.py` explicitly detects PyInstaller's `sys._MEIPASS` and resolves bundled resources from the frozen runtime.

The PyInstaller spec includes the full `resources/` directory.

This is suitable for the current offline Help/User Guide resource model.

### 2.2 User data is separated from installation files

`core/app_paths.py` writes runtime data to per-user platform locations.

On Windows the current root is based on `%APPDATA%/Script Manager`.

Project backups, database migration backups, logs, and project runtime state are not designed to live under `{app}`.

This is a strong base for uninstall/reinstall safety.

### 2.3 Application logging is frozen-aware

Startup logging records whether the runtime is frozen and writes rotating logs under per-user application data.

A console window is not required for normal diagnostics.

### 2.4 `.smproj` command-line open flow exists

`main.py` accepts a non-option command-line argument and opens it as a project when the path exists.

This matches the installer file-association command:

```text
"ScriptManager.exe" "%1"
```

### 2.5 Application identity already has basic packaging metadata

The PyInstaller spec already embeds:

- product name;
- file version;
- product version;
- executable name;
- app icon when generated.

The Inno Setup installer already includes app identity, optional desktop shortcut, Start Menu entry, modern wizard style, per-user installation, and uninstall support.

### 2.6 Windows packaging CI already exists

`windows-package.yml` currently builds on `windows-latest` and performs:

1. PyInstaller build;
2. frozen executable smoke test;
3. portable ZIP creation;
4. Inno Setup installation through Chocolatey;
5. installer compilation;
6. silent install into a temporary directory;
7. installed executable smoke test;
8. `.smproj` Registry verification;
9. project icon verification;
10. open-command verification;
11. silent uninstall;
12. artifact upload.

### 2.7 Release pipeline already exists

`release.yml` currently:

1. triggers on semantic version tag;
2. verifies tag matches `APP_VERSION`;
3. builds frozen portable app;
4. builds installer;
5. smoke-tests installer;
6. generates SHA-256 files;
7. publishes a GitHub Release;
8. verifies the published release through the updater.

This is already aligned with the desired real update-check validation flow.

---

## 3. Packaging Gaps / Required Phase 12 Work

### P12-A — Google Drive prerequisite is absent

Current installer has no Google Drive for desktop prerequisite detection, download, installation, or readiness explanation.

**Required before first user-facing installer acceptance.**

Planned handling remains:

- detect existing installation;
- do not bundle Google installer binary;
- offer official download/install when missing;
- make third-party installation explicit;
- keep user login manual;
- support manual/corporate fallback.

### P12-B — Google Drive install state and Drive readiness are different

The installer must not claim that Drive is usable merely because the application is installed.

States must distinguish at minimum:

```text
NOT_INSTALLED
INSTALLED_NOT_READY
READY
```

A user may still need to sign in after installation.

### P12-C — Packaging CI must not accidentally install Google Drive

Current Windows Package and Release smoke tests install Script Manager silently.

If Google Drive prerequisite logic is added directly to Inno Setup without a CI-aware contract, GitHub-hosted runners could attempt to download/install Google Drive during packaging smoke tests.

Required design:

- production/default installer path performs prerequisite handling;
- automated installer smoke test has a dedicated explicit bypass or test mode for external prerequisite installation only;
- the bypass must not disable normal Script Manager installation/file-association tests;
- the bypass must not become the default behavior for users.

This is a **P0 packaging-design requirement** for 12.03–12.05.

### P12-D — Windows Package workflow is intentionally manual-only

`windows-package.yml` still contains Phase 10 comments and only uses `workflow_dispatch`.

That was correct while UI was changing frequently, but Phase 12 now needs a stronger packaging gate.

Planned direction:

- keep manual trigger available;
- add an appropriate automatic Phase 12/PR packaging gate when implementation stabilizes, likely scoped to packaging/runtime/release-related paths;
- do not make every documentation-only commit rebuild Windows artifacts unnecessarily.

### P12-E — Publisher/company metadata is still placeholder identity

Current metadata uses `Script Manager` as both product and publisher/company.

Before v0.1.0 publication, decide the final publisher string to show in:

- EXE version information;
- installer Publisher field;
- future About page;
- future code-signing identity if applicable.

This is not a runtime blocker, but it is a professional-release identity decision.

### P12-F — README remains development-oriented

README currently presents Python/venv setup as the primary run path.

Before public/user distribution, README/release documentation should distinguish:

- normal user installation;
- portable build;
- developer/source setup.

### P12-G — Repository license must be intentional

The repository currently contains Apache License 2.0.

Packaging itself can proceed, but before broad distribution the project owner should confirm that Apache-2.0 distribution is intentional for this repository/product.

Do not silently change licensing during packaging work.

### P12-H — Current frozen smoke test is intentionally shallow

`--smoke-test` proves the production ApplicationWindow/MainWindow and pages can be constructed in the frozen build.

It does not replace manual packaged UAT for:

- actual Excel source sync;
- Google Drive filesystem usage;
- real backup/recovery;
- real double-click project workflow;
- update server access;
- installer visual UX.

Manual Windows UAT remains required.

### P12-I — Code signing is not part of baseline

No Windows signing certificate is currently integrated.

The unsigned v0.1.0 baseline may produce Windows SmartScreen reputation warnings.

Per Phase 12 scope, code signing remains future release hardening and is not a blocker for proving the first packaging/update lifecycle.

---

## 4. Resource/Runtime Audit

### Covered by existing frozen design

- `resources/` bundled by PyInstaller;
- Help HTML resolved through `resource_path()`;
- icon payload materialization;
- per-user application logs;
- per-project backups/logs;
- SQLite database embedded in Python runtime;
- openpyxl declared runtime dependency;
- PySide6 declared runtime dependency;
- command-line `.smproj` open path;
- app version source centralized in `core/version.py`.

### No packaging change required yet

No evidence from the audited foundation requires changing the `.smproj` format or database schema for packaging.

No user data needs to be embedded into the frozen application.

---

## 5. Current Release Architecture

```text
Source Commit
    ↓
PyInstaller spec
    ↓
dist/ScriptManager/
    ├── ScriptManager.exe
    └── bundled runtime/resources
    ↓
Portable ZIP

and

Inno Setup
    ↓
ScriptManager-<version>-Setup.exe
    ↓
Per-user install
    ↓
.smproj association
```

Phase 12 extends the installer path to:

```text
Script Manager Setup
    ↓
Prerequisite state
    ├── Drive ready → continue
    ├── Drive installed/not ready → explain login/readiness
    └── Drive missing
         ├── official install flow
         └── manual/corporate fallback
    ↓
Install Script Manager
```

---

## 6. Decisions for Next Step

12.03 must design the prerequisite contract before changing Inno Setup.

Required outputs of 12.03:

1. Windows support/architecture policy.
2. Google Drive installed detection policy.
3. Google Drive readiness policy.
4. Offline/download-failure behavior.
5. Cancel behavior.
6. corporate/manual fallback behavior.
7. CI smoke-test bypass contract for external prerequisite installation.
8. clear separation between installer prerequisite and first-run readiness.

---

## 7. Audit Verdict

**12.02 COMPLETE — READY FOR 12.03.**

The existing packaging foundation is suitable to evolve into the first Windows release. No rewrite of PyInstaller/Inno/GitHub Release architecture is justified at this point.
