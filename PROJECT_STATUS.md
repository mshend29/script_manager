# Script Manager — Project Status & Engineering Roadmap

> Dokumen ini adalah **entry point teknis utama** ketika pengembangan Script Manager dilanjutkan.
>
> Sebelum mengubah kode:
>
> 1. Baca file ini.
> 2. Cek commit terbaru di branch `main`.
> 3. Bandingkan dengan **Last Reviewed Commit** di bawah.
> 4. Baca test dan implementasi terbaru untuk area yang akan diubah.
> 5. Kerjakan phase yang berstatus **CURRENT** terlebih dahulu. Jangan melompat ke phase berikutnya kecuali blocker tercatat di dokumen ini.
>
> Setiap perubahan arsitektur, workflow utama, schema, atau keputusan desain harus memperbarui file ini dalam commit / PR yang sama.

---

## 1. Project Snapshot

- Application: **Script Manager**
- Repository: `mshend29/script_manager`
- Main branch: `main`
- Application version saat audit: `0.1.0`
- Database schema saat audit: `9`
- Project format: satu file **`.smproj`** berbasis SQLite.
- Last Reviewed Date: **2026-09-02**
- Last Reviewed Commit:
  `ebdd920f887cfec3ee5f88af395bfc98a8ec834d`
- Commit title:
  `Merge pull request #51 from mshend29/feature/help-about`

Jika HEAD `main` sudah berbeda dari commit di atas, baca commit / PR setelah commit tersebut sebelum melanjutkan roadmap.

---

## 2. Product Goal

Script Manager adalah aplikasi desktop untuk workflow naskah drama pendek vertikal:

```text
Source Excel
    ↓
Scan / fingerprint
    ↓
Inspect workbook
    ↓
Parse
    ↓
Normalize
    ↓
Character / Talent resolution
    ↓
Validation
    ↓
Commit to .smproj
    ↓
Recording
    ↓
Tracking / Stem / Delivery
```

Target UX utama:

> Operator cukup melakukan **satu Source Sync** ketika client menambah atau merevisi source. Setelah Apply selesai, seluruh workspace membaca keadaan database terbaru tanpa perlu melakukan Refresh View berulang di tab lain.

---

## 3. Current Architecture

Area utama:

- `core/` — database, project lifecycle, project settings, application paths.
- `import_engine/` — source scan, workbook inspection, parsing, normalization, resolution, synchronization.
- `services/` — business logic untuk dialogue, recording, tracking, validation, backup, audit, diagnostics, dan lain-lain.
- `pages/` — workspace UI.
- `dialogs/` — modal / preview workflow.
- `app/main_window.py` — application orchestration dan ribbon action wiring.
- `tests/` — regression tests.

Current project model:

```text
Project.smproj
└── SQLite
    ├── Project Settings
    ├── Source metadata + fingerprints
    ├── Episodes + Dialogues
    ├── Character / Talent data
    ├── Cast mapping
    ├── Recording status
    ├── Tracking / Stem status
    ├── Validation / Review
    ├── Audit history
    └── Internal schema metadata
```

Source Excel, audio, stem, delivery, dan Drive tetap external references dan tidak di-embed ke `.smproj`.

---

# 4. CURRENT MILESTONE

## Source Refresh + Dialogue Identity Hardening

**Status: CURRENT**

Alasan milestone ini harus diselesaikan sebelum refactor UI besar atau packaging v1:

1. Source Refresh adalah pusat aliran data seluruh aplikasi.
2. Recording status dan Tracking harus aman terhadap revisi source.
3. Saat ini Preview dan Apply belum menggunakan reconciliation decision yang sama.
4. Current `dialog_uid` lebih menyerupai content signature daripada persistent identity.
5. Current Tracking invalidation masih berbasis perubahan fingerprint file, bukan perubahan semantic.
6. UX Refresh tersebar di beberapa tab sehingga operator tidak yakin apakah data sudah terbaru.

---

# 5. Audit Findings — Source Refresh

## Finding SR-01 — Refresh terminology bercampur

