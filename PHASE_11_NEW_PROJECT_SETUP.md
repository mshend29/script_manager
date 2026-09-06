# Phase 11 — New Project Setup Wizard & Project Settings Alignment

Status: **IN PROGRESS — 11.01–11.09 COMPLETE**  
Baseline: `main` after PR #73 (`cc64a8c758693d0c1366a417068d37d839105568`)  
Scope: redesign flow **Proyek Baru**, preflight sumber, initial sync, dan penyelarasan **Pengaturan Proyek**.  
Packaging EXE: **OUT OF SCOPE** untuk phase ini.

---

## Tujuan Phase

Phase ini mengubah pembuatan proyek dari form sederhana menjadi **setup wizard berbasis milestone** yang memastikan proyek benar-benar siap dipakai sebelum user masuk ke workspace utama.

Prinsip utama:

1. **Selesai wizard = proyek siap kerja.**
2. Semua konfigurasi operasional penting harus ditentukan sejak awal.
3. Sumber naskah harus terbaca dan lolos preflight sebelum proyek dibuat.
4. Setelah `.smproj` dibuat, initial source sync berjalan otomatis.
5. Pengaturan yang diisi saat Proyek Baru harus identik dengan yang tersedia di Pengaturan Proyek.
6. Existing project dan workflow aplikasi yang sudah stabil tidak boleh rusak.
7. Perubahan dilakukan bertahap dengan regression gate; jangan melompat ke pekerjaan berikutnya sebelum pekerjaan aktif selesai dan test terkait hijau.

---

## Flow Target

```text
Proyek Baru
  ↓
1. Inisialisasi Proyek
  ↓
2. Sumber Naskah
  ↓
   Source filename validation
   + workbook preflight read-only
  ↓
3. Sumber Audio
  ↓
4. Folder & Tautan
  ↓
5. Review & Buat Proyek
  ↓
Final validation
  ↓
Create .smproj
  ↓
Initial Source Sync otomatis
  ↓
Verify database
  ↓
Open Project Dashboard dengan data terisi
```

Milestone wizard:

```text
● 1  Inisialisasi Proyek
│
● 2  Sumber Naskah
│
● 3  Sumber Audio
│
● 4  Folder & Tautan
│
● 5  Buat Proyek
```

Status milestone harus dapat menunjukkan:

- belum dikunjungi;
- aktif;
- `✓` valid;
- `⚠` warning;
- error/blocking.

---

# Keputusan Produk yang Sudah Dikunci

## Nama file proyek baru

Format file project baru:

```text
KODE PROYEK - NAMA PROYEK.smproj
```

Contoh:

```text
AA23 - Cinta di Ujung Senja.smproj
```

Ketentuan:

- kode proyek dan nama proyek tetap disimpan sebagai metadata terpisah;
- sanitasi hanya berlaku pada **nama file**, tidak mengubah nilai metadata asli;
- karakter Windows invalid harus disanitasi;
- `.smproj` tidak boleh terduplikasi;
- project existing **tidak** di-rename otomatis;
- Save As / Duplicate tetap mengikuti target yang dipilih user;
- preview path final harus terlihat sebelum proyek dibuat.

## Field wajib vs opsional

Blocking untuk proyek baru:

- Nama Proyek;
- Kode Proyek;
- Klien;
- Tanggal Mulai;
- Lokasi penyimpanan `.smproj`;
- Folder Sumber Naskah;
- delimiter episode yang valid untuk seluruh source;
- source workbook lolos preflight;
- Folder Stem / Export;
- Folder Setoran;
- konfigurasi WAV yang valid.

Opsional tetapi direkomendasikan:

- Drive Utama URL;
- Material URL;
- Setoran URL.

URL browser tidak boleh dianggap sebagai filesystem path.

---

# Aturan Eksekusi Phase

**Jangan melompat pekerjaan.** Gunakan checklist 24 pekerjaan di bawah secara berurutan kecuali ada alasan teknis yang terdokumentasi.

Untuk setiap pekerjaan:

1. baca bagian pekerjaan aktif;
2. cek dependency;
3. implement hanya scope pekerjaan tersebut;
4. tambahkan / update test yang relevan;
5. jalankan test targeted;
6. jalankan regression suite bila menyentuh core flow;
7. update status pekerjaan pada file ini;
8. catat keputusan baru pada **Decision Log**;
9. baru lanjut ke pekerjaan berikutnya.

Jika sebuah pekerjaan membuka kebutuhan baru, tambahkan sebagai subtask pada pekerjaan terkait terlebih dahulu. Jangan langsung membuat feature sampingan di luar phase plan.

---

# Daftar Pekerjaan Phase 11

## 11.01 — Freeze baseline sebelum perubahan

Status: [x] COMPLETE

Tujuan: memastikan phase dimulai dari aplikasi yang stabil.

Pekerjaan:

- [x] Verifikasi `main` terbaru.
- [x] Jalankan full test baseline.
- [x] Jalankan Qt runtime baseline.
- [x] Catat jumlah pass / skip / fail.
- [x] Pastikan tidak ada perubahan packaging EXE.
- [x] Pastikan existing `.smproj` dapat dibuka.
- [x] Pastikan Open / Save / Save As / Duplicate / Recover / Recent Project tetap hijau.
- [x] Identifikasi file zona risiko tinggi:
  - `core/project_manager.py`
  - source sync pipeline
  - project data invalidation
  - Tracking / Delivery filesystem invalidation
- [x] Buat feature branch phase dari `main` terbaru.

Baseline evidence:

- PR #73 / commit `6d2041e01ceba9969262619136946bf8f7ec0a27`: `344 passed, 15 skipped`;
- Qt runtime baseline: success;
- `main` Phase 11 start: `86224ad777033b0668999799fab97674a8cf9bec` (hanya menambah dokumen Phase 11 dibanding baseline code);
- feature branch: `phase-11-new-project-setup`;
- packaging EXE tidak disentuh.

Exit criteria:

- baseline test hijau;
- baseline commit tercatat;
- tidak ada pekerjaan feature lain bercampur.

---

## 11.02 — Definisikan kontrak konfigurasi tunggal

Status: [x] COMPLETE  
Depends on: 11.01

Tujuan: Proyek Baru dan Pengaturan Proyek memiliki sumber field yang sama.

Kontrak field:

### Inisialisasi Proyek

- [x] Nama Proyek
- [x] Kode Proyek
- [x] Klien
- [x] Tanggal Mulai
- [x] lokasi penyimpanan project baru

### Sumber Naskah

- [x] Folder Sumber
- [x] Sebelum Nomor Episode
- [x] Setelah Nomor Episode

### Sumber Audio

- [x] Folder Stem / Mixdown / Export
- [x] Folder Setoran
- [x] Format WAV
- [x] Sample rate
- [x] Bit depth
- [x] Channel

### Folder & Tautan

- [x] ringkasan Folder Naskah
- [x] ringkasan Folder Stem
- [x] ringkasan Folder Setoran
- [x] Drive Utama URL
- [x] Material URL
- [x] Setoran URL

Pekerjaan:

- [x] Pastikan `ProjectSettings` mencakup seluruh data persistent yang diperlukan.
- [x] Jangan menambah schema baru jika field existing sudah cukup.
- [x] Pertahankan `project_folder` sebagai runtime/read-only untuk existing project.
- [x] Definisikan field blocking, warning, dan optional.
- [x] Definisikan normalization tunggal untuk New Project dan Settings.

Exit criteria:

- tidak ada field yang hanya hidup di salah satu window;
- data model yang dibutuhkan sudah dipastikan.

---

## 11.03 — Pisahkan reusable configuration widgets

Status: [x] COMPLETE  
Depends on: 11.02

Tujuan: menghindari dua implementasi form yang dapat drift.

Target komponen konseptual:

- [x] `ProjectIdentitySection`
- [x] `SourceConfigurationSection`
- [x] `AudioOutputSection`
- [x] `DriveLinksSection`
- [x] reusable `FolderField`

Pekerjaan:

- [x] Extract komponen dari `NewProjectDialog` dan `ProjectSettingsDialog` dengan perubahan visual seminimal mungkin terlebih dahulu.
- [x] Pastikan widget dapat dipakai di wizard maupun tab Settings.
- [x] Pusatkan collection `ProjectSettings` dari widget.
- [x] Pusatkan load existing `ProjectSettings` ke widget.
- [x] Pusatkan basic validation.
- [x] Tambahkan test roundtrip widget → settings → widget.

Guardrail:

- jangan redesign wizard pada pekerjaan ini;
- tujuan tahap ini adalah architecture extraction terlebih dahulu.

Exit criteria:

- form existing masih bekerja;
- tidak ada duplikasi logic field utama.

---

## 11.04 — Implement formatter nama file `.smproj`

Status: [x] COMPLETE  
Depends on: 11.02

Tujuan: file project baru selalu menggunakan gabungan kode + nama proyek.

Format:

```text
KODE - NAMA PROYEK.smproj
```

Pekerjaan:

- [x] Buat formatter resmi di layer yang sesuai; jangan menyusun filename hanya di UI.
- [x] Sanitasi karakter Windows invalid.
- [x] Bersihkan whitespace berlebih.
- [x] Cegah suffix `.smproj` ganda.
- [x] Pertahankan Unicode yang valid.
- [x] Preview path destination.
- [x] Collision detection sebelum Create aktif.
- [x] Pastikan metadata name/code tidak ikut berubah oleh sanitasi filename.

Test wajib:

- [x] nama + kode normal;
- [x] Unicode;
- [x] invalid Windows chars;
- [x] code / name berisi `.smproj`;
- [x] whitespace;
- [x] existing destination;
- [x] project existing lama tetap dapat dibuka.

Exit criteria:

- `ProjectManager.create()` dan preview UI menggunakan rule filename yang sama.

Checkpoint test setelah 11.02–11.04:

- full suite PR #75: `356 passed, 16 skipped`;
- compile Python sources: success;
- Qt runtime smoke tests: success.

---

## 11.05 — Bangun shell wizard Proyek Baru

Status: [x] COMPLETE  
Depends on: 11.03, 11.04

Tujuan: mengganti form panjang dengan wizard milestone tanpa mengaktifkan create kompleks terlebih dahulu.

UI target:

- [x] milestone rail di kiri;
- [x] active page di kanan;
- [x] title `Proyek Baru`;
- [x] tombol `?` di header;
- [x] footer `< Kembali`, `Berikutnya >`, `Batal`;
- [x] milestone terakhir memakai `Buat Proyek`;
- [x] state valid/warning/error;
- [x] user boleh kembali ke milestone sebelumnya;
- [x] forward navigation dikunci oleh validation gate;
- [x] data field tetap tersimpan saat Back/Next.

Responsiveness:

- [x] 1920×1080;
- [x] 1366×768;
- [x] scale 100%;
- [x] scale 125%;
- [x] scale 150%.

