from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path


APP_DATA_FOLDER = "Script Manager"


def app_data_root() -> Path:
    """Return the writable per-user application data directory."""
    if sys.platform == "win32":
        base = Path(
            os.environ.get("APPDATA")
            or (Path.home() / "AppData" / "Roaming")
        )
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        xdg = str(os.environ.get("XDG_DATA_HOME", "") or "").strip()
        base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"

    return base / APP_DATA_FOLDER


def project_runtime_root(project_id: str) -> Path:
    key = _safe_project_key(project_id)
    return app_data_root() / "Projects" / key


def project_backups_dir(project_id: str) -> Path:
    return project_runtime_root(project_id) / "Backups"


def project_logs_dir(project_id: str) -> Path:
    return project_runtime_root(project_id) / "Logs"


def database_backups_dir(
    database_path: str | Path,
    *,
    project_id: str = "",
) -> Path:
    project_key = str(project_id or "").strip()
    if project_key:
        return project_backups_dir(project_key)

    path = Path(database_path).expanduser()
    digest = hashlib.sha256(
        str(path.resolve(strict=False)).encode("utf-8")
    ).hexdigest()[:16]
    return app_data_root() / "Database Backups" / digest


def _safe_project_key(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "unknown-project"

    safe = "".join(
        char if char.isalnum() or char in ("-", "_") else "-"
        for char in raw
    ).strip("-_")
    return safe or "unknown-project"
