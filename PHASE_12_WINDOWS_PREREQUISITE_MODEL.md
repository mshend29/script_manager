# Phase 12 — Windows Prerequisite Model

> Milestone: **12.03**
>
> Status: **COMPLETE — CONTRACT LOCKED**
>
> Branch: `phase-12-first-windows-release`
>
> Scope: prerequisite behavior for the first packaged Windows release of Script Manager.

---

## 1. Purpose

Script Manager uses Google Drive for desktop as the supported desktop-filesystem bridge for project folders that live in Google Drive. The Script Manager installer should make this dependency easy for normal users without bundling Google binaries, hiding third-party installation, or making CI/release builds depend on an interactive Google login.

This document defines the prerequisite contract before `packaging/ScriptManager.iss` is changed.

---

## 2. Official Google facts used by this contract

Verified on **2026-09-08** against current Google documentation.

Google documents that:

- Drive for desktop on Windows is installed using `GoogleDriveSetup.exe`;
- the official current Windows installer is available from:
  `https://dl.google.com/drive-file-stream/GoogleDriveSetup.exe`;
- administrators may deploy it silently with `GoogleDriveSetup --silent`;
- optional installer switches include `--skip_launch_new` and `--gsuite_shortcuts=false`;
- work/school users may be unable to install Drive themselves because their organization can manage deployment;
- after Drive for desktop is installed and signed in, Google Drive becomes available as a desktop filesystem location;
- the default streaming drive letter can be `G:` but can be configured differently, therefore Script Manager must **never** use `G:` as its readiness contract;
- Google documents the Windows uninstall registry key GUID:
  `{6BBAE539-2232-434A-A4E5-9A33560C6283}`;
- supported Drive for desktop Windows systems are 64-bit Windows 10+; ARM64 requires Windows 11+;
- Microsoft WebView2 is a Google Drive dependency, and Google's installer handles downloading/installing it when needed.

References:

- https://knowledge.workspace.google.com/admin/drive/set-up-drive-for-desktop-for-your-organization
- https://support.google.com/drive/answer/10838124
- https://support.google.com/drive/answer/2375082

Script Manager will not independently install or manage WebView2.

---

## 3. Locked decisions

### D1214 — Prerequisite is Google Drive for desktop, not Google credentials

The installer may detect/install Google Drive for desktop.

It must never request, store, proxy, or automate Google account credentials.

Sign-in remains inside Google's own application/browser flow.

### D1215 — Installed and Ready are different concepts

A machine may have Google Drive for desktop installed but not yet signed in or mounted.

Therefore prerequisite state distinguishes installation from operational readiness.

### D1216 — Drive letter is never part of the contract

Do not assume `G:` or any fixed path.

Drive for desktop can use a different streaming location and can expose different account locations.

### D1217 — Installer installation detection uses stable system evidence

Primary installed check on Windows:

```text
HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\
{6BBAE539-2232-434A-A4E5-9A33560C6283}
```

Detection must account for normal registry-view differences on 64-bit Windows where relevant.

A secondary executable/path probe may be used only as fallback; it must not become the sole contract.

### D1218 — Setup does not hard-block because login is incomplete

Once Google Drive for desktop is installed, Script Manager itself may be installed.

If Drive has not been signed in/mounted yet, setup presents guidance and the application continues to validate the actual project folders when the user configures or opens a project.

### D1219 — Missing Google Drive has a recommended automatic path and an explicit manual fallback

Interactive setup when Drive is missing must offer:

```text
Recommended:
Install Google Drive & Lanjut

Alternative:
Saya akan mengaturnya sendiri
```

The automatic path downloads the current installer directly from Google's official URL.

The manual path is important for:

- managed/corporate PCs;
- offline installation;
- users without sufficient admin permission;
- environments where Google Drive is installed by IT later.

### D1220 — Third-party installation is never hidden

Interactive Script Manager setup must tell the user before downloading/running Google software.

The page must identify **Google Drive for desktop** and **Google LLC** and state that its installer is downloaded from Google.

### D1221 — Silent Script Manager setup never silently installs Google Drive

A `/VERYSILENT` or CI install of Script Manager must not unexpectedly download/install third-party software.

For silent/managed deployments:

- Script Manager installation may proceed;
- Google Drive deployment remains the responsibility of the administrator or a separate prerequisite step;
- CI uses an explicit internal prerequisite-bypass switch.

This protects both CI and enterprise deployment behavior.

### D1222 — CI bypass is explicit and narrow

The installer will expose an internal switch such as:

```text
/SKIPDRIVEPREREQ
```

Purpose:

- GitHub Actions installer smoke test;
- automated packaging verification;
- controlled enterprise deployment where Drive is provisioned separately.

The switch bypasses only the Google Drive prerequisite workflow. It must not bypass Script Manager file-association, install, launch-smoke, or uninstall checks.

### D1223 — Download is temporary and removed after use

`GoogleDriveSetup.exe` is downloaded into an installer temporary directory.

It is not:

- committed to git;
- embedded in Script Manager setup;
- copied into the installed Script Manager application directory;
- kept as a Script Manager user-data artifact after setup.

### D1224 — Google Drive installer is launched with minimal Script Manager opinion

Preferred automated invocation:

```text
GoogleDriveSetup.exe --silent --gsuite_shortcuts=false
```

Reasoning:

- installation is automated after explicit user consent;
- Docs/Sheets/Slides desktop shortcuts are unrelated to Script Manager and should not be added by default;
- Google Drive may launch afterward so the user can sign in.

Do **not** use `--skip_launch_new` in the normal interactive Script Manager flow because launching Drive after successful installation makes the next sign-in step easier.

If this behavior proves disruptive during Windows UAT, the launch policy may be adjusted without changing the prerequisite state model.

### D1225 — Script Manager validates actual paths, not Google account internals

Operational readiness is ultimately established when configured Script Manager filesystem paths are accessible.

The application must not depend on undocumented Google account configuration files, private registry data, cached tokens, or Google process internals to decide whether a project folder is usable.

This preserves cross-platform portability and avoids brittle coupling to Google implementation details.

---

## 4. Prerequisite states

The logical states are:

### `UNSUPPORTED_SYSTEM`

The current Windows environment does not meet the release/prerequisite support contract.

For the first Windows release, baseline distribution remains Windows x64. Google Drive itself requires 64-bit Windows 10+ (ARM64 requires Windows 11+).

**Installer behavior:** blocker with a clear explanation.

### `NOT_INSTALLED`

No reliable Google Drive installation evidence was found.

**Interactive behavior:** show prerequisite page with automatic install recommended and manual fallback.

**Silent/CI behavior:** do not download third-party software; use explicit managed/CI bypass behavior.

### `INSTALLED_NOT_READY`

Google Drive installation is present, but a usable Drive filesystem session cannot be established/confirmed yet.

Typical examples:

- newly installed and not signed in;
- Drive application closed;
- sign-in required;
- organization policy prevents sign-in;
- mount not yet created.

**Installer behavior:** Script Manager installation may continue. Completion guidance explains that Drive must be signed in before selecting Drive-backed folders.

### `READY`

Google Drive is installed and a usable filesystem location is available.

**Installer behavior:** prerequisite satisfied; no extra action required.

Important: installer readiness detection is best-effort only. Project-level filesystem validation remains authoritative.

### `CHECK_ERROR`

The prerequisite check itself cannot complete reliably.

Examples:

- registry access anomaly;
- temporary system query failure;
- unexpected installation state.

**Interactive behavior:** show a warning and allow manual setup/continue rather than trapping the user.

### `BYPASSED_MANAGED`

Explicit user/admin/CI decision to provision Drive separately.

This is not treated as `READY`; it records that Script Manager setup intentionally did not manage the external prerequisite.

---

## 5. Interactive setup flow

### Case A — Drive already ready

```text
Script Manager Setup
↓
Pemeriksaan Sistem
✓ Google Drive for desktop siap
↓
Install Script Manager
```

### Case B — Drive installed but not ready

```text
Script Manager Setup
↓
Pemeriksaan Sistem
! Google Drive terpasang, login/Drive belum siap
↓
Install Script Manager
↓
Completion guidance:
  Buka Google Drive
  Login jika diperlukan
  Jalankan Script Manager
```

### Case C — Drive missing, automatic path

```text
Script Manager Setup
↓
Google Drive for desktop diperlukan
↓
User chooses: Install Google Drive & Lanjut
↓
Download official GoogleDriveSetup.exe to {tmp}
↓
Run Google installer
↓
Re-check installation
↓
Install Script Manager
↓
Open/allow Google Drive sign-in
```

### Case D — Drive missing, manual/managed path

```text
Script Manager Setup
↓
Google Drive for desktop diperlukan
↓
User chooses: Saya akan mengaturnya sendiri
↓
Warning explains Drive-backed folders need Drive later
↓
Install Script Manager
```

### Case E — Google download fails