Automated responsiveness evidence memakai Qt offscreen logical-size + `QT_SCALE_FACTOR` smoke. Windows DPI acceptance nyata tetap diuji kembali pada 11.21/11.23 dan tidak dianggap tergantikan oleh smoke CI ini.

Exit criteria:

- wizard dapat dinavigasikan tanpa membuat project;
- tidak ada regresi startup / existing project.

---

## 11.06 — Milestone 1: Inisialisasi Proyek

Status: [x] COMPLETE  
Depends on: 11.05

Field:

- [x] Nama Proyek
- [x] Kode Proyek
- [x] Klien
- [x] Tanggal Mulai
- [x] Penyimpanan Proyek
- [x] preview final `.smproj`

Validation:

- [x] semua field wajib terisi;
- [x] destination folder valid;
- [x] folder dapat dibuat bila perlu;
- [x] destination writable;
- [x] destination bukan file;
- [x] `.smproj` belum ada.

Auto-code behavior:

- [x] Kode boleh mengikuti Nama Proyek sebelum user mengedit code manual.
- [x] Setelah user mengubah Kode secara manual, perubahan Nama tidak boleh menimpa Kode.

Guardrail:

- [x] belum membuat project/file permanen.

Exit criteria:

- milestone hanya `✓` bila seluruh blocker lolos.

Checkpoint test setelah 11.06:

- full suite: `364 passed, 22 skipped`;
- compile Python sources: success;
- Qt runtime Phase 11 + existing runtime: success;
- Phase 11 wizard scale smoke pada 100% / 125% / 150%: success;
- tidak ada `.smproj` dibuat selama navigasi/validation Milestone 1.

---

## 11.07 — Milestone 2: Sumber Naskah

Status: [x] COMPLETE  
Depends on: 11.05

Tujuan: source folder dan episode extraction harus benar sejak awal.

Pekerjaan:

- [x] Folder Sumber wajib.
- [x] Scan `.xlsx/.xlsm` otomatis saat folder dipilih.
- [x] Reuse `SourceFilenameAnalysis` / source filename service existing.
- [x] Tampilkan jumlah file.
- [x] Tampilkan representative filenames.
- [x] Tampilkan pola filename.
- [x] Input delimiter sebelum/after nomor episode.
- [x] Preview episode awal/tengah/akhir.
- [x] Validasi delimiter terhadap **seluruh filename**, bukan hanya preview.

Deteksi:

- [x] filename gagal dibaca;
- [x] episode non-numeric;
- [x] duplicate episode;
- [x] lebih dari satu pola;
- [x] gap episode sebagai warning terpisah;
- [x] source folder tanpa workbook.

Exit criteria:

- seluruh source yang dianggap naskah dapat dipetakan ke episode secara deterministic.

Checkpoint test setelah 11.07:

- full suite: `372 passed, 24 skipped`;
- Qt runtime termasuk source milestone + existing runtime: success;
- Phase 11 wizard scale smoke: success;
- filename validation tidak membuka isi workbook dan tidak menulis database/fingerprint.

---

## 11.08 — Source Preflight read-only

Status: [x] COMPLETE  
Depends on: 11.07

Tujuan: memastikan source benar-benar dapat diproses sebelum `.smproj` dibuat.

Pekerjaan:

- [x] Reuse parser/inspector produksi; jangan membuat parser khusus wizard.
- [x] Buka workbook secara read-only/preflight.
- [x] Pastikan workbook tidak corrupt.
- [x] Pastikan struktur script dapat dikenali.
- [x] Pastikan episode filename valid.
- [x] Pastikan data dapat diparse.
- [x] Jangan menulis database.
- [x] Progress harus terlihat.
- [x] Preflight dapat dibatalkan.
- [x] Error per file dapat dilihat.

Summary target:

```text
✓ Nama file terbaca
✓ Nomor episode terbaca
✓ Workbook dapat dibuka
✓ Struktur naskah dikenali
✓ N episode siap diimpor
```

Exit criteria:

- milestone Sumber Naskah tidak valid bila preflight blocking gagal.

Checkpoint test setelah 11.08:

- full suite: `377 passed, 27 skipped`;
- compile Python sources: success;
- Qt runtime termasuk preflight UI + existing runtime: success;
- Phase 11 wizard scale smoke: success;
- valid workbook dapat di-inspect dan diparse read-only tanpa database write;
- corrupt workbook menjadi blocker per file;
- milestone 2 tetap blocking sampai preflight sukses.

---

## 11.09 — Milestone 3: Sumber Audio

Status: [x] COMPLETE  
Depends on: 11.05

Field:

- [x] Folder Stem / Mixdown / Export
- [x] Folder Setoran
- [x] Format WAV
- [x] Laju Sampel
- [x] Kedalaman Bit
- [x] Kanal

Validation:

- [x] folder wajib;
- [x] path filesystem valid;
- [x] folder readable/writable sesuai kebutuhan;
- [x] folder belum ada → tampilkan opsi `Buat Folder`;
- [x] tidak meninggalkan temp test file;
- [x] audio option hanya nilai yang didukung aplikasi.

Default existing harus dipertahankan:

- WAV;
- 48 kHz default;
- 24-bit default;
- Mono default.

Exit criteria:

- output configuration siap dipakai Tracking/Delivery.

Checkpoint test setelah 11.09:

- full suite: `382 passed, 29 skipped`;
- compile Python sources: success;
- Qt runtime termasuk Milestone 3 + existing runtime: success;
- Phase 11 wizard scale smoke: success;
- mengetik folder yang belum ada tidak membuat folder otomatis;
- folder baru hanya dibuat lewat aksi explicit `Buat Folder`;
- writable probe membersihkan seluruh temp test file;
- browser URL pada field Folder ditolak sebelum filesystem interpretation.

