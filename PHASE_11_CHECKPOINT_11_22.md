# Phase 11 — Checkpoint 11.18–11.22 & UAT Gate

Status: **11.01–11.22 implementation COMPLETE; 11.23 staged UAT A–D COMPLETE, UAT E PENDING**  
Branch: `phase-11-new-project-setup`  
PR: #75  
Packaging EXE: **OUT OF SCOPE / tidak disentuh**.

Dokumen ini adalah checkpoint append-only untuk pekerjaan 11.18–11.22. File utama `PHASE_11_NEW_PROJECT_SETUP.md` tetap menjadi rencana Phase 11; checkpoint ini dibuat agar evidence terbaru tidak hilang ketika connector GitHub tidak menyediakan patch-in-place aman untuk file rencana yang besar. Final reconciliation dokumen dilakukan setelah UAT/final acceptance.

---

## 11.18 — Regression Project Lifecycle

Status: [x] COMPLETE

Skenario yang dikunci:

- [x] New Project
- [x] Open Project
- [x] Save
- [x] Save As
- [x] Duplicate
- [x] Recover
- [x] Recent Projects
- [x] Close/Reopen
- [x] `.smproj` file association
- [x] legacy filename seperti `AA23.smproj`
- [x] project identity tetap stabil
- [x] tidak ada auto rename existing project
- [x] overwrite protection tetap aktif

Evidence:

- full regression: `412 passed, 49 skipped`;
- Qt runtime: success;
- Phase 11 scale smoke: success.

Catatan: satu failure sementara berasal dari assertion test yang mengasumsikan validasi suffix `.smproj` berada di `main.py`. Implementasi production memang meneruskan kandidat command-line ke `open_project_path()` dan validasi format tetap dimiliki layer Project/ProjectManager. Test diperbaiki agar mengunci kontrak yang benar; production lifecycle tidak diubah untuk kasus tersebut.

---

## 11.19 — Regression Source Sync

Status: [x] COMPLETE

Skenario yang dikunci:

- [x] initial sync normal
- [x] source tanpa perubahan
- [x] corrupt workbook
- [x] duplicate episode
- [x] delimiter salah
- [x] source berubah setelah preflight / stale source safety
- [x] cancel preflight
- [x] cancel wizard
- [x] failure setelah `.smproj` dibuat dan rollback
- [x] source revision setelah project berjalan
- [x] F5 existing tetap menggunakan production Source Sync
- [x] Source Refresh Preview existing tetap aman
- [x] lineage / recording history existing tidak rusak
- [x] initial creation, F5, dan preview tetap memakai `SourceSyncEngine` yang sama

Evidence:

- full regression: `417 passed, 49 skipped`;
- Qt runtime: success;
- Phase 11 scale smoke: success.

Tidak ada production bug yang ditemukan pada gate ini. Failure sementara yang muncul berasal dari test yang bergantung pada nama private attribute worker (`engine` vs `_engine`); test diubah menjadi contract behavior/ownership dan production code tidak diubah.

---

## 11.20 — Regression Filesystem & Drive

Status: [x] COMPLETE

Skenario:

- [x] local folder
- [x] Google Drive Desktop folder sebagai filesystem
- [x] path dengan spasi
- [x] Unicode path
- [x] mapped/network/UNC-style path tetap diperlakukan sebagai filesystem
- [x] read-only folder
- [x] missing folder
- [x] temporary unavailable existing folder
- [x] browser URL di field Folder ditolak
- [x] filesystem path di field URL baru ditolak

Folder relationship policy:

- [x] `Source == Stem` → **ERROR / blocker** untuk konfigurasi baru;
- [x] `Source == Setoran` → **ERROR / blocker** untuk konfigurasi baru;
- [x] `Stem == Setoran` → **WARNING**, tetap diperbolehkan;
- [x] existing legacy project yang sudah memiliki Source/output overlap tetap dapat dibuka; kondisi unchanged diturunkan menjadi warning agar compatibility tidak rusak.

