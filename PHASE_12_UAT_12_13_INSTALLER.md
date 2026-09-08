# Phase 12 — UAT 12.13 Windows Installer v0.1.0

> Status: **READY FOR USER UAT**
>
> Branch: `phase-12-first-windows-release`
>
> PR: #77
>
> Source commit: `a43fb0ddc5bad776698887e03de9fd3ac1950cb3`
>
> Windows Package run: #104 (`34192938996`)
>
> Installer artifact: `ScriptManager-windows-installer`
>
> Installer inside artifact: `ScriptManager-0.1.0-Setup.exe`

---

## Automated gate confirmed before user UAT

GitHub Actions Windows runner sudah membuktikan seluruh jalur berikut dari source commit yang sama:

- [x] PyInstaller frozen build sukses.
- [x] Windows application identity/version metadata valid.
- [x] Portable frozen runtime smoke sukses.
- [x] Packaged runtime diagnostics smoke sukses.
- [x] `.smproj` path dengan spasi + Unicode dapat dibuka oleh frozen EXE.
- [x] Portable ZIP berhasil dibuat dan di-upload.
- [x] Inno Setup 6.7.1 compile sukses.
- [x] Installer version/product/company metadata valid.
- [x] Silent per-user install sukses.
- [x] Installed EXE runtime smoke sukses.
- [x] Installed EXE diagnostics smoke sukses.
- [x] Installed EXE dapat membuka `.smproj` path dengan spasi + Unicode.
- [x] `.smproj` ProgID terdaftar sebagai `ScriptManager.Project`.
- [x] File type name terdaftar sebagai `Script Manager Project`.
- [x] Project file icon terdaftar dan tersedia setelah install.
- [x] Open command meneruskan `"%1"` ke `ScriptManager.exe`.
- [x] Silent uninstall sukses.

Engine gate pada commit yang sama juga hijau untuk regular regression, Qt runtime smoke, dan Phase 11 scale smoke.

---

## UAT di PC user — Google Drive sudah terpasang

Gunakan PC normal yang saat ini memang dipakai untuk Script Manager. **Jangan uninstall Google Drive hanya demi pengujian.**

### A. Install

- [ ] Tutup portable Script Manager bila masih terbuka.
- [ ] Jalankan `ScriptManager-0.1.0-Setup.exe` sebagai user normal.
- [ ] SmartScreen warning, bila muncul karena build belum code-signed, dicatat tetapi bukan blocker fungsional baseline.
- [ ] Installer mengenali Google Drive existing / tidak memaksa download ulang.
- [ ] Lokasi install terlihat wajar untuk per-user install.
- [ ] Start Menu shortcut dibuat.
- [ ] Desktop shortcut hanya dibuat bila opsi dipilih.
- [ ] Instalasi selesai tanpa membutuhkan Python, VS Code, atau Inno Setup.

### B. Launch & identity

- [ ] Launch dari Start Menu berhasil.
- [ ] Bila Desktop shortcut dipilih, shortcut tersebut berhasil launch.
- [ ] Icon aplikasi benar di shortcut/window/taskbar.
- [ ] Tidak muncul console Python.
- [ ] UI utama tampil normal.

### C. `.smproj` association

Gunakan project test/backup-safe, bukan satu-satunya copy project produksi.

- [ ] Double-click `.smproj` dari File Explorer membuka Script Manager.
- [ ] Project yang benar langsung terbuka.
- [ ] File icon `.smproj` terlihat sebagai Script Manager Project.
- [ ] Path `.smproj` yang mengandung spasi aman.
- [ ] Jika tersedia project di path Unicode, double-click juga aman.
- [ ] File → Open dari dalam aplikasi tetap bekerja normal.

### D. Workflow smoke

Tidak perlu mengulang seluruh regression manual. Spot-check workflow nyata cukup:

- [ ] Open existing project.
- [ ] New Project test bila aman dilakukan.
- [ ] Source Sync.
- [ ] NASKAH.
- [ ] DIALOG.
- [ ] TRACKING.
- [ ] DELIVERY.
- [ ] DATA.
- [ ] Project Settings.
- [ ] Help / User Guide.
- [ ] Close dan reopen aplikasi.

### E. Uninstall & data safety

Sebelum uninstall, catat lokasi satu project test yang sudah berhasil dibuka.

- [ ] Uninstall Script Manager dari Windows Apps / Installed apps.
- [ ] Aplikasi terhapus dari install directory.
- [ ] Shortcut aplikasi terhapus.
- [ ] Project `.smproj` user **tidak terhapus**.
- [ ] Source Excel **tidak terhapus**.
- [ ] Audio/stem/delivery external data **tidak terhapus**.
- [ ] Backup project **tidak terhapus**.

### F. Reinstall

- [ ] Install kembali installer v0.1.0 yang sama.
- [ ] Existing `.smproj` tetap dapat dibuka.
- [ ] Double-click association kembali bekerja.
- [ ] Project state/data tetap utuh.

---

## Google Drive missing-path UAT

Jangan menghapus Google Drive dari PC produksi hanya untuk pengujian ini.

Lakukan nanti di Windows Sandbox, VM, atau PC uji terpisah:

- [ ] Installer menunjukkan halaman prerequisite Google Drive.
- [ ] `Install Google Drive & Lanjut` menggunakan installer resmi Google.
- [ ] User dapat memilih `Saya akan mengaturnya sendiri`.
- [ ] Cancel/failure download tetap user-friendly.
- [ ] Offline state tetap memberikan manual fallback.
- [ ] Script Manager tetap tidak meminta/menyimpan credential Google.

Bagian ini boleh dipisahkan dari acceptance PC produksi selama jalur `Google Drive already installed` sudah lolos dan tidak ada blocker installer lainnya.

---

## Acceptance report

Untuk mempercepat triage, user cukup mengembalikan status berikut:

```text
12.13 Installer UAT
A Install: PASS / FAIL
B Launch & identity: PASS / FAIL
C .smproj double-click: PASS / FAIL
D Workflow smoke: PASS / FAIL
E Uninstall & data safety: PASS / FAIL
F Reinstall: PASS / FAIL

Catatan/error:
...
```

Screenshot hanya diperlukan bila ada tampilan, warning, icon, association, atau error yang tidak sesuai.

---

## Exit criteria

12.13 dapat ditandai **COMPLETE** setelah:

1. installer dapat dipakai sebagai user normal tanpa development environment;
2. installed Script Manager dapat menjalankan workflow inti;
3. `.smproj` double-click berfungsi pada PC nyata;
4. uninstall tidak menghapus project/user production data;
5. reinstall tetap dapat membuka project existing.

Google Drive missing-path flow dapat divalidasi terpisah di lingkungan aman tanpa mengganggu Google Drive produksi user.
