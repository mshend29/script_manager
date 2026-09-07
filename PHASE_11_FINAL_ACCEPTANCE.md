# Phase 11 — Final Acceptance

Status: **11.01–11.24 COMPLETE — READY TO MERGE**  
Branch: `phase-11-new-project-setup`  
PR: #75  
Packaging EXE: **OUT OF SCOPE / tidak disentuh**.

---

## 11.23 — Staged UAT

Status: [x] COMPLETE

UAT dilakukan pada environment Windows operator setelah seluruh implementation/regression gate 11.01–11.22 selesai.

### UAT A — Wizard shell + Milestone 1

Status: [x] ACCEPTED

- rail 5 milestone dan navigasi Back/Next aman;
- identity/destination/preview filename bekerja;
- auto-code berhenti menimpa kode setelah edit manual;
- destination/collision/create-folder behavior diterima;
- tidak ada `.smproj` dibuat hanya karena navigation/validation.

### UAT B — Sumber Naskah & Preflight

Status: [x] ACCEPTED

- scan `.xlsx/.xlsm`, delimiter, preview episode, dan Source Preflight diterima;
- stale-preflight/source safety diterima;
- blocker/warning source terbaca dengan benar;
- temuan UAT: variasi kapitalisasi filename seperti `Episode 1`, `episode 2`, `EPISODE 3` semula dianggap pola berbeda dan memblokir preflight;
- perbaikan: filename pattern comparison dan episode delimiter extraction dibuat case-insensitive, sementara nama file asli tetap dipertahankan untuk preview/error;
- pola yang benar-benar berbeda seperti `Episode` vs `Chapter` tetap dianggap berbeda/blocking;
- regression setelah fix: `430 passed, 57 skipped`, Qt runtime success, scale smoke success.

### UAT C — Audio + Folder & Tautan

Status: [x] ACCEPTED

- Folder Stem/Setoran, WAV settings, filesystem-vs-URL separation, folder relationship policy, dan help `?` diterima.

### UAT D — Final Review + Transactional Create

Status: [x] ACCEPTED

- Review/Ubah/Create gate diterima;
- automatic Initial Source Sync diterima;
- transactional rollback/failure recovery diterima;
- input wizard tetap tersedia untuk retry setelah failure.

### UAT E — Existing Project / Settings / Lifecycle

Status: [x] ACCEPTED

- Initial Source Sync otomatis sampai Dashboard diterima;
- Recent Project hanya setelah success diterima;
- Project Settings 4-tab diterima;
- New Project → reopen → Settings value parity diterima;
- `.smproj` read-only di Settings diterima;
- existing project/offline-drive compatibility diterima;
- F5 / Sinkronkan Sumber existing diterima.

---

## 11.24 — Final Acceptance

Status: [x] COMPLETE

Acceptance criteria:

- [x] seluruh pekerjaan 11.01–11.22 implementation/regression complete;
- [x] UAT A–E diterima operator Windows;
- [x] temuan UAT case-sensitive source filename diperbaiki dan diregression;
- [x] latest branch CI success;
- [x] Python compile success;
- [x] full suite latest code gate: `430 passed, 57 skipped`;
- [x] Qt runtime: success;
- [x] wizard scale smoke 100% / 125% / 150%: success;
- [x] PR #75 tetap mergeable;
- [x] packaging/EXE tetap tidak disentuh.

## Final decision

**Phase 11 diterima dan siap di-merge ke `main`.**

Merge tetap merupakan aksi eksplisit terpisah. PR #75 tidak di-merge oleh checkpoint ini.
