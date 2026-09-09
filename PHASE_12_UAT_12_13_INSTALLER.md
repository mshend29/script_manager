# Phase 12 — UAT 12.13 Windows Installer v0.1.0

> Status: **PARTIAL PASS — PROGRAM FILES REVALIDATION PENDING**
>
> Branch: `phase-12-first-windows-release`
>
> PR: #77
>
> Latest Program Files source commit: `1c4e8f37db8e1c9f68afb94697ec7c7411631164`
>
> Latest Windows Package run: #112 (`34211494661`)
>
> Installer artifact: `ScriptManager-windows-installer`
>
> Installer inside artifact: `ScriptManager-0.1.0-Setup.exe`

---

## User UAT result already accepted

UAT pada build installer sebelumnya sudah mengonfirmasi:

- [x] Install berjalan tanpa kendala.
- [x] Uninstall berjalan tanpa kendala.
- [x] Project lama dapat dibuka tanpa kendala.
- [x] SmartScreen warning diketahui berasal dari unsigned baseline build.

### SmartScreen / code signing decision

**DEFERRED — bukan blocker Phase 12 v0.1.0 baseline.**

User memilih untuk menunda code signing / SmartScreen reputation work. Jangan menahan release-candidate baseline hanya karena installer belum signed. Pekerjaan ini dipindahkan ke release-hardening setelah baseline/update lifecycle selesai.

---

## Program Files policy update

Berdasarkan feedback UAT, installer diubah dari per-user LocalAppData menjadi administrative Program Files install:

```text
C:\Program Files\Script Manager
```

Implementation policy:

- [x] `DefaultDirName={autopf}\Script Manager`.
- [x] `PrivilegesRequired=admin`.
- [x] Start Menu/Desktop shortcut memakai auto scope.
- [x] `.smproj` association menjadi machine-wide registration.
- [x] Windows Package #112 compile sukses.
- [x] Installer identity sukses.
- [x] Install-over-existing sukses.
- [x] Installed runtime smoke sukses.
- [x] `.smproj` open/association smoke sukses.
- [x] Uninstall sukses.
- [x] External `.smproj`, source/audio/delivery/backup sentinel tetap aman setelah uninstall.

### Manual revalidation — USER

- [ ] Jalankan installer terbaru.
- [ ] Confirm default destination menunjukkan `C:\Program Files\Script Manager`.
- [ ] Accept UAC/admin prompt.
- [ ] Launch aplikasi setelah install.
- [ ] Open project lama.
- [ ] Double-click `.smproj` bila convenient.
- [ ] Uninstall dan confirm project tetap ada.

Jika seluruh poin di atas aman, tidak perlu mengulang seluruh workflow UAT sebelumnya.

---

## Automated gate confirmed

GitHub Actions Windows runner sudah membuktikan:

- [x] PyInstaller frozen build sukses.
- [x] Windows application identity/version metadata valid.
- [x] Portable frozen runtime smoke sukses.
- [x] Packaged runtime diagnostics smoke sukses.
- [x] `.smproj` path dengan spasi + Unicode dapat dibuka oleh frozen EXE.
- [x] Portable ZIP berhasil dibuat dan di-upload.
- [x] Inno Setup compile sukses.
- [x] Installer version/product/company metadata valid.
- [x] Administrative install sukses.
- [x] Installed EXE runtime smoke sukses.
- [x] Installed EXE diagnostics smoke sukses.
- [x] Installed EXE dapat membuka `.smproj` path dengan spasi + Unicode.
- [x] `.smproj` ProgID terdaftar sebagai `ScriptManager.Project`.
- [x] File type name terdaftar sebagai `Script Manager Project`.
- [x] Project file icon terdaftar dan tersedia setelah install.
- [x] Open command meneruskan `"%1"` ke `ScriptManager.exe`.
- [x] Install-over-existing ke lokasi yang sama sukses.
- [x] Runtime tetap dapat dijalankan setelah install-over-existing.
- [x] Uninstall sukses.
- [x] Installed executable terhapus setelah uninstall.
- [x] External `.smproj` tetap ada setelah uninstall.
- [x] Source/audio/delivery/backup sentinel di luar install directory tetap ada setelah uninstall.
- [x] `ScriptManager.Project` registration dibersihkan setelah uninstall.

Engine gate pada commit yang sama juga hijau untuk regular regression, Qt runtime smoke, dan Phase 11 scale smoke.

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

## Exit criteria

12.13 dapat ditandai **COMPLETE** setelah Program Files build terbaru diverifikasi pada PC nyata:

1. default destination benar di `C:\Program Files\Script Manager`;
2. installed Script Manager dapat launch dan membuka project existing;
3. uninstall tetap tidak menghapus project/user data.

SmartScreen/code signing tidak termasuk exit criteria baseline v0.1.0 berdasarkan keputusan user.