---

## 11.10 — Milestone 4: Folder & Tautan

Status: [ ] NOT STARTED  
Depends on: 11.07, 11.09

Tujuan: menegaskan filesystem path dan browser link sebagai dua hal berbeda.

Folder summary read-only:

- [ ] Naskah
- [ ] Stem
- [ ] Setoran

URL editable:

- [ ] Drive Utama
- [ ] Material
- [ ] Setoran

Validation:

- [ ] URL boleh kosong.
- [ ] Bila diisi, format harus masuk akal.
- [ ] Jangan melakukan network request sebagai validation gate.
- [ ] URL browser tidak boleh diterima sebagai folder filesystem.

Exit criteria:

- folder operasional jelas;
- tautan tersimpan tanpa memblokir workflow offline.

---

## 11.11 — Help `?` untuk Folder & Google Drive

Status: [ ] NOT STARTED  
Depends on: 11.05

Tujuan: menyediakan bantuan singkat langsung dari wizard dan Settings.

Isi minimum:

- [ ] arti filesystem path;
- [ ] arti Google Drive Desktop path;
- [ ] contoh `G:\My Drive\Client\AA23\Scripts`;
- [ ] arti browser URL;
- [ ] contoh `https://drive.google.com/drive/folders/...`;
- [ ] URL browser tidak digunakan untuk membaca file;
- [ ] Drive Desktop harus tersedia/sync agar filesystem path dapat dipakai;
- [ ] jangan memasukkan URL ke field Folder.

UI:

- [ ] popup/modal ringan;
- [ ] reusable oleh New Project dan Project Settings;
- [ ] tidak bergantung internet.

Catatan:

- visual dokumentasi Help global akan dibahas terpisah; pekerjaan ini hanya bantuan kontekstual wizard/settings.

---

## 11.12 — Milestone 5: Review & Buat Proyek

Status: [ ] NOT STARTED  
Depends on: 11.06–11.11

Tujuan: user melihat seluruh konfigurasi sebelum commit.

Review sections:

- [ ] Inisialisasi;
- [ ] destination `.smproj`;
- [ ] source folder;
- [ ] jumlah workbook;
- [ ] episode range;
- [ ] delimiter;
- [ ] preflight source;
- [ ] audio output;
- [ ] Stem folder;
- [ ] Setoran folder;
- [ ] Drive links.

State summary:

- [ ] `✓ Siap`
- [ ] `⚠ Opsional / dapat dilengkapi nanti`
- [ ] `✕ Harus diperbaiki`

Interaction:

- [ ] `Buat Proyek` disabled bila blocker tersisa.
- [ ] User dapat kembali ke milestone bermasalah.
- [ ] Tidak ada create otomatis hanya karena Enter.

Exit criteria:

- tidak ada konfigurasi blocking yang tersembunyi saat Create ditekan.

---

## 11.13 — Jadikan project creation transactional

Status: [ ] NOT STARTED  
Depends on: 11.12

Target transaction:

```text
Final validation
→ Create .smproj
→ Initialize database
→ Initial source sync
→ Verify
→ Open project
```

Pekerjaan:

- [ ] Pertahankan cleanup behavior `ProjectManager.create()` existing.
- [ ] Extend cleanup untuk failure setelah project file sudah dibuat.
- [ ] Cleanup `.smproj` bila create belum berhasil final.
- [ ] Cleanup `-journal`, `-wal`, `-shm`.
- [ ] Cleanup runtime temp directory.
- [ ] Project gagal tidak masuk Recent Projects.
- [ ] Wizard tetap terbuka setelah failure.
- [ ] Input user tidak hilang setelah failure.

Exit criteria:

- tidak ada project setengah jadi.

---

## 11.14 — Initial Source Sync otomatis

Status: [ ] NOT STARTED  
Depends on: 11.08, 11.13

Tujuan: setelah wizard selesai, project langsung memiliki database produksi.

Pekerjaan:

- [ ] Reuse pipeline `Sinkronkan Sumber` existing.
- [ ] Jangan duplicate prepare/apply implementation.
- [ ] Initial sync berjalan setelah `.smproj` dibuat.
- [ ] Progress tampil di final wizard.
- [ ] Wizard belum ditutup selama sync.
- [ ] Sync dapat memberi error detail.
- [ ] Setelah success, refresh project data state.
- [ ] Setelah success, record Recent Project.
- [ ] Setelah success, buka Project Dashboard.

Expected first dashboard:

- Episodes terisi;
- Dialogues terisi;
- Tokoh terisi;
- Talent/mapping mengikuti hasil import/resolution yang berlaku.

Exit criteria:

- user tidak perlu menekan F5/Sinkronkan Sumber untuk pekerjaan pertama.

---

## 11.15 — Hindari double parsing & stale preflight

Status: [ ] NOT STARTED  
Depends on: 11.08, 11.14

Tujuan: source tidak dibaca mahal dua kali tanpa kontrol dan source tidak boleh berubah antara preview dan commit tanpa diketahui.

Pekerjaan:

- [ ] Simpan source fingerprint/snapshot dari preflight.
- [ ] Reuse konsep fingerprint/source safety existing bila tersedia.
- [ ] Sebelum Create, verifikasi source masih sama.
- [ ] Bila source berubah, invalidate milestone 2 readiness.
- [ ] Minta preflight ulang.
- [ ] Bila aman, reuse hasil preflight bila arsitektur memungkinkan.
- [ ] Jangan mengorbankan correctness hanya demi menghindari re-read.

