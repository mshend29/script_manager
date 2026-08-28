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
PROJECT_PACKAGE_EXTENSION = ".drsp"
PROJECT_PACKAGE_TYPE = "directory-package"
LEGACY_PROJECT_FORMAT_VERSION = 1
PROJECT_FORMAT_VERSION = 2
SUPPORTED_PROJECT_FORMAT_VERSIONS = {
    LEGACY_PROJECT_FORMAT_VERSION,
    PROJECT_FORMAT_VERSION,
}


class ProjectFormatError(ValueError):
    pass


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
    def is_package(self) -> bool:
        return self.root.name.casefold().endswith(
            PROJECT_PACKAGE_EXTENSION.casefold()
        )

    @property
    def package_name(self) -> str:
        return self.root.name

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
            "format_version": PROJECT_FORMAT_VERSION,
            "package_type": (
                PROJECT_PACKAGE_TYPE if self.is_package else "legacy-directory"
            ),
            "package_extension": (
                PROJECT_PACKAGE_EXTENSION if self.is_package else ""
            ),
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
        path = Path(project_file).expanduser()

        if (
            path.suffix.casefold() == PROJECT_PACKAGE_EXTENSION
            and path.exists()
            and not path.is_dir()
        ):
            raise ProjectFormatError(
                ".drsp harus berupa project package directory, bukan file."
            )

        if path.is_dir():
            path = path / PROJECT_FILE_NAME

        if path.name.casefold() != PROJECT_FILE_NAME.casefold():
            raise ProjectFormatError(
                "Pilih folder project .drsp / legacy project folder "
                f"atau file {PROJECT_FILE_NAME}: {path.name}"
            )

        if not path.exists():
            raise FileNotFoundError(f"Project file not found: {path}")

        if not path.is_file():
            raise ProjectFormatError(f"Project descriptor bukan file: {path}")

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProjectFormatError(
                f"Project descriptor bukan JSON yang valid: {exc}"
            ) from exc
        except (OSError, UnicodeError) as exc:
            raise ProjectFormatError(
                f"Project descriptor tidak dapat dibaca: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise ProjectFormatError("Project descriptor harus berupa JSON object.")

        format_version = payload.get("format_version")
        if (
            type(format_version) is not int
            or format_version not in SUPPORTED_PROJECT_FORMAT_VERSIONS
        ):
            supported = ", ".join(
                str(value)
                for value in sorted(SUPPORTED_PROJECT_FORMAT_VERSIONS)
            )
            raise ProjectFormatError(
                "Project format tidak didukung: "
                f"{format_version!r}; aplikasi mendukung {supported}."
            )

        settings_payload = payload.get("settings")
        if not isinstance(settings_payload, dict):
            raise ProjectFormatError("Project descriptor tidak memiliki object settings.")

        project_name = str(settings_payload.get("project_name", "") or "").strip()
        if not project_name:
            raise ProjectFormatError("Project descriptor tidak memiliki Project Name.")

        try:
            settings = ProjectSettings.from_dict(settings_payload)
        except (TypeError, ValueError) as exc:
            raise ProjectFormatError(
                f"Project settings tidak valid: {exc}"
            ) from exc

        settings.project_folder = str(path.parent)

        project = cls(
            root=path.parent,
            settings=settings,
            created_at=str(payload.get("created_at", "")),
            updated_at=str(payload.get("updated_at", "")),
        )

        return project