Current ribbon mempunyai dua jenis operasi dengan istilah mirip:

### Source synchronization

- PROJECT → Import Source
- PROJECT → Refresh Data
- DATA → Refresh Data
- F5 → Refresh Data

Operasi ini scan / inspect / parse / apply source Excel.

### Local view reload

- SCRIPT → Refresh View
- DIALOG → Refresh View
- TRACKING → Refresh View

Operasi ini hanya reload dari database yang sama.

### Problem

Operator harus memahami detail internal aplikasi untuk mengetahui tombol mana yang diperlukan.

### Target

Satu user-facing operation:

```text
Sync Source
```

Initial import dan incremental refresh menggunakan workflow yang sama.

---

## Finding SR-02 — Setelah Source Apply hanya current page yang direload

Current `MainWindow._source_sync_applied()` melakukan:

```text
refresh_project_page()
+
_refresh_current_data_page(project)
```

Halaman lain baru reload saat dibuka atau ketika Refresh View ditekan.

### Target

Setelah source commit:

```text
project_data_changed
```

menjadi satu application-level event.

- Current visible page → reload langsung.
- Page lain → ditandai dirty.
- Ketika page dirty dibuka → reload otomatis.
- User tidak perlu menekan Refresh View.

---

## Finding SR-03 — Tracking invalidation terlalu kasar

Current synchronizer mereset downstream status:

- READY_TO_STEM
- STEMMED
- DELIVERED

ketika **fingerprint source file berubah**.

Fingerprint berubah walaupun perubahan workbook hanya formatting / metadata Excel dan parsed dialogue sebenarnya identik.

### Target

Tracking invalidation harus berdasarkan **semantic source change**, bukan byte-level file change.

Contoh:

```text
Excel formatting only
→ no recording impact
→ no tracking impact

dialog added
→ affected cast scope needs new recording
→ affected tracking scope invalidated

dialog text changed
→ preserve recording history
→ mark source revision
→ invalidate affected tracking scope

cast changed
→ preserve history
→ invalidate old/new affected cast scope
```

Invalidasi idealnya scoped ke:

```text
Episode + Talent + Character
```

bukan seluruh episode jika tidak diperlukan.

---

# 6. Audit Findings — Dialogue Identity

## Finding DI-01 — Current dialog_uid adalah content-derived signature

Current `build_dialog_uid()` menggunakan:

```text
episode
+ characters
+ time_in
+ time_out
+ dialogue text
→ SHA-1
```

Nomor Excel row memang tidak dipakai, tetapi UID tetap berubah jika client mengubah:

- dialog text,
- character spelling,
- timecode,
- cast identity.

Jadi current UID bukan persistent identity.

---

## Finding DI-02 — Preview dan Apply dapat mengambil keputusan berbeda

`SourceChangeService` preview:

1. mencoba match berdasarkan `dialog_uid`,
2. jika UID berubah, mencoba fallback berdasarkan `source_row`,
3. dapat menampilkan row sebagai Text Changed / Cast Changed.

Tetapi `DialogueSynchronizer` Apply kembali hanya mencari:

```python
existing_by_uid.get(parsed_row.dialog_uid)
```

Jika UID berubah:

```text
old dialogue → inactive
new dialogue → INSERT
```

Akibatnya persistent `dialogue_id` dapat berubah.

Recording status lama memang masih tersimpan pada inactive dialogue, tetapi active dialogue baru mendapat recording status baru / unchecked.

### Risk

Recorded dialogue dapat terlihat seperti belum direkam setelah client melakukan revisi kecil.

### Priority

**P0 — correctness bug.**

---

## Finding DI-03 — Duplicate content dapat menghasilkan UID collision

Dua source row dengan kombinasi yang benar-benar sama:

- episode,
- character,
- time in,
- time out,
- dialogue text

akan menghasilkan UID yang sama.

Database mempunyai:

```text
dialogues.dialog_uid UNIQUE
```

Content signature tidak boleh menjadi satu-satunya persistent identity.

---

# 7. Locked Design Decisions