Exit criteria:

- tidak ada TOCTOU antara preflight dan initial sync.

---

## 11.16 — Redesign Pengaturan Proyek agar sejajar dengan wizard

Status: [ ] NOT STARTED  
Depends on: 11.03, 11.06–11.11

Pengaturan Proyek tetap **tab**, bukan milestone.

Tab target:

```text
[ Proyek ]
[ Sumber Naskah ]
[ Audio & Setoran ]
[ Tautan Drive ]
```

### Tab Proyek

- [ ] Nama Proyek
- [ ] Kode Proyek
- [ ] Klien
- [ ] Tanggal Mulai
- [ ] File `.smproj` read-only

### Tab Sumber Naskah

- [ ] Folder Sumber
- [ ] filename analysis
- [ ] delimiter
- [ ] preview episode
- [ ] re-validation source

### Tab Audio & Setoran

- [ ] Folder Stem
- [ ] Folder Setoran
- [ ] WAV specification

### Tab Tautan Drive

- [ ] Drive Utama
- [ ] Material
- [ ] Setoran
- [ ] tombol `?`

Exit criteria:

- nilai dari wizard dapat dibuka kembali secara identik di Settings.

---

## 11.17 — Validasi perubahan Settings untuk existing project

Status: [ ] NOT STARTED  
Depends on: 11.16

Tujuan: strict New Project tidak membuat existing project rapuh saat drive eksternal offline.

Rules:

- [ ] konfigurasi baru yang invalid → block Save;
- [ ] existing external folder sementara unavailable → warning yang jelas;
- [ ] existing project tetap dapat dibuka;
- [ ] URL optional tidak memblokir Save;
- [ ] changing source setting invalidates source-dependent workspace;
- [ ] changing audio/output path invalidates Tracking/Delivery filesystem state.

Exit criteria:

- existing workflows tetap usable ketika external drive sementara unavailable.

---

## 11.18 — Regression Project Lifecycle

Status: [ ] NOT STARTED  
Depends on: 11.04, 11.13, 11.16

Harus tetap hijau:

- [ ] New Project
- [ ] Open Project
- [ ] Save
- [ ] Save As
- [ ] Duplicate
- [ ] Recover
- [ ] Recent Projects
- [ ] Close/Reopen
- [ ] `.smproj` file association
- [ ] old filename project seperti `AA23.smproj`
- [ ] project identity tetap stabil
- [ ] tidak ada auto rename existing project

Exit criteria:

- lifecycle existing tidak berubah kecuali flow New Project yang memang dirancang ulang.

---

## 11.19 — Regression Source Sync

Status: [ ] NOT STARTED  
Depends on: 11.08, 11.14, 11.15

Test scenario:

- [ ] initial sync normal;
- [ ] source tanpa perubahan;
- [ ] corrupt workbook;
- [ ] duplicate episode;
- [ ] delimiter salah;
- [ ] source berubah setelah preflight;
- [ ] cancel preflight;
- [ ] cancel wizard;
- [ ] failure setelah `.smproj` dibuat;
- [ ] source revision setelah project berjalan;
- [ ] F5 existing masih sama;
- [ ] Source Refresh Preview existing masih aman;
- [ ] lineage/recording history existing tidak rusak.

Exit criteria:

- wizard memakai pipeline production tanpa fork behavior.

---

## 11.20 — Regression Filesystem & Drive

Status: [ ] NOT STARTED  
Depends on: 11.09–11.11, 11.17

Scenario:

- [ ] local folder;
- [ ] Google Drive Desktop folder;
- [ ] path dengan spasi;
- [ ] Unicode path;
- [ ] mapped/network drive;
- [ ] read-only folder;
- [ ] missing folder;
- [ ] temporary unavailable folder;
- [ ] Stem == Setoran → warning/rule ditentukan;
- [ ] Source == Output → error atau strong warning;
- [ ] URL browser dimasukkan ke Folder → ditolak dengan pesan jelas;
- [ ] folder filesystem dimasukkan ke URL → warning bila perlu.

Exit criteria:

- tidak ada path ambiguity yang dapat merusak source/output workflow.

---

## 11.21 — Regression UI & Accessibility

Status: [ ] NOT STARTED  
Depends on: 11.05–11.12, 11.16

Scenario:

- [ ] 1920×1080;
- [ ] 1366×768;
- [ ] Windows scaling 100%;
- [ ] 125%;
- [ ] 150%;
- [ ] keyboard Tab order;
- [ ] Back/Next menjaga state;
- [ ] Enter tidak trigger Create sebelum final;
- [ ] Escape/Cancel aman;
- [ ] long project/path labels tidak merusak layout;
- [ ] error list scrollable;
- [ ] focus pindah ke field bermasalah;
- [ ] help `?` keyboard reachable;
- [ ] milestone state dapat dibaca tanpa hanya bergantung warna.

Exit criteria:

- wizard usable pada target desktop utama.

---

## 11.22 — Contract test reusable form & settings roundtrip

Status: [ ] NOT STARTED  
Depends on: 11.03, 11.16

Test contract:

```text
New Project inputs
→ ProjectSettings
→ create .smproj
→ reopen .smproj
→ Project Settings
→ values identik
```

Pekerjaan:

- [ ] field parity test;
- [ ] default parity test;
- [ ] normalization parity test;
- [ ] folder parity test;
- [ ] audio settings parity test;
- [ ] URL parity test;
- [ ] delimiter parity test;
- [ ] project metadata parity test.