Evidence:

- full regression: `425 passed, 49 skipped`;
- Qt runtime: `46 passed`;
- scale 100%: `3 passed`;
- scale 125%: `3 passed`;
- scale 150%: `3 passed`.

---

## 11.21 — Regression UI & Accessibility

Status: [x] COMPLETE

Skenario:

- [x] 1920×1080 logical-size smoke
- [x] 1366×768 logical-size smoke
- [x] scale 100%
- [x] scale 125%
- [x] scale 150%
- [x] keyboard Tab order
- [x] Back/Next menjaga state
- [x] Enter tidak trigger Create sebelum/final tanpa explicit action
- [x] Escape/Cancel aman saat tidak ada background operation
- [x] long project/path labels tetap berada pada page yang scrollable
- [x] long preflight error list scrollable
- [x] focus pindah ke field bermasalah pada production `TransactionalNewProjectDialog`
- [x] stale preflight mengarahkan user kembali ke Milestone 2 dan field/action relevan
- [x] help `?` keyboard reachable dan memiliki accessible name
- [x] milestone state memakai simbol `✓`, `⚠`, `✕`, `●`, bukan warna saja

CI hardening:

- [x] accessibility suite dimasukkan langsung ke Qt runtime job; tidak hanya menjadi skip pada regular job tanpa PySide6.

Evidence final:

- full regression: `425 passed, 55 skipped`;
- Qt runtime + accessibility: `52 passed`;
- scale 100% / 125% / 150%: masing-masing `3 passed`.

Catatan: CI pertama setelah memasukkan accessibility suite menemukan assertion test yang memanggil `_show_step(3)`, sehingga validator Milestone 4 secara sah mengganti PENDING menjadi ERROR. Test diperbaiki untuk menguji rail rendering secara langsung. Production UI tidak diubah untuk failure tersebut.

Windows DPI visual acceptance nyata tetap menjadi bagian UAT 11.23; Qt offscreen scale smoke tidak dianggap menggantikannya.

---

## 11.22 — Contract Test Reusable Form & Settings Roundtrip

Status: [x] COMPLETE

Contract:

```text
New Project inputs
→ ProjectSettings
→ create .smproj
→ reopen .smproj
→ Project Settings
→ values identik
```

Pekerjaan:

- [x] field parity test
- [x] default parity test
- [x] normalization parity test
- [x] folder parity test
- [x] audio settings parity test
- [x] URL parity test
- [x] delimiter parity test
- [x] project metadata parity test
- [x] `project_folder` dibuktikan runtime-only dan tidak bocor ke persistent settings
- [x] Project Settings `.smproj` field dibuktikan read-only dan menunjuk file aktual setelah reopen
- [x] Unicode dan whitespace normalization dibuktikan sepanjang roundtrip

Test baru:

- `tests/test_phase11_reusable_roundtrip_contract.py`
- `tests/test_phase11_qt_reusable_roundtrip.py`

Qt end-to-end test memakai production `TransactionalNewProjectDialog`, shared `ProjectConfigurationSections`, `ProjectManager.create()`, fresh `ProjectManager.open()`, dan `ProjectSettingsDialog._collect_candidate()`; bukan jalur model khusus test.

Evidence final:

- full regression: `429 passed, 57 skipped`;
- Qt runtime termasuk accessibility + reusable roundtrip: `54 passed`;
- scale 100% / 125% / 150%: masing-masing `3 passed`;
- compile Python sources: success.

Exit criteria terpenuhi: New Project dan Project Settings tidak dapat drift pada persistent field/default/normalization tanpa contract test gagal.

---

# 11.23 — Staged UAT Gate

Status: [ ] UAT A–D COMPLETE; UAT E PENDING USER ACCEPTANCE

