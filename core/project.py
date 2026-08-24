from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.database import Database
from core.project_settings import ProjectSettings


PROJECT_FILE_NAME = "project.json"
DATABASE_FILE_NAME = "project.db"


@dataclass
class Project:
    root: Path
    settings: ProjectSettings
    created_at: str = ""
    updated_at: str = ""

    @property
    def project_file(self) -> Path:
        return self.root / PROJECT_FILE_NAME

    @property
    def database_file(self) -> Path:
        return self.root / DATABASE_FILE_NAME

    @property
    def backups_folder(self) -> Path:
        return self.root / "backups"

    @property
    def logs_folder(self) -> Path:
        return self.root / "logs"

    @property
    def database(self) -> Database:
        return Database(self.database_file)

    def ensure_structure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.backups_folder.mkdir(exist_ok=True)
        self.logs_folder.mkdir(exist_ok=True)

    def save(self) -> None:
        self.ensure_structure()

        now = datetime.now().isoformat(timespec="seconds")
        if not self.created_at:
            self.created_at = now
        self.updated_at = now

        self.settings.project_folder = str(self.root)

        payload: dict[str, Any] = {
            "format_version": 1,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "settings": self.settings.to_dict(),
        }

        temp_file = self.project_file.with_suffix(".json.tmp")

        temp_file.write_text(
            json.dumps(payload, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )
        temp_file.replace(self.project_file)

    @classmethod
    def load(cls, project_file: str | Path) -> "Project":
        path = Path(project_file)

        if path.is_dir():
            path = path / PROJECT_FILE_NAME

        if not path.exists():
            raise FileNotFoundError(f"Project file not found: {path}")

        payload = json.loads(path.read_text(encoding="utf-8"))

        settings = ProjectSettings.from_dict(payload.get("settings", {}))
        settings.project_folder = str(path.parent)

        project = cls(
            root=path.parent,
            settings=settings,
            created_at=str(payload.get("created_at", "")),
            updated_at=str(payload.get("updated_at", "")),
        )

        return project