Keputusan berikut dianggap **LOCKED** sampai ada alasan kuat dan test yang membuktikan kebutuhan perubahan.

## LD-01 — .smproj tetap single-file SQLite

Jangan kembali ke pola:

```text
project.json + project.db
```

Project settings, operational data, audit, dan schema metadata tetap berada dalam satu `.smproj`.

## LD-02 — Source Excel bukan database utama

Excel adalah external source yang dapat di-refresh.

`.smproj` adalah operational state aplikasi.

## LD-03 — History tidak dihapus hanya karena source berubah

Missing / removed source dan dialogue dinonaktifkan bila diperlukan.

Recording / audit / historical state tidak dibuang diam-diam.

## LD-04 — Source Refresh harus previewable dan backup-safe

Workflow tetap:

```text
Prepare
↓
Read-only Preview
↓
User Apply
↓
Safety Backup
↓
Transactional Apply
↓
Audit
```

## LD-05 — Preview dan Apply harus menggunakan reconciliation plan yang sama

Tidak boleh ada dua algoritma matching independen.

## LD-06 — Recording history harus survive source revision

Perubahan source tidak boleh otomatis menghapus fakta bahwa sebuah line pernah direkam.

## LD-07 — Tracking invalidation harus semantic

File fingerprint dipakai untuk menentukan file perlu diparse atau tidak.

Fingerprint **tidak boleh menjadi satu-satunya alasan business status downstream direset**.

---

# 8. Ordered Work Plan

Kerjakan **berurutan**.

---

## PHASE 0 — Baseline Regression Safety

**Status: COMPLETE**

Tujuan: membuat bug / behavior yang akan diperbaiki terlihat jelas lewat test sebelum mengubah implementation.

### Tasks

- [x] P0.1 Tambah regression test: recorded dialogue + client mengubah dialog text.
- [x] P0.2 Tambah regression test: recorded dialogue + timecode berubah.
- [x] P0.3 Tambah regression test: character spelling berubah.
- [x] P0.4 Tambah regression test: row baru disisipkan di atas existing dialogue.
- [x] P0.5 Tambah regression test: row dipindahkan tetapi content sama.
- [x] P0.6 Tambah regression test: duplicate identical source rows tidak collision.
- [x] P0.7 Tambah regression test: source formatting/fingerprint berubah tetapi parsed semantics sama → tracking tidak reset.
- [x] P0.8 Catat current expected failures sebelum implementation.

### Baseline Result

Regression baseline dibuat di `tests/test_source_refresh_identity_regressions.py`.

Expected current failures yang dicatat sebagai `xfail(strict=True)`:

- recorded dialogue + text revision kehilangan lineage;
- recorded dialogue + timecode revision kehilangan lineage;
- character spelling revision kehilangan lineage;
- duplicate identical rows collision pada unique `dialog_uid`;
- formatting-only workbook change mereset downstream tracking karena fingerprint berubah.

Existing behavior yang diharapkan sudah lolos:

- insert row di atas existing dialogue mempertahankan lineage karena content-derived UID tidak memakai source row;
- move row dengan content sama mempertahankan lineage.

`xfail` marker harus dihapus satu per satu ketika phase implementation membuat scenario tersebut lulus.

### Exit Criteria

Semua scenario target mempunyai regression test yang jelas. Test untuk behavior lama yang salah boleh fail sampai Phase terkait selesai.

---

## PHASE 1 — Dialogue Reconciliation Model

**Status: COMPLETE**

Tujuan: memisahkan persistent identity dari source content signature.

### Target Model

Persistent identity:

```text
dialog_uid
```

dibuat sekali dan dipertahankan.

Mutable source identity / signature:

```text
source_signature
```

boleh berubah mengikuti source.

### Tasks

- [x] P1.1 Tentukan schema tambahan untuk source signature / reconciliation metadata.
- [x] P1.2 Tambah safe schema migration + pre-migration backup coverage.
- [x] P1.3 Buat reconciliation data model.
- [x] P1.4 Definisikan match levels, misalnya:
  - exact persistent/source match,
  - exact semantic match,
  - safe row continuity,
  - safe neighborhood / ordered match,
  - ambiguous,
  - new,
  - removed.
