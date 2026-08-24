# Script Manager

Fondasi baru aplikasi manajemen naskah dengan UI ribbon ala Excel.

## Requirement

- Python 3.13
- PySide6
- SQLite sudah termasuk di Python standard library

## Menjalankan

PowerShell:

```powershell
cd script_manager_starter
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

## Tahap yang sudah aktif

### Application Shell

- Ribbon PROJECT
- SCRIPT
- DIALOG
- TRACKING
- DATA
- TOOLS
- Context sidebar berbeda per halaman
- Workspace
- Status bar

### Project System

Tombol berikut sudah berfungsi:

- New Project
- Open Project
- Save
- Project Settings
- Close
- Open Client Drive

New Project membuat:

```text
PROJECT_FOLDER/
├── project.json
├── project.db
├── backups/
└── logs/
```

### project.json

Menyimpan konfigurasi project:

- Project Name
- Project Code
- Client
- Start Date
- Project Location
- Source Folder
- delimiter sebelum nomor episode
- delimiter setelah nomor episode
- Main Drive URL
- Material Drive URL
- Delivery / Setoran URL

### project.db

SQLite schema awal:

- app_meta
- source_files
- episodes
- characters
- talents
- character_talent
- dialogues
- dialog_cast
- recording_status
- stem_status

Database ini sengaja memisahkan data source dari progress recording.

## Belum aktif

- Import Source
- Refresh Data
- Excel scanner/parser
- auto character/talent resolution
- data binding Script
- recording checkbox persistence
- Tracking calculation

Tahap berikutnya: **Import / Refresh Engine**.