Do not fail with an opaque installer error.

Offer:

```text
Coba Lagi
Buka Halaman Download Google
Atur Nanti / Lanjutkan Script Manager
Batal
```

No partial Google installer should be retained as application data.

### Case F — Google installer fails/cancelled

Re-check installation evidence.

If still missing, explain that Google Drive was not installed and allow either retry, manual setup, continue Script Manager only, or cancel.

---

## 6. Silent / CI contract

Existing Windows package CI currently installs Script Manager with:

```text
/VERYSILENT
/SUPPRESSMSGBOXES
/NORESTART
```

Phase 12 will add the explicit external prerequisite bypass:

```text
/SKIPDRIVEPREREQ
```

CI command target:

```text
ScriptManager-<version>-Setup.exe
  /VERYSILENT
  /SUPPRESSMSGBOXES
  /NORESTART
  /SKIPDRIVEPREREQ
  /DIR=<temp-test-dir>
```

The CI test still must verify:

- installer exit code;
- frozen application `--smoke-test`;
- `.smproj` association;
- project file icon;
- open command;
- uninstall.

CI does **not** claim that Google Drive itself is installed or usable.

---

## 7. Application-level readiness contract

Installer prerequisite success does not replace application filesystem validation.

When Script Manager later receives a configured Source/Stem/Setoran/Drive Desktop path:

```text
configured path
↓
normal filesystem validation
↓
exists / readable / writable as required
↓
workspace can use it
```

If the path is temporarily unavailable on an existing project, Phase 11 baseline-aware warning rules remain authoritative.

No Google-specific hidden state is required in `.smproj`.

---

## 8. UX copy direction

Recommended prerequisite page language:

### Missing

**Google Drive for desktop diperlukan**

Script Manager menggunakan Google Drive for desktop agar folder proyek di Google Drive dapat diakses seperti folder biasa di Windows.

Installer resmi Google akan diunduh langsung dari Google. Anda tetap akan login ke akun Google melalui Google Drive sendiri.

Primary action:

`Install Google Drive & Lanjut`

Secondary action:

`Saya akan mengaturnya sendiri`

### Installed but not ready

**Google Drive sudah terpasang**

Google Drive ditemukan, tetapi Drive belum siap digunakan. Anda tetap dapat menyelesaikan instalasi Script Manager. Login ke Google Drive sebelum memilih folder proyek yang berada di Drive.

### Ready

**Google Drive siap digunakan**

Tidak diperlukan instalasi tambahan.

---

## 9. Security and privacy boundaries

Script Manager installer may:

- read normal Windows installation evidence;
- download the documented Google installer URL;
- execute that installer after explicit consent;
- delete the temporary downloaded installer afterward.

Script Manager installer must not:

- inspect Google credentials;
- read browser cookies;
- copy OAuth/session tokens;
- modify Google account configuration;
- disable Google update mechanisms;
- uninstall/replace an existing Google Drive installation merely because its version differs;
- use an undocumented Google download mirror.

Google Drive owns its own update lifecycle after installation.

---

## 10. Test contract for implementation milestones

### 12.04 detection tests

Must cover at minimum:

- documented uninstall key present → installed;
- key absent → not installed;
- malformed/partial registry state → check error or safe fallback;
- no fixed `G:` assumption;
- non-Windows unit tests remain safe;
- detection layer is mockable without touching real registry.

### 12.05 installer tests

Must cover at minimum:

- normal interactive missing-Drive page contract;
- official URL is the only automatic download endpoint;
- temporary installer location;
- explicit consent before execution;
- manual/managed fallback;
- retry path after download failure;
- CI `/SKIPDRIVEPREREQ` path;
- silent install never triggers Google download;
- Google installer binary absent from repository/package payload.

### Windows UAT

At least these real-PC scenarios are required before release:

1. Google Drive already installed and signed in.
2. Google Drive installed but signed out/not ready.
3. Google Drive not installed → automatic install.
4. Google Drive not installed → manual/managed fallback.
5. network unavailable during prerequisite download.

---

## 11. Exit criteria

12.03 is COMPLETE when:

- state model is explicit;
- installer vs application responsibilities are separated;
- interactive and silent behavior are defined;
- corporate/offline fallback exists;
- CI bypass is explicit and narrow;
- official Google URL/source is locked;
- login/credential boundary is locked;
- no fixed Drive letter is assumed;
- implementation tests for 12.04/12.05 are defined.

**Result: COMPLETE — implementation may proceed to 12.04 Google Drive installation detection.**
