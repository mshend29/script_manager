# Script Manager

Aplikasi desktop untuk manajemen naskah drama pendek vertikal, recording dialogue, character/talent resolution, tracking stem, dan delivery.

## Requirement

- Python 3.13
- PySide6
- SQLite (tersedia di Python standard library)

## Menjalankan

PowerShell:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Project `.smproj` juga dapat diberikan sebagai argumen:

```powershell
python main.py "D:\Projects\AA23.smproj"
```

## Project Format

Script Manager menggunakan satu file project:

```text
AA23.smproj
```

`.smproj` adalah SQLite database yang menyimpan data dan konfigurasi project. File source atau output tidak di-embed ke dalam project.

Data yang berada di dalam `.smproj` meliputi antara lain:

- Project Settings
- source file metadata dan fingerprint
- episodes dan dialogues
- characters dan talents
- character/talent mapping
- dialog cast
- recording status
- stem/tracking status
- validation dan audit history
- internal format/schema metadata

Referensi eksternal meliputi:

- Source Script Folder
- source Excel `.xlsx` / `.xlsm`
- Stem / Mixdown / Export Folder
- Setoran Folder
- Main Drive / Material / Delivery URL

## Project Lifecycle

PROJECT menyediakan:

- New Project
- Open Project
- Open Recent
- Save
- Save As
- Duplicate Project
- Recover Project
- Project Settings
- Close Project

Aturan identitas project:

- **Save As** mempertahankan `project_id`.
- **Duplicate Project** membuat `project_id` baru.
- **Recover Project** membuat file recovery baru dari snapshot backup.

Backup project disimpan sebagai `.smproj` di application data per-user, bukan di folder tempat project berada. Logs juga disimpan di application data.

## Source Import / Refresh

Alur source:

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
```

Refresh hanya memproses file yang New / Changed / Restored. Data aplikasi seperti recording status dan downstream tracking dipertahankan sesuai aturan sinkronisasi.

## Workspace

Ribbon utama:

- PROJECT
- SCRIPT
- DIALOG
- TRACKING
- DATA
- TOOLS
- HELP

Fitur yang sudah tersedia mencakup project dashboard, source import/refresh, script/dialog views, recording checkbox persistence, character/talent mapping, validation, tracking, backup/restore, diagnostics, dan audit history.

## Help

Tab HELP menyediakan:

- Getting Started
- User Guide
- Keyboard Shortcuts
- Check for Updates
- Report a Problem
- About Script Manager

Dokumentasi utama tersedia offline. Check for Updates memeriksa GitHub Releases secara manual dan tidak mengunduh atau memasang update otomatis. Report a Problem hanya menyiapkan template GitHub Issue beserta environment teknis dasar; data project, client, source path, Drive URL, dialogue text, dan isi naskah tidak dimasukkan otomatis.

## Windows File Association

Fondasi association `.smproj` sudah tersedia di kode melalui spesifikasi:

```text
Extension : .smproj
Prog ID   : ScriptManager.Project
File Type : Script Management Project
Open      : ScriptManager.exe "%1"
```

Registrasi ke Windows belum dilakukan otomatis dari aplikasi. Association akan dipasang melalui installer saat packaging aplikasi sudah dibuat.