Automated implementation gate 11.01–11.22 sudah selesai. PR #75 **jangan di-merge** sebelum UAT A–E berikut diterima pada environment Windows operator.

## UAT A — Wizard shell + Milestone 1

Status: [x] COMPLETE — diterima operator pada Windows.

- [x] rail milestone tampil rapi dan status mudah dibaca;
- [x] Back/Next mempertahankan input;
- [x] Nama/Kode/Klien/Tanggal/Lokasi bekerja;
- [x] auto-code berhenti menimpa Kode setelah Kode diedit manual;
- [x] preview filename berbentuk `KODE - NAMA PROYEK.smproj`;
- [x] existing destination diblokir;
- [x] tampilan layak pada 100%, 125%, dan 150% Windows scaling.

## UAT B — Sumber Naskah

Status: [x] COMPLETE — diterima operator pada Windows.

- [x] pilih Folder Sumber;
- [x] `.xlsx/.xlsm` ter-scan;
- [x] representative filename/pattern tampil;
- [x] delimiter sebelum/sesudah episode bekerja pada seluruh filename;
- [x] preview episode benar;
- [x] Source Preflight dapat dijalankan;
- [x] blocker workbook/parsing terlihat jelas;
- [x] tidak ada `.smproj` dibuat hanya karena preflight/navigation.

UAT finding yang diperbaiki sebelum acceptance:

- perbedaan case saja (`Episode 1`, `episode 2`, `EPISODE 3`) tidak lagi dianggap pola berbeda;
- delimiter episode production juga case-insensitive;
- nama file asli tetap dipertahankan untuk preview/error;
- pola yang benar-benar berbeda seperti `Episode` vs `Chapter` tetap blocker;
- regression gate setelah patch: `430 passed, 57 skipped`, Qt runtime + scale smoke success.

## UAT C — Audio + Folder & Tautan

Status: [x] COMPLETE — diterima operator pada Windows.

- [x] Folder Stem dapat dipilih/dibuat;
- [x] Folder Setoran dapat dipilih/dibuat;
- [x] WAV sample rate / bit depth / channel tersimpan;
- [x] `Source == Stem/Setoran` diblokir;
- [x] `Stem == Setoran` memberi warning;
- [x] Google Drive Desktop dipakai sebagai filesystem path;
- [x] URL browser hanya masuk field Tautan Drive;
- [x] tombol help `?` menjelaskan perbedaan filesystem dan URL.

## UAT D — Final Review + Transactional Create

Status: [x] COMPLETE — diterima operator pada Windows.

- [x] Review merangkum seluruh konfigurasi;
- [x] tombol `Ubah` kembali ke milestone yang benar;
- [x] `Buat Proyek` disabled bila blocker tersisa;
- [x] filename final benar;
- [x] simulasi failure tidak meninggalkan `.smproj`/SQLite sidecar/project setengah jadi;
- [x] input wizard tetap ada setelah failure sehingga dapat dicoba ulang.

## UAT E — Initial Sync + Project Settings

Status: [ ] PENDING

- [ ] Create sukses menjalankan Initial Source Sync otomatis;
- [ ] wizard tetap terbuka selama sync dan progress terlihat;
- [ ] setelah sukses Dashboard terbuka dengan episode/dialogue hasil sync;
- [ ] project baru masuk Recent Projects hanya setelah sukses;
- [ ] Pengaturan Proyek memiliki 4 tab: Proyek / Sumber Naskah / Audio & Setoran / Tautan Drive;
- [ ] nilai yang dibuat dari wizard identik setelah project dibuka kembali;
- [ ] file `.smproj` pada Settings read-only;
- [ ] project existing dengan drive offline tetap dapat dibuka dan menampilkan warning, bukan blocker;
- [ ] F5/Sinkronkan Sumber existing masih bekerja seperti sebelumnya.

Setelah UAT A–E diterima, lanjut ke 11.24 Final Acceptance dan baru merge PR #75.