Exit criteria:

- New Project dan Project Settings tidak dapat drift tanpa test gagal.

---

## 11.23 — UAT bertahap sebelum final merge

Status: [ ] NOT STARTED  
Depends on: seluruh implementation tasks sebelum final acceptance

UAT dibagi, jangan langsung final sekaligus:

### UAT A — Wizard shell + Milestone 1

- [ ] rail milestone
- [ ] navigation
- [ ] project identity
- [ ] filename preview

### UAT B — Sumber Naskah

- [ ] source browser
- [ ] filename scan
- [ ] delimiter
- [ ] preflight

### UAT C — Audio + Folder & Tautan

- [ ] Stem
- [ ] Setoran
- [ ] audio spec
- [ ] links
- [ ] help `?`

### UAT D — Final Review + Transactional Create

- [ ] summary
- [ ] blockers
- [ ] failure rollback

### UAT E — Initial Sync + Project Settings

- [ ] automatic initial sync
- [ ] populated dashboard
- [ ] settings tabs
- [ ] existing project compatibility

Exit criteria:

- setiap UAT diterima sebelum melanjutkan ke final merge.

---

## 11.24 — Final Acceptance & Phase Close

Status: [ ] NOT STARTED  
Depends on: 11.01–11.23

Phase dianggap selesai hanya bila seluruh poin berikut benar:

- [ ] user tidak dapat membuat proyek tanpa konfigurasi operasional minimum;
- [ ] filename project baru = `KODE - NAMA PROYEK.smproj`;
- [ ] tidak ada overwrite destination;
- [ ] seluruh source filename berhasil diterjemahkan ke episode;
- [ ] source workbook lolos preflight;
- [ ] folder produksi valid;
- [ ] URL optional tidak memblokir workflow;
- [ ] semua nilai wizard tersedia kembali di Pengaturan Proyek;
- [ ] project creation atomic;
- [ ] failure tidak meninggalkan project setengah jadi;
- [ ] initial source sync otomatis selesai;
- [ ] dashboard pertama sudah berisi data;
- [ ] F5 / Sinkronkan Sumber existing tetap berfungsi;
- [ ] project lama tetap kompatibel;
- [ ] Save As / Duplicate / Recover tetap kompatibel;
- [ ] Tracking / Delivery invalidation tetap benar;
- [ ] test reguler hijau;
- [ ] Qt runtime hijau;
- [ ] Windows UAT hijau;
- [ ] tidak ada packaging EXE dalam phase ini.

Setelah seluruh checkbox di atas selesai, ubah status dokumen menjadi:

```text
Status: COMPLETE / FROZEN
```

---

# Dependency Map Ringkas

```text
11.01 Baseline
  ↓
11.02 Settings contract
  ↓
11.03 Reusable sections ───────┐
11.04 Filename formatter       │
  ↓                            │
11.05 Wizard shell             │
  ↓                            │
11.06 Identity                 │
11.07 Source filename          │
  ↓                            │
11.08 Source preflight         │
11.09 Audio                    │
11.10 Folder & links           │
11.11 Context help             │
  └────────────┬───────────────┘
               ↓
11.12 Final review
  ↓
11.13 Transactional create
  ↓
11.14 Initial sync
  ↓
11.15 Preflight/fingerprint safety
  ↓
11.16 Settings tabs alignment
  ↓
11.17 Existing project validation rules
  ↓
11.18–11.22 Regression contracts
  ↓
11.23 UAT
  ↓
11.24 Phase close
```

---

# Zona Berisiko Tinggi — Jangan Diubah Tanpa Test

## `ProjectManager.create()`

Risiko:

- project file naming;
- project ID;
- cleanup failure;
- project identity;
- runtime directory;
- recent project interaction.

Rule:

> Perubahan harus disertai project lifecycle regression test.

## Source Sync Pipeline

Risiko:

- dialogue lineage;
- source revision;
- inactive/history rows;
- cast resolution;
- recording state;
- audit;
- source fingerprint safety.

Rule:

> Wizard harus reuse pipeline production, bukan membuat import pipeline kedua.

## Tracking / Delivery invalidation

Risiko:

- perubahan output folder;
- Stem status;
- Delivered status;
- filesystem inventory cache;
- Revision workflow.

Rule:

> Perubahan Project Settings harus mempertahankan invalidation semantics existing.

---

# Non-Goals Phase 11

Jangan dikerjakan pada phase ini kecuali menjadi blocker langsung:

- packaging/build EXE;
- redesign workspace Project;
- redesign workspace Script/Dialog/Tracking/Delivery;
- reporting/dashboard baru;
- cloud API Google Drive;
- upload/download file melalui Google Drive API;
- autentikasi user;
- perubahan format `.smproj` besar yang tidak diperlukan;
- redesign visual Help global.

---

# Decision Log

Gunakan bagian ini untuk mencatat keputusan yang muncul selama implementasi supaya saat phase dilanjutkan tidak perlu membaca ulang seluruh chat.

## D-001 — Wizard Milestone

Status: LOCKED

Proyek Baru menggunakan lima milestone:

1. Inisialisasi Proyek
2. Sumber Naskah
3. Sumber Audio
4. Folder & Tautan
5. Buat Proyek

## D-002 — Project Settings

Status: LOCKED

Pengaturan Proyek **tidak** menggunakan milestone. Tetap menggunakan tab dan memakai reusable sections yang sama dengan wizard.

## D-003 — Filename project baru

Status: LOCKED

Format:

```text
KODE PROYEK - NAMA PROYEK.smproj
```