- [x] P1.5 Pastikan ambiguous match tidak ditebak diam-diam.
- [x] P1.6 Pastikan duplicate identical rows dapat memperoleh persistent identity berbeda.

### Exit Criteria

Dialogue yang sama secara lineage dapat dipertahankan walaupun mutable source content berubah.

---

## PHASE 2 — SourceChangePlan: Preview = Apply

**Status: COMPLETE**

Tujuan: reconciliation dilakukan satu kali.

### Target Flow

```text
Scan
↓
Inspect
↓
Parse
↓
Reconcile
↓
SourceChangePlan
├── Preview reads plan
└── Apply executes same plan
```

### Tasks

- [x] P2.1 Buat `SourceChangePlan` / equivalent immutable apply plan.
- [x] P2.2 Move dialogue matching keluar dari Preview-only logic.
- [x] P2.3 Preview hanya merender plan.
- [x] P2.4 Synchronizer hanya mengeksekusi approved plan.
- [x] P2.5 Tambah guard agar stale plan tidak diaplikasikan jika source/project berubah antara Prepare dan Apply.
- [x] P2.6 Audit details mengambil data dari plan yang sama.

### Exit Criteria

Preview dan committed result tidak dapat berbeda dalam keputusan identity / add / update / remove.

---

## PHASE 3 — Recording Revision Semantics

**Status: COMPLETE**

Tujuan: recording history dipertahankan tetapi source revision tetap terlihat.

### Proposed Direction

Tambahkan informasi seperti:

```text
dialogue.source_signature
recording_status.source_signature_at_recording
```

Jika berbeda:

```text
Recorded
+
Source Revised
```

bukan kehilangan checkbox dan bukan diam-diam dianggap selesai.

### Tasks

- [x] P3.1 Finalisasi status model source revision untuk recording.
- [x] P3.2 Simpan source signature saat line ditandai recorded.
- [x] P3.3 Deteksi stale recording setelah source revision.
- [x] P3.4 Tampilkan revision indicator di Dialog.
- [x] P3.5 Tentukan behavior Check All / Uncheck All terhadap revised lines.
- [x] P3.6 Pastikan old recording history tetap tersedia di audit / database.

### Exit Criteria

Recorded line yang direvisi client tetap memiliki lineage dan history, tetapi operator mendapat warning yang actionable.

---

## PHASE 4 — Semantic Tracking Invalidation

**Status: COMPLETE**

Tujuan: downstream tracking hanya direset jika semantic source change memang mempengaruhi scope tersebut.

### Tasks

- [x] P4.1 Hapus policy `fingerprint changed = reset entire episode downstream`.
- [x] P4.2 Derive affected Episode + Talent + Character dari SourceChangePlan.
- [x] P4.3 Dialog added → invalidate affected scope.
- [x] P4.4 Dialog removed → invalidate affected scope.
- [x] P4.5 Text/timecode revision → invalidate affected scope.
- [x] P4.6 Cast change → invalidate old + new affected scope.
- [x] P4.7 Formatting-only source change → no downstream invalidation.
- [x] P4.8 Preserve explicit REVISION semantics sesuai business rules.
- [x] P4.9 Tambah audit entry yang menjelaskan scope yang diinvalidasi dan alasannya.

### Exit Criteria

Tidak ada status STEMMED / DELIVERED yang reset hanya karena file Excel berubah secara non-semantic.

---

## PHASE 5 — Unified Application Data Change Notification

**Status: COMPLETE**

Tujuan: pengguna tidak perlu Refresh View manual.

### Target

Setelah successful Apply:

```text
project_data_changed(revision)
```

### Tasks

- [x] P5.1 Buat application-level project data revision / change event.
- [x] P5.2 Current page reload langsung.
- [x] P5.3 Hidden data pages ditandai dirty.
- [x] P5.4 Saat dirty page dibuka, reload otomatis.
- [x] P5.5 Preserve current filter / selected talent / character / episode jika masih valid.
- [x] P5.6 Project dashboard ikut reload.
- [x] P5.7 Tools / diagnostics hanya reload bila memang relevan; hindari expensive automatic work yang tidak diperlukan.

