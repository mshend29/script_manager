# Phase 12 — UAT 12.08 Portable Build v0.1.0

> Status: **COMPLETE**
>
> Branch: `phase-12-first-windows-release`
>
> Tested artifact source: Windows Package #77 / commit `21d15fa53259a75cba1c8b81df45ade016d788a7`
>
> User acceptance recorded: **portable build launches and functions on a real Windows PC**.

---

## Confirmed

- [x] Portable ZIP dapat didownload dan diekstrak.
- [x] Struktur `onedir` PyInstaller dengan folder `_internal` dikenali sebagai expected layout.
- [x] `ScriptManager.exe` dapat dijalankan langsung dari hasil extract.
- [x] Tidak perlu menjalankan aplikasi melalui VS Code / `python main.py`.
- [x] Basic portable runtime berfungsi pada PC user nyata.
- [x] User mengonfirmasi portable build berfungsi dan tidak melaporkan packaged-only blocker.
- [x] Windows Defender SmartScreen / Windows Protection warning diamati pada unsigned build dan dicatat sebagai expected distribution-polish issue, bukan runtime failure.

---

## Workflow coverage note

Checklist workflow berikut tetap menjadi referensi minimum portable UAT:

- New Project;
- Open existing `.smproj`;
- Source Sync;
- NASKAH;
- DIALOG;
- TRACKING;
- DELIVERY;
- DATA;
- Project Settings;
- Help / User Guide;
- Backup / Recovery;
- Close / reopen;
- Existing/legacy project.

User tidak melaporkan hasil setiap item sebagai assertion terpisah. Milestone 12.08 ditutup berdasarkan acceptance bahwa portable build **berfungsi pada penggunaan nyata** dan tidak ditemukan blocker khusus frozen/portable. Automated regression, Qt runtime, frozen EXE smoke, dan Windows Package gate tetap menjadi coverage teknis pelengkap.

---

## SmartScreen note

Build v0.1.0 baseline belum code-signed. Karena itu Windows dapat menampilkan peringatan seperti `Windows protected your PC` / unknown publisher.

Keputusan Phase 12:

- warning ini tidak memblokir baseline packaging/update validation;
- code signing tetap direkomendasikan sebelum distribusi luas / release yang diposisikan sebagai public production-grade;
- jangan menyamakan SmartScreen reputation dengan kegagalan aplikasi.

---

## Exit criteria result

**PASS.** Portable frozen app dapat dijalankan dan digunakan pada Windows PC nyata tanpa Python/VS Code. Tidak ada packaged-only blocker yang dilaporkan pada acceptance 12.08.
