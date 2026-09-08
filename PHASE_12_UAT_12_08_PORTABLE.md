# Phase 12 — UAT 12.08 Portable Build v0.1.0

> Status: **IN PROGRESS**
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

---

## Remaining workflow spot-check sebelum 12.08 COMPLETE

- [ ] New Project.
- [ ] Open existing `.smproj`.
- [ ] Source Sync.
- [ ] NASKAH.
- [ ] DIALOG.
- [ ] TRACKING.
- [ ] DELIVERY.
- [ ] DATA.
- [ ] Project Settings.
- [ ] Help / User Guide.
- [ ] Backup / Recovery.
- [ ] Close / reopen.
- [ ] Existing/legacy project tetap dapat dibuka.

Tidak perlu mengulang seluruh regression secara manual. Spot-check workflow nyata cukup untuk memastikan frozen portable build tidak kehilangan resource/dependency yang hanya tersedia pada source environment.

---

## Exit criteria

12.08 dapat ditandai **COMPLETE** setelah workflow inti di atas tidak menunjukkan packaged-only blocker.