### Exit Criteria

Setelah Source Sync berhasil, berpindah SCRIPT / DIALOG / TRACKING / DATA selalu menampilkan data terbaru tanpa menekan Refresh View.

---

## PHASE 6 — Simplify Refresh UX / Ribbon

**Status: COMPLETE**

Tujuan: satu mental model untuk operator.

### Target User-facing action

```text
↻ Sync Source
```

### Tasks

- [x] P6.1 Satukan Import Source dan Refresh Data menjadi Sync Source.
- [x] P6.2 Initial sync dan incremental sync memakai tombol yang sama.
- [x] P6.3 F5 = Sync Source.
- [x] P6.4 Hapus SCRIPT → Refresh View sebagai required workflow.
- [x] P6.5 Hapus DIALOG → Refresh View sebagai required workflow.
- [x] P6.6 Hapus TRACKING → Refresh View sebagai required workflow.
- [x] P6.7 Hapus duplicate DATA → Refresh Data.
- [x] P6.8 Tentukan satu lokasi ribbon yang konsisten / global untuk Sync Source.
- [x] P6.9 Update Getting Started, User Guide, dan Keyboard Shortcuts.

### Exit Criteria

Operator hanya perlu memahami satu jenis source refresh.

---

## PHASE 7 — Qt Runtime CI Hardening

**Status: COMPLETE**

Current GitHub Actions lightweight environment hanya memasang `pytest` dan `openpyxl`. PySide6 runtime tests dapat skip ketika PySide6 tidak tersedia.

### Tasks

- [x] P7.1 Tambah CI job khusus Qt/PySide6.
- [x] P7.2 Gunakan offscreen platform untuk runtime smoke tests.
- [x] P7.3 Construct MainWindow dan semua major pages.
- [x] P7.4 Smoke-test project open → source sync mock → page reload.
- [x] P7.5 Pertahankan fast engine-only job jika diperlukan untuk feedback cepat.

### Exit Criteria

Critical Qt runtime behavior benar-benar diuji di CI, bukan hanya AST/source assertions.

---

## PHASE 8 — Architecture Refactor

**Status: COMPLETE**

Beberapa file sudah besar:

- `app/main_window.py`
- `pages/tracking_compact_page.py`
- `pages/data_page.py`
- sejumlah service / resolver.

Jangan melakukan refactor besar sebelum Source Refresh correctness mempunyai regression coverage kuat.

### Tasks

- [x] P8.1 Extract source sync orchestration dari MainWindow.
- [x] P8.2 Extract project lifecycle orchestration bila mengurangi coupling.
- [x] P8.3 Pisahkan large page workspace menjadi focused components/controllers.
- [x] P8.4 Jangan mengubah business behavior tanpa regression test.
- [x] P8.5 Hindari refactor kosmetik yang tidak mengurangi complexity nyata.

---

## PHASE 9 — v1 Release Readiness

**Status: IN PROGRESS**

### Areas

- [x] Windows packaging.
- [ ] Application icon / metadata.
- [x] `.smproj` file association via installer.
- [x] Upgrade / migration smoke test.
- [x] Backup / recovery disaster test.
- [x] Crash / diagnostics logging.
- [x] GitHub Release pipeline.
- [ ] Update checker against real release.
- [x] User acceptance workflow using representative project.
- [x] Final user guide review.
- [x] Version bump strategy toward `1.0.0`.

---

# 9. Required Regression Scenarios

Scenario berikut harus tetap ada sebagai long-term tests setelah implementation selesai.

## Dialogue identity

1. Unchanged dialogue keeps the same persistent identity.
2. Text-only revision preserves lineage.
3. Timecode-only revision preserves lineage when reconciliation is safe.
4. Source row insertion does not change existing dialogue lineage.
5. Source row movement does not automatically create a new dialogue.
6. Character spelling revision is surfaced correctly.
7. Talent revision preserves dialogue lineage when appropriate.
8. Duplicate identical source rows do not collide.
9. Ambiguous reconciliation does not silently guess.