Tidak ada rename otomatis untuk project existing.

## D-004 — Source readiness

Status: LOCKED

Folder source + delimiter + filename validation + workbook preflight adalah blocker sebelum Create.

## D-005 — Initial Sync

Status: LOCKED

Setelah `.smproj` dibuat, initial source sync berjalan otomatis sebelum project dianggap selesai dibuat.

## D-006 — Drive URLs

Status: LOCKED

Drive URLs opsional; filesystem paths adalah konfigurasi operasional wajib.

## D-007 — Google Drive Desktop

Status: LOCKED

Aplikasi membaca Google Drive Desktop sebagai filesystem biasa. Browser URL hanya shortcut/link dan tidak dipakai membaca file.

## D-008 — Packaging

Status: LOCKED

Tidak melakukan packaging EXE pada Phase 11.

## D-009 — Destination project baru bersifat transient

Status: LOCKED

Folder tujuan `.smproj` baru adalah state wizard dan tidak ditambahkan ke schema persistent. `project_folder` tetap runtime/read-only dan menunjuk file `.smproj` yang sudah dibuat.

## D-010 — Strict validation berada di wizard

Status: LOCKED

Wizard Proyek Baru menerapkan blocker lengkap Phase 11. `ProjectManager.create()` tetap kompatibel untuk caller programatik/test lama, tetapi semua caller memakai formatter filename resmi yang sama dan manager tetap menolak overwrite destination.

## D-011 — Folder destination hanya dibuat secara eksplisit

Status: LOCKED

Mengetik path destination yang belum ada tidak membuat direktori atau file. Wizard menampilkan blocker dan tombol `Buat Folder`; direktori baru dibuat hanya setelah aksi eksplisit user. Probe writability selalu membersihkan file sementara.

## D-012 — Extension workbook bukan pola filename

Status: LOCKED

Milestone 2 membandingkan pola berdasarkan stem filename. `.xlsx` dan `.xlsm` sama-sama format workbook yang didukung dan tidak memecah satu konvensi nama menjadi dua pola. Filename validation hanya membaca filesystem metadata/nama file; isi workbook dan fingerprint tetap menjadi scope 11.08/11.15.

## D-013 — Preflight memakai parser produksi tanpa database

Status: LOCKED

Preflight wizard menjalankan `WorkbookInspector` dan `ScriptParser` yang sama dengan source sync produksi, tetapi orchestration preflight tidak memakai `Project`, `Database`, diff, atau synchronizer. Workbook dibuka read-only, cancellation bersifat cooperative di antara file/stage, dan source milestone baru siap setelah filename validation serta preflight sama-sama lolos.

## D-014 — Folder audio dibuat eksplisit dan URL dipertahankan untuk validation

Status: LOCKED

Milestone Audio tidak membuat folder saat user mengetik path. Folder Stem/Setoran yang belum ada hanya dibuat lewat aksi `Buat Folder`. Normalization mempertahankan nilai yang mengandung skema URL agar dedicated filesystem validator dapat menolak browser URL dengan pesan yang benar sebelum nilai tersebut diperlakukan sebagai `Path`.

---

# Progress Log

Tambahkan entry setiap pekerjaan selesai atau ketika ada keputusan penting.

Format:

```text
YYYY-MM-DD — 11.xx
- perubahan:
- test:
- keputusan:
- commit/PR:
- next:
```

2026-09-06 — 11.01
- perubahan: baseline dikunci; branch `phase-11-new-project-setup` dibuat dari `86224ad777033b0668999799fab97674a8cf9bec`.
- test: baseline PR #73 `344 passed, 15 skipped`; Qt runtime success.
- keputusan: packaging tetap out of scope; zona risiko tinggi dikunci sesuai dokumen.
- commit/PR: baseline code `cc64a8c758693d0c1366a417068d37d839105568` / Phase doc merge `86224ad777033b0668999799fab97674a8cf9bec`.
- next: 11.02.

2026-09-06 — 11.02
- perubahan: kontrak field, audio constants, blocking/warning/optional, dan normalization dipusatkan pada `core/project_settings.py`; tidak ada schema baru.
- test: contract/normalization tests ikut full suite `356 passed, 16 skipped`.
- keputusan: destination project baru transient; `project_folder` tetap runtime-only.
- commit/PR: `cc7c589ba3e537fc14f785d83d361da3c91fa03e` / PR #75.
- next: 11.03.

2026-09-06 — 11.03
- perubahan: reusable `ProjectIdentitySection`, `SourceConfigurationSection`, `AudioOutputSection`, `DriveLinksSection`, `FolderField`, serta coordinator `ProjectConfigurationSections`; New Project dan Settings memakai section yang sama.
- test: widget roundtrip test + Qt runtime smoke success; full suite `356 passed, 16 skipped`.
- keputusan: source filename preview memakai `extract_episode_number()` produksi agar tidak drift.
- commit/PR: `cc7c589ba3e537fc14f785d83d361da3c91fa03e` / PR #75.
- next: 11.04.

2026-09-06 — 11.04
- perubahan: formatter resmi `KODE - NAMA.smproj`, Windows sanitization, whitespace cleanup, Unicode preservation, suffix guard, preview destination, dan collision detection; `ProjectManager.create()` memakai formatter yang sama.
- test: normal/Unicode/invalid chars/suffix/whitespace/collision/legacy open; full suite `356 passed, 16 skipped`; Qt runtime success.
- keputusan: metadata name/code tidak disanitasi; project existing tidak di-rename; Save As/Duplicate tetap target user.
- commit/PR: `cc7c589ba3e537fc14f785d83d361da3c91fa03e` / PR #75.
- next: 11.05 Wizard shell.

