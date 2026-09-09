# Phase 12 — First Windows Release & Real Update Validation

> Status: **PLANNED**
>
> Branch: `phase-12-first-windows-release`
>
> Baseline: `main` after Help/User Guide redesign (PR #76)
>
> Release target: **v0.1.0** as the first packaged Windows baseline.

---

## 1. Purpose

Phase 12 mengubah Script Manager dari aplikasi development yang dijalankan melalui Python menjadi aplikasi Windows yang dapat dipasang, dijalankan, dibuka dari file `.smproj`, dan diperbarui melalui siklus release nyata.

Phase ini **tidak** menambah fitur workflow besar baru. Fokusnya adalah release engineering, packaging, installer, prerequisite, distribution safety, dan pembuktian fitur update checker secara end-to-end.

Splash Screen dan redesign halaman **Tentang Script Manager** sengaja **ditunda sampai baseline v0.1.0 sudah dibuild dan dipasang**. Keduanya akan menjadi perubahan versi berikutnya sehingga update checker dapat diuji dari versi lama ke versi baru dalam kondisi nyata.

---

## 2. Product Target

Target akhir Phase 12 tahap pertama:

```text
ScriptManagerSetup-0.1.0.exe
        ↓
Setup Wizard
        ↓
System prerequisite check
        ↓
Google Drive for desktop readiness
        ↓
Install Script Manager
        ↓
Register .smproj
        ↓
Launch Script Manager
```

Selain installer, release pertama juga menyiapkan portable build untuk diagnosis dan UAT.

Expected release artifacts:

```text
ScriptManager-0.1.0-Windows-x64.zip
ScriptManagerSetup-0.1.0.exe
SHA256SUMS.txt
Release Notes
```

---

## 3. Locked Decisions

### D1201 — Baseline release tetap v0.1.0

Current application version `0.1.0` dipakai sebagai packaged baseline pertama.

Jangan menaikkan versi hanya karena packaging dibuat.

### D1202 — Splash dan About redesign dilakukan setelah baseline terpasang

Tujuan:

```text
Installed v0.1.0
    ↓
Develop Splash + About
    ↓
Version bump v0.2.0
    ↓
Publish v0.2.0
    ↓
v0.1.0 detects real update
```

Dengan demikian update checker diuji terhadap GitHub Release nyata, bukan hanya test/mocking.

### D1203 — Google Drive for desktop adalah prerequisite resmi

Script Manager menggunakan Google Drive Desktop sebagai filesystem untuk workflow folder proyek.

Installer harus memeriksa keberadaan Google Drive for desktop.

### D1204 — Google Drive installer tidak dibundle permanen

Jangan menyimpan atau mendistribusikan binary `GoogleDriveSetup.exe` di dalam repository maupun payload installer Script Manager.

Jika Google Drive belum terpasang:

1. Setup menjelaskan bahwa Google Drive for desktop diperlukan.
2. User memilih `Install Google Drive & Lanjut` atau opsi setara.
3. Installer resmi Google diunduh dari sumber resmi Google pada saat setup.
4. Installer resmi Google dijalankan.
5. Setup memverifikasi hasil instalasi sebelum melanjutkan bila memungkinkan.

Keuntungan:

- binary berasal langsung dari publisher resmi;
- user memperoleh installer terbaru;
- payload Script Manager tetap lebih kecil;
- tidak perlu menjaga salinan installer pihak ketiga di repository.

### D1205 — Instalasi pihak ketiga tidak boleh tersembunyi

Wizard harus menjelaskan dengan jelas bahwa software Google akan diunduh/dijalankan.

Tidak boleh silent install pihak ketiga tanpa informasi yang jelas kepada user.

### D1206 — Login Google tetap dilakukan user

Script Manager maupun installer tidak menangani password, OAuth token, atau credential akun Google.

Setelah Google Drive terpasang, user tetap melakukan login sendiri jika belum login.

### D1207 — Google Drive existing installation tidak diinstall ulang

Jika prerequisite sudah tersedia, wizard menampilkan status siap dan melewati instalasi Google Drive.

### D1208 — Inno Setup adalah build tool, bukan user prerequisite

Inno Setup dipakai oleh developer/CI untuk membuat `ScriptManagerSetup-<version>.exe`.

User Script Manager **tidak pernah diminta menginstall Inno Setup**.

### D1209 — Packaging tidak boleh memasukkan state user ke install directory

Project `.smproj`, backup project, source Excel, audio, stem, delivery, dan data operasional user tidak boleh diletakkan di lokasi program yang akan hilang saat uninstall/update.

### D1210 — Installer harus mendukung upgrade in-place

Versi berikutnya harus dapat dipasang di atas versi lama tanpa menghapus project/user data.

### D1211 — `.smproj` harus menjadi file association resmi Script Manager

Double-click `.smproj` harus membuka project melalui Script Manager setelah installer selesai.

### D1212 — Build Windows tetap cross-platform-aware

Business logic tidak boleh dibuat Windows-only hanya demi packaging.

OS-specific behavior harus dibatasi ke packaging/integration layer agar macOS dapat menjadi target setelah Windows release stabil.

### D1213 — Update v1 adalah notification + release-page flow

Phase ini tidak membuat silent/self updater.

Expected flow:

```text
Bantuan
→ Periksa Pembaruan
→ versi baru ditemukan
→ Buka Halaman Rilis
→ user download installer
→ install upgrade
```

Ini dianggap cukup dan lebih aman untuk release awal.

---

## 4. Scope

### In scope

- baseline release audit;
- Windows packaging readiness;
- PyInstaller/frozen app configuration;
- portable build;
- Windows installer;
- Google Drive prerequisite detection;
- official Google Drive downloader/launch flow;
- `.smproj` file association;
- app/version metadata;
- install/uninstall/upgrade safety;
- release artifacts;
- GitHub Release v0.1.0;
- real update-check baseline;
- later v0.2.0 update validation after Splash/About work.

### Out of scope untuk packaged baseline v0.1.0

- Splash Screen redesign;
- About redesign;
- macOS build;
- Apple signing/notarization;
- Windows paid code-signing certificate acquisition;
- silent auto-update;
- cloud sync implementation di dalam Script Manager;
- multi-user concurrent `.smproj` database.

---

## 5. Ordered Work Plan

Kerjakan **berurutan**. Jangan menandai item COMPLETE hanya berdasarkan source code; packaging step harus mempunyai automated gate dan/atau Windows UAT sesuai kebutuhan.

---

## 12.01 — Freeze v0.1.0 Baseline

**Owner:** Assistant / repository

### Tasks

- [ ] Verifikasi branch dibuat dari `main` terbaru.
- [ ] Verifikasi `APP_VERSION == "0.1.0"`.
- [ ] Catat baseline commit.
- [ ] Verifikasi Python compile gate.
- [ ] Verifikasi full regression suite.
- [ ] Verifikasi Qt runtime gate.
- [ ] Catat database schema dan project format yang akan menjadi baseline release.
- [ ] Pastikan tidak ada Splash/About redesign yang masuk sebelum packaged baseline selesai.

### Exit criteria

Satu commit baseline jelas dan semua existing release gates hijau.

---

## 12.02 — Packaging Readiness Audit

**Owner:** Assistant / repository

### Audit targets

- [ ] Python entry point.
- [ ] PySide6/Qt runtime plugins.
- [ ] Qt Multimedia/FFmpeg requirements.
- [ ] `openpyxl` dan dependency runtime.
- [ ] HTML Help resources.
- [ ] icons/images/resources.
- [ ] application paths.
- [ ] temp/cache/runtime directories.
- [ ] backup/recovery paths.
- [ ] browser/file/folder opening behavior.
- [ ] hard-coded repository/development paths.
- [ ] assumptions about current working directory.
- [ ] hidden imports/dynamic imports.
- [ ] subprocess calls.
- [ ] Windows-only calls yang perlu dibungkus cross-platform.

### Deliverable

Dokumen/checklist packaging audit + daftar perubahan yang diperlukan sebelum freeze.

### Exit criteria

Tidak ada known runtime resource yang hanya bekerja saat `python main.py` dari source tree.

---

## 12.03 — Windows Prerequisite Model

**Owner:** Assistant / repository

### Tasks

- [ ] Definisikan supported Windows architecture untuk baseline (target awal Windows x64).
- [ ] Definisikan minimum OS support yang akan diklaim.
- [ ] Definisikan free-space check bila diperlukan.
- [ ] Definisikan Google Drive installed detection.
- [ ] Definisikan Google Drive running/readiness detection secara terpisah dari installed detection.
- [ ] Definisikan behavior untuk managed/corporate PC.
- [ ] Definisikan behavior bila prerequisite download gagal/offline.
- [ ] Definisikan behavior bila user membatalkan Google Drive install.

### UX contract

Jika Google Drive sudah tersedia:

```text
Google Drive for desktop
✓ Sudah terpasang
```

Jika belum tersedia:

```text
Google Drive for desktop diperlukan

[Install Google Drive & Lanjut]
[Saya akan mengaturnya sendiri]
```

### Exit criteria

Prerequisite flow mempunyai state machine yang jelas dan testable.

---

## 12.04 — Google Drive Prerequisite Detection

**Owner:** Assistant / repository

### Tasks

- [ ] Implement detection tanpa bergantung pada satu drive letter.
- [ ] Hindari false positive hanya karena folder bernama Google Drive ada.
- [ ] Bedakan `installed`, `running`, dan `filesystem ready` bila memungkinkan.
- [ ] Tambah unit/regression test.

### Exit criteria

Existing installation dapat dilewati; missing installation dapat dikenali dengan aman.

---

## 12.05 — Official Google Drive Download / Install Flow

**Owner:** Assistant + Windows UAT

### Tasks

- [ ] Gunakan URL/sumber resmi Google saja.
- [ ] Download ke temporary location.
- [ ] Jangan commit binary installer Google ke repository.
- [ ] Tampilkan publisher/source secara jelas di wizard.
- [ ] Jalankan installer resmi dengan mode yang sesuai.
- [ ] Tangani cancel/failure/reboot-needed states.
- [ ] Cleanup temporary installer setelah aman.
- [ ] Sediakan pilihan manual fallback bila download gagal atau policy perusahaan melarang install otomatis.

### Manual UAT

- [ ] PC tanpa Google Drive.
- [ ] PC dengan Google Drive existing.
- [ ] User membatalkan install Google Drive.
- [ ] Internet unavailable/download failure.

### Exit criteria

User normal tidak perlu membuka browser sendiri hanya untuk menemukan Google Drive installer.

---

## 12.06 — Google Drive First-Run Readiness UX

**Owner:** Assistant + Windows UAT

Install sukses tidak berarti user sudah login.

### Tasks

- [ ] Detect `installed but not ready` state.
- [ ] Tampilkan instruction untuk login bila filesystem Google Drive belum siap.
- [ ] Sediakan `Buka Google Drive` bila masuk akal.
- [ ] Sediakan `Periksa Lagi`/retry behavior bila masuk akal.
- [ ] Jangan meminta atau menyimpan credential Google.

### Exit criteria

User memahami perbedaan antara aplikasi Google Drive sudah dipasang dan Drive siap digunakan.

---

## 12.07 — PyInstaller / Frozen Build Configuration

**Owner:** Assistant / repository

### Tasks

- [ ] Tambah pinned/dev packaging dependency.
- [ ] Buat reproducible `.spec` atau build configuration.
- [ ] Windowed application (tanpa console release).
- [ ] Include runtime resources.
- [ ] Include Qt plugins yang benar-benar diperlukan.
- [ ] Include app icon.
- [ ] Embed version/product metadata.
- [ ] Hindari accidental inclusion project/source/test data yang tidak perlu.
- [ ] Buat build script yang repeatable.

### Exit criteria

Clean checkout dapat menghasilkan frozen app tanpa manual copying file satu per satu.

---

## 12.08 — Portable Build v0.1.0

**Owner:** Assistant + Windows UAT

### Tasks

- [ ] Produce `ScriptManager-0.1.0-Windows-x64` folder/build.
- [ ] Produce ZIP portable.
- [ ] Launch tanpa Python/VS Code.
- [ ] Verify runtime version.
- [ ] Verify resources.

### Manual UAT — USER

User menjalankan build portable langsung, bukan `python main.py`.

Check minimum:

- [ ] app launch;
- [ ] New Project;
- [ ] Open existing `.smproj`;
- [ ] Source Sync;
- [ ] NASKAH;
- [ ] DIALOG;
- [ ] TRACKING;
- [ ] DELIVERY;
- [ ] DATA;
- [ ] Project Settings;
- [ ] Help/User Guide;
- [ ] Backup/Recovery;
- [ ] close/reopen;
- [ ] project lama tetap terbuka.

### Exit criteria

Portable frozen app dapat menggantikan `python main.py` untuk workflow normal.

---

## 12.09 — Packaged Runtime Diagnostics

**Owner:** Assistant + Windows UAT

### Tasks

- [ ] Verify error reporting tetap user-friendly tanpa console.
- [ ] Pastikan fatal startup error dapat didiagnosis.
- [ ] Pastikan report-problem/environment info memakai packaged runtime info yang benar.
- [ ] Pastikan path internal frozen tidak bocor sebagai requirement user.

### Exit criteria

Jika packaged app gagal, developer masih memiliki informasi yang cukup untuk diagnosis.

---

## 12.10 — Windows Application Identity

**Owner:** Assistant / repository

### Tasks

- [ ] Product name: `Script Manager`.
- [ ] Version: `0.1.0`.
- [ ] File description.
- [ ] Company/publisher field sementara sesuai keputusan project.
- [ ] App icon.
- [ ] Taskbar/window icon.
- [ ] Executable naming.
- [ ] Consistent resource metadata.

### Note

Splash dan visual About redesign tetap out-of-scope baseline.

### Exit criteria

File/property/UI identity tidak terlihat seperti generic Python executable.

---

## 12.11 — `.smproj` Windows File Association

**Owner:** Assistant + Windows UAT

### Tasks

- [ ] Register `.smproj` sebagai `Script Manager Project`.
- [ ] Register project icon.
- [ ] Pass opened project path ke executable.
- [ ] Test spaces/Unicode path.
- [ ] Test double-click after fresh Windows login.

### Manual UAT — USER

- [ ] Double-click `.smproj` membuka Script Manager.
- [ ] Project yang benar langsung terbuka.
- [ ] Path dengan spasi aman.
- [ ] Existing normal File → Open tetap aman.

### Exit criteria

`.smproj` berperilaku seperti format file aplikasi desktop yang sebenarnya.

---

## 12.12 — Inno Setup Installer Wizard

**Owner:** Assistant / repository

### Tasks

- [ ] Buat Inno Setup script.
- [ ] Install ke lokasi Windows yang benar.
- [ ] Start Menu shortcut.
- [ ] Optional Desktop shortcut bila diputuskan.
- [ ] `.smproj` association.
- [ ] prerequisite screen.
- [ ] Google Drive prerequisite integration.
- [ ] uninstall support.
- [ ] upgrade support.
- [ ] version metadata.
- [ ] app icon/setup icon.
- [ ] license/privacy/support text bila diperlukan.

### Important

Inno Setup hanya dibutuhkan pada developer/build environment. User hanya menerima `ScriptManagerSetup-0.1.0.exe`.

### Exit criteria

Satu executable installer dapat memasang Script Manager tanpa Python/VS Code/Inno Setup di komputer user.

---

## 12.13 — Installer UAT

**Owner:** USER + Assistant triage

### Manual checklist

- [ ] Jalankan installer sebagai user normal.
- [ ] Google Drive already installed path.
- [ ] Google Drive missing path.
- [ ] launch dari Start Menu.
- [ ] launch dari Desktop shortcut bila enabled.
- [ ] open `.smproj` via double-click.
- [ ] create new project.
- [ ] source sync.
- [ ] close/reopen.
- [ ] uninstall.
- [ ] verify project files tidak terhapus.
- [ ] reinstall.
- [ ] verify existing project masih dapat dibuka.

### Exit criteria

Fresh-user installation tidak membutuhkan development environment.

---

## 12.14 — User Data & Upgrade Safety

**Owner:** Assistant + USER

### Tasks

- [ ] Confirm uninstall tidak menghapus project `.smproj`.
- [ ] Confirm backup project tetap ada.
- [ ] Confirm source/audio/stem/delivery external data tidak disentuh.
- [ ] Confirm settings behavior setelah reinstall sesuai policy.
- [ ] Confirm install-over-existing works.
- [ ] Confirm database migration tetap backup-safe.

### Exit criteria

Installer tidak pernah menjadi risiko terhadap project production user.

---

## 12.15 — Build Automation / Release Reproducibility

**Owner:** Assistant / repository

### Preferred direction

Gunakan GitHub Actions Windows runner untuk menghasilkan artifacts dari commit/tag yang sama bila feasible.

### Tasks

- [ ] Windows build workflow.
- [ ] Frozen app build.
- [ ] Installer compile.
- [ ] Artifact upload.
- [ ] Version consistency check.
- [ ] SHA-256 generation.

### Exit criteria

Release tidak bergantung pada folder lokal developer yang tidak terdokumentasi.

---

## 12.16 — v0.1.0 Release Candidate

**Owner:** Assistant

### Tasks

- [ ] Freeze source commit.
- [ ] Python compile success.
- [ ] Full tests success.
- [ ] Qt runtime success.
- [ ] Packaged runtime UAT accepted.
- [ ] Installer UAT accepted.
- [ ] Upgrade/data safety accepted.
- [ ] Build artifacts from same source/version.
- [ ] Generate checksums.
- [ ] Prepare release notes.

### Exit criteria

v0.1.0 layak menjadi baseline yang sengaja dipertahankan untuk update test berikutnya.

---

## 12.17 — Publish GitHub Release v0.1.0

**Owner:** Assistant where permissions allow; USER for manual GitHub action if required

### Tasks

- [ ] Create tag `v0.1.0` at accepted release commit.
- [ ] Publish full GitHub Release, bukan draft/prerelease.
- [ ] Attach installer.
- [ ] Attach portable ZIP.
- [ ] Attach checksum file.
- [ ] Publish release notes.

### Reason full release is required

Current update checker reads GitHub `/releases/latest`; baseline therefore harus muncul sebagai latest published release.

### Exit criteria

Release v0.1.0 dapat diunduh dari halaman GitHub Releases sebagai user biasa.

---

## 12.18 — Install Official Baseline Release

**Owner:** USER

### Manual action

- [ ] Download installer dari GitHub Release v0.1.0.
- [ ] Install release tersebut seperti user baru.
- [ ] Jangan mengganti baseline ini dengan development build sampai update test selesai.

### Exit criteria

PC UAT memiliki Script Manager v0.1.0 resmi yang berasal dari published release.

---

## 12.19 — Real Update Checker Baseline Test

**Owner:** USER

Dengan latest GitHub Release masih v0.1.0:

```text
Bantuan
→ Periksa Pembaruan
```

Expected:

```text
Current: 0.1.0
Latest:  0.1.0
Aplikasi sudah terbaru
```

### Tasks

- [ ] Online success.
- [ ] Release page link benar.
- [ ] Offline/error state tetap user-friendly.

### Exit criteria

Packaged app benar-benar dapat berbicara dengan published release endpoint.

---

# 6. Deferred Update Validation — After Splash/About

Bagian berikut dikerjakan setelah baseline v0.1.0 selesai dan installed.

---

## 12.20 — Splash Screen + About Work

**Owner:** USER + Assistant

- [ ] Bahas isi Splash Screen.
- [ ] Bahas tampilan Splash Screen.
- [ ] Bahas isi About.
- [ ] Redesign About.
- [ ] Implement/test.

Tidak boleh mengubah baseline v0.1.0 yang sudah terpasang untuk update test.

---

## 12.21 — Version Bump to v0.2.0

**Owner:** Assistant

- [ ] Bump application version.
- [ ] Ensure package metadata matches.
- [ ] Ensure About displays same version.
- [ ] Build portable + installer.
- [ ] Regression + packaged UAT.

---

## 12.22 — Publish GitHub Release v0.2.0

**Owner:** Assistant/USER according to release permissions

- [ ] Full release.
- [ ] Installer asset.
- [ ] Portable asset.
- [ ] Checksums.
- [ ] Release notes.

---

## 12.23 — End-to-End Update Detection

**Owner:** USER

Sebelum menginstall v0.2.0, buka installed v0.1.0:

```text
Bantuan
→ Periksa Pembaruan
```

Expected:

```text
Current: 0.1.0
Latest:  0.2.0
Pembaruan tersedia
```

- [ ] Open release page from application.
- [ ] Download official v0.2.0 installer.
- [ ] Install over v0.1.0.
- [ ] Project/user data preserved.

---

## 12.24 — Post-Update Validation

**Owner:** USER + Assistant

- [ ] v0.2.0 launches.
- [ ] Splash new version correct.
- [ ] About version/content correct.
- [ ] Existing `.smproj` opens.
- [ ] source/tracking/delivery workflow intact.
- [ ] update checker now says `Aplikasi sudah terbaru`.

---

## 12.25 — Phase 12 Final Acceptance

**Owner:** USER + Assistant

### Acceptance criteria

- [ ] Script Manager runs without Python development environment.
- [ ] Installer wizard is user-friendly.
- [ ] Google Drive prerequisite flow is clear and safe.
- [ ] `.smproj` association works.
- [ ] uninstall/reinstall does not destroy project data.
- [ ] in-place upgrade works.
- [ ] GitHub Release flow works.
- [ ] packaged update checker detects a real newer release.
- [ ] full automated gate remains green.
- [ ] Windows UAT accepted.

### Final decision

Only after these criteria are accepted should the project be considered to have a proven Windows release lifecycle.

---

# 7. Manual Responsibilities — User

Bagian yang kemungkinan membutuhkan tindakan manual user selama Phase 12:

1. Menjalankan portable `.exe` pada Windows nyata.
2. Menjalankan installer sebagai user normal.
3. Menguji Google Drive existing/missing prerequisite flow.
4. Login Google Drive dengan akun sendiri bila diperlukan.
5. Menguji `.smproj` double-click.
6. Menguji install/uninstall/reinstall.
7. Menguji upgrade install-over-existing.
8. Menjaga installed baseline v0.1.0 sampai v0.2.0 dipublikasikan.
9. Menjalankan `Bantuan → Periksa Pembaruan` sebelum dan setelah update.
10. Melakukan manual GitHub Release upload/publish hanya jika connector/tool permission tidak mendukung action tersebut.

Assistant harus memberikan perintah/checklist yang spesifik pada saat masing-masing manual gate tiba; user tidak perlu melakukan semua item ini sekaligus.

---

# 8. Build / Distribution Safety Rules

- Jangan commit certificate/private signing key.
- Jangan commit Google Drive installer binary.
- Jangan menyimpan credential Google.
- Jangan menghapus user project saat uninstall.
- Jangan mengubah `.smproj` format hanya untuk kebutuhan installer.
- Jangan membuat business logic bergantung pada drive letter Windows.
- Jangan menandai release COMPLETE sebelum packaged Windows UAT.
- Jangan publish release dari unaccepted commit.
- Jangan membuat v0.2.0 sebelum v0.1.0 baseline packaged/update-check flow terbukti.

---

# 9. Future After Phase 12

Setelah lifecycle Windows terbukti, kandidat pekerjaan berikutnya:

```text
Release Hardening
├── Windows code signing
├── SmartScreen reputation strategy
├── richer diagnostics
└── v1.0.0 readiness

Cross-Platform Readiness
├── OS abstraction audit
├── relocatable external paths
├── macOS .app
├── Universal 2 feasibility
├── Developer ID signing
├── notarization
└── DMG distribution
```

macOS tidak dikerjakan dalam Phase 12, tetapi semua keputusan packaging Phase 12 harus menghindari penguncian core application ke Windows.
