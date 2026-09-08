# Phase 12 — Checkpoint 12.08–12.09

> Status: **COMPLETE**
>
> Branch: `phase-12-first-windows-release`
>
> Current application version: `0.1.0`

## 12.08 — Portable Build v0.1.0

**PASS.**

- Portable artifact berhasil dijalankan pada Windows PC user nyata.
- User mengonfirmasi portable build berfungsi.
- Layout PyInstaller `onedir` dengan `_internal` diterima sebagai expected.
- Tidak diperlukan Python / VS Code untuk menjalankan aplikasi.
- SmartScreen / Windows Protection warning diamati sebagai expected unsigned-build behavior dan bukan runtime blocker.

Detail acceptance ada di `PHASE_12_UAT_12_08_PORTABLE.md`.

## 12.09 — Packaged Runtime Diagnostics

**PASS.**

Implemented:

- rotating application log tetap berada di per-user application data;
- fatal startup exception ditulis ke application log;
- fallback diagnostic log dibuat di temporary directory bila normal log tidak dapat digunakan;
- windowed packaged build menampilkan pesan fatal startup yang menunjuk ke diagnostic log;
- Problem Report membedakan `Source (Python)` dan `Packaged (PyInstaller)`;
- PySide6 version detection mempunyai fallback yang aman untuk frozen runtime;
- Problem Report hanya menampilkan generic diagnostic-log hint dan tidak membocorkan username/project path;
- Windows Package menjalankan `--diagnostics-smoke-test` pada portable frozen EXE dan installed EXE.

Final automated gate pada head yang membawa 12.09:

- regular regression: **462 passed, 66 skipped**;
- Qt runtime + scale smoke: **success**;
- Google Drive Windows readiness probe: **success**;
- frozen normal smoke: **success**;
- frozen diagnostics smoke: **success**;
- installer compile: **success**;
- installed normal smoke: **success**;
- installed diagnostics smoke: **success**;
- `.smproj` association smoke: **success**;
- uninstall smoke: **success**.

## Exit

12.08 dan 12.09 dapat dianggap **COMPLETE**. Phase berikutnya: **12.10 — Windows Application Identity**.