2026-09-06 — 11.05
- perubahan: wizard lima milestone, rail kiri, stacked page, bantuan `?`, Back/Next/Cancel, final `Buat Proyek`, generic validation gate, state preservation, serta runtime coverage ukuran/scaling.
- test: full regression sesudah shell `358 passed, 17 skipped`; kemudian gate terkini `364 passed, 22 skipped`; Qt runtime + Phase 11 wizard size/scale smoke success.
- keputusan: automated size/scale test adalah regression proxy; Windows DPI UAT nyata tetap wajib di 11.21/11.23.
- commit/PR: `3e731fdbb695d28d74741d59af6dbdf517a42c77`, `524ccae6f67f0a06ee29409cfb6318cf1aa17336`, `cf6475e35f326ed2d7201e18d80110a29a0e6280` / PR #75.
- next: 11.06.

2026-09-06 — 11.06
- perubahan: validator identity/destination terpisah; Nama/Kode/Klien/Tanggal wajib; filesystem-vs-URL validation; collision dan writable probe; tombol explicit `Buat Folder`; auto-code mengikuti Nama sampai Kode benar-benar diedit manual.
- test: full suite `364 passed, 22 skipped`; Qt runtime Phase 11 + existing runtime success; size 1920×1080/1366×768 dan scale 100/125/150 smoke success.
- keputusan: destination belum ada tidak dibuat saat typing; tidak ada `.smproj` selama wizard navigation/validation.
- commit/PR: `40b34b685ea6f74239000359abf64dc6ebf76c62`, `07a22b1934cd7b9c79c3d5ec994cf6966233aee6`, `cf6475e35f326ed2d7201e18d80110a29a0e6280` / PR #75.
- next: 11.07 Sumber Naskah.

2026-09-06 — 11.07
- perubahan: filename-only source gate; auto scan/debounce pada wizard; validasi seluruh `.xlsx/.xlsm`; mapping episode; count/pattern/representative preview; duplicate/multiple-pattern/extraction blocker; gap warning; milestone state terhubung ke navigation gate.
- test: full suite `372 passed, 24 skipped`; Qt runtime + Phase 11 source milestone + wizard scale smoke success.
- keputusan: extension workbook tidak termasuk pola naming; validator 11.07 tidak membuka workbook, tidak menghitung fingerprint, dan tidak menyentuh database.
- commit/PR: `7140b211ad2c132962376ecbe6ef2eadfdcb3552`, `7883f6309ba438e6b4c9b05a880c9816657240a7`, `e437829ae9faaa7eb87ca023b6e31b7b0de245e2` / PR #75.
- next: 11.08 Source Preflight read-only.

2026-09-06 — 11.08
- perubahan: service preflight read-only memakai inspector/parser produksi; UI progress + cancel + summary + detail error per file; source milestone menggabungkan filename gate dan preflight gate; corrupt workbook/parse failure menjadi blocker.
- test: full suite `377 passed, 27 skipped`; compile success; Qt runtime dan Phase 11 wizard scale smoke success.
- keputusan: preflight tidak memakai Project/Database/diff/synchronizer; cancellation cooperative; initial-sync reuse/fingerprint safety tetap scope 11.14/11.15.
- commit/PR: `84b788d85be4fd9a0fc7ac814803b42ad30e681f`, `5d18124ef2bcda517d06f17554096288890a550c` / PR #75.
- next: 11.09 Milestone 3 — Sumber Audio.

2026-09-06 — 11.09
- perubahan: validator folder audio strict untuk New Project; panel status Stem/Setoran; explicit create folder; read/write check + cleanup probe; supported WAV/sample-rate/bit-depth/channel gate; milestone 3 terhubung ke navigation/final create.
- test: full suite `382 passed, 29 skipped`; compile success; Qt runtime + wizard scale smoke success.
- keputusan: browser URL pada Folder dipertahankan selama normalization agar dapat ditolak validator secara eksplisit; folder tidak pernah dibuat hanya karena typing.
- commit/PR: `31257ed92597b33ff2639e81273308bcc2214780`, `efb1f3de732d18a9a9c0b236959419446a020928`, `050600eec8a94eee517f83969d996e1d3ebda4e0`, `f0704b9cd42ace9bee4b9188dd8a837125454871`, `27b2b0c368261369d07a6f5da31b5bec7f19ce51`, `04165ead02f2caeb12f168e13c04177e81e0bcca`, `609de7a9a3536ff2449d238eb8fe6518137d3243`, `8439b227cc38de7ae170f36f5a1944c9695f9cc0` / PR #75.
- next: 11.10 Milestone 4 — Folder & Tautan.

---

# Resume Protocol

Jika pekerjaan dilanjutkan pada chat/session baru:

1. baca file ini terlebih dahulu;
2. baca `PROJECT_STATUS.md` bila perlu untuk konteks aplikasi secara keseluruhan;
3. cek `main` terbaru;
4. cari pekerjaan **pertama** dengan status `[ ] NOT STARTED` atau pekerjaan yang ditandai `IN PROGRESS`;
5. baca dependency pekerjaan tersebut;
6. jangan mulai pekerjaan setelahnya sebelum exit criteria pekerjaan aktif terpenuhi;
7. setelah implementasi, update checklist/status dan Progress Log pada file ini;
8. jalankan targeted test + CI sesuai risiko perubahan;
9. jangan packaging EXE.

**Phase 11 source of truth = file ini.**