## Recording

1. Recorded checkbox survives unchanged refresh.
2. Recorded history survives source revision.
3. Revised recorded line is visibly stale / needs attention.
4. Removed dialogue history remains stored.
5. Restored source can reactivate previous lineage when safe.

## Tracking

1. Formatting-only Excel change does not reset tracking.
2. New dialogue invalidates only affected tracking scope.
3. Removed dialogue invalidates affected scope.
4. Text revision invalidates affected scope.
5. Cast revision invalidates old/new affected scopes.
6. Unaffected talents / characters in same episode preserve downstream state.

## Source safety

1. Prepare is read-only.
2. Apply creates safety backup.
3. Duplicate episode detection blocks write.
4. Parser/inspection error blocks write.
5. Apply is transactional.
6. Audit records the actual approved change plan.

---

# 10. Working Rules

## WR-01 — GitHub main is source of truth

Jangan mengambil kode lama dari chat sebagai implementation terbaru.

Saat membahas file tertentu, baca file tersebut dari repository terbaru.

## WR-02 — Update this document

Perbarui `PROJECT_STATUS.md` jika terjadi salah satu hal berikut:

- phase selesai,
- phase baru dimulai,
- schema berubah,
- source sync algorithm berubah,
- persistent identity policy berubah,
- recording/tracking business rule berubah,
- major UI workflow berubah,
- release milestone berubah,
- blocker penting ditemukan.

## WR-03 — Complete one phase before jumping

Jangan memulai phase berikutnya hanya karena terlihat lebih mudah / menarik.

Pengecualian hanya untuk:

- blocker,
- critical regression,
- security/data-loss issue,
- prerequisite yang ternyata salah urutan.

Jika terjadi pengecualian, tulis alasannya di **Current Blockers / Deviations**.

## WR-04 — Tests before dangerous data migration

Untuk perubahan schema, identity, synchronization, recording, atau tracking:

```text
regression test
↓
implementation
↓
migration test
↓
full test suite
```

## WR-05 — Preserve operator data

Source-derived data boleh diperbarui.

Operator-created state seperti recording, manual mapping, review, tracking, dan audit tidak boleh dibuang tanpa explicit business rule.

## WR-06 — Keep source fingerprint technical

Fingerprint menentukan apakah file perlu diproses ulang.

Business consequences harus berdasarkan parsed / semantic diff.

---

# 11. Current Blockers / Deviations

Tidak ada blocker tercatat pada audit 2026-09-02.

Current next action:

```text
PHASE 9 — Windows packaging + release safety
```

Jangan mulai perubahan ribbon Refresh sebelum correctness Source Refresh dan persistent dialogue lineage selesai.

---

# 12. Resume Checklist

Jika project dibuka kembali setelah lama:

```text
1. Open PROJECT_STATUS.md
2. Fetch current main HEAD
3. Compare HEAD with Last Reviewed Commit
4. Read commits / merged PRs after Last Reviewed Commit
5. Check current APP_VERSION
6. Check current SCHEMA_VERSION
7. Run / inspect CI status
8. Identify CURRENT phase
9. Read implementation + tests for that phase
10. Continue only from first unchecked task unless blocker is documented
11. Update this file together with the change
```

---

# 13. Engineering Log

| Date | Commit / State | Note |
|---|---|---|
| 2026-09-02 | Branch `phase/source-refresh-hardening` | Phase 9 representative UAT: create project → Sync Source → record two cast scopes → auto-delivered tracking → revise one dialogue → preserve lineage/recording history → invalidate only affected tracking scope → accept re-record; engine + Qt runtime CI green. |
| 2026-09-02 | Branch `phase/source-refresh-hardening` | Phase 9 documentation review: README, Getting Started, and User Guide aligned to Sync Source, installer/portable distribution, file association, recovery, update, and current Help capabilities; regression suite green. |
| 2026-09-02 | Branch `phase/source-refresh-hardening` | Phase 9 installer: Inno Setup per-user installer builds successfully, silent install + frozen EXE + HKCU .smproj association smoke pass, and installer artifact uploads in Windows CI. |
| 2026-09-02 | Branch `phase/source-refresh-hardening` | Phase 9 release automation: tag-gated release workflow validates tag against APP_VERSION, rebuilds portable + installer, smoke-tests assets, generates SHA-256 checksums, and is documented in RELEASING.md; no release tag has been published yet. |
| 2026-09-02 | Branch `phase/source-refresh-hardening` | Phase 9 crash logging: rotating local application log + unhandled main/thread exception hooks added; startup metadata excludes project/source content; engine + Qt runtime CI green. |
| 2026-09-02 | Branch `phase/source-refresh-hardening` | Phase 9 Windows packaging: PyInstaller onedir build, frozen EXE smoke test, portable ZIP and Actions artifact upload pass on windows-latest. |
| 2026-09-02 | Branch `phase/source-refresh-hardening` | Phase 9 release safety: backup disaster recovery + schema v10→v11 migration smoke tests added and passing in engine CI. |
| 2026-09-02 | Branch `phase/source-refresh-hardening` | Phase 8 final verification complete: runtime monkey-patching removed, MainWindow imports AliasDataPage/CompactTrackingPage explicitly, alias-aware DATA validation stays behind DataWorkspaceController, and engine + production Qt runtime CI are green. |
| 2026-09-02 | Branch `phase/source-refresh-hardening` | Phase 8 previously reached green baseline: SourceSyncController owns async source lifecycle, existing ProjectManager retained as the correct lifecycle boundary, DATA domain service graph extracted into DataWorkspaceController. |
| 2026-09-02 | Branch `phase/source-refresh-hardening` | Phase 7 complete: dedicated PySide6/offscreen CI job added alongside fast engine job; Qt system libraries installed; MainWindow + major pages construct and project-open/source-commit/page-reload smoke flow passes in runtime CI. |
| 2026-09-02 | Branch `phase/source-refresh-hardening` | Phase 6 complete: ribbon/source UX unified to one Sync Source action, F5 routes to same command, redundant per-page refresh actions removed, Help updated, CI green. |
| 2026-09-02 | Branch `phase/source-refresh-hardening` | Phase 5 complete: project_data_changed revision signal + dirty-page lazy refresh keeps SCRIPT/DIALOG/TRACKING/DATA current without manual Refresh View; mutation events refresh sibling workspaces and dashboard; CI green. |
| 2026-09-02 | Branch `phase/source-refresh-hardening` | Phase 4 complete: Tracking invalidation is semantic and scoped to Episode + Talent + Character; formatting-only changes preserve downstream state; invalidation reasons are audited; CI green. |
| 2026-09-02 | Branch `phase/source-refresh-hardening` | Phase 3 complete: schema v11 records source signature at recording, revised recordings retain history and show Source Revised, bulk recording semantics tested, CI green. |
| 2026-09-02 | Branch `phase/source-refresh-hardening` | Phase 2 complete: immutable SourceChangePlan drives Preview + Apply, stale source/database guards added, dialogue lineage regressions promoted to required tests, CI green. |
| 2026-09-02 | Branch `phase/source-refresh-hardening` | Phase 1 complete: schema v10 adds source_signature, conservative reconciler added, migration ordering fixed, CI green. |
| 2026-09-02 | Branch `phase/source-refresh-hardening` | Phase 0 regression baseline added. Expected legacy failures recorded with strict xfail before reconciliation implementation. |
| 2026-09-02 | Reviewed main at `ebdd920f887cfec3ee5f88af395bfc98a8ec834d` | Source Refresh + Dialogue Identity audit started. Found refresh UX duplication, Preview/Apply identity mismatch, content-derived dialog UID risk, and fingerprint-based Tracking invalidation. Roadmap established. |

Add new rows above/below as development progresses. Keep entries concise; detailed implementation belongs in commit / PR history.
