from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.app_paths import project_backups_dir, project_logs_dir
from core.database import Database, DatabaseCompatibilityError
from core.project_settings import ProjectSettings


PROJECT_FILE_EXTENSION = ".smproj"
PROJECT_FORMAT_ID = "SMPROJ"
PROJECT_FORMAT_NAME = "Script Management Project"
PROJECT_FORMAT_VERSION = 1
SUPPORTED_PROJECT_FORMAT_VERSIONS = {PROJECT_FORMAT_VERSION}


class ProjectFormatError(ValueError):
    pass


@dataclass
class Project:
    file_path: Path
    settings: ProjectSettings
    project_id: str
    created_at: str = ""
    updated_at: str = ""

    @property
    def project_file(self) -> Path:
        return self.file_path

    @property
    def root(self) -> Path:
        """Parent folder of the .smproj file.

        Kept as a compatibility convenience for UI/services that need the
        folder containing the project file. It is not a project package.
        """
        return self.file_path.parent

    @property
    def database_file(self) -> Path:
        return self.file_path

    @property
    def database(self) -> Database:
        return Database(self.file_path)

    @property
    def backups_folder(self) -> Path:
        return project_backups_dir(self.project_id)

    @property
    def logs_folder(self) -> Path:
        return project_logs_dir(self.project_id)

    @property
    def package_name(self) -> str:
        return self.file_path.name

    @property
    def is_smproj(self) -> bool:
        return (
            self.file_path.suffix.casefold()
            == PROJECT_FILE_EXTENSION.casefold()
        )

    def ensure_structure(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.backups_folder.mkdir(parents=True, exist_ok=True)
        self.logs_folder.mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        self.ensure_structure()
        self.database.initialize()

        now = datetime.now().isoformat(timespec="seconds")
        if not self.created_at:
            self.created_at = now
        self.updated_at = now

        # Runtime-only UI value; never persisted as a project setting.
        self.settings.project_folder = str(self.file_path)

        self.database.set_smproj_meta(
            {
                "format_id": PROJECT_FORMAT_ID,
                "format_name": PROJECT_FORMAT_NAME,
                "format_version": str(PROJECT_FORMAT_VERSION),
                "project_id": self.project_id,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }
        )
        self.database.save_project_settings(
            self.settings.to_persistent_dict()
        )

    @classmethod
    def load(cls, project_file: str | Path) -> "Project":
        path = Path(project_file).expanduser()

        if path.suffix.casefold() != PROJECT_FILE_EXTENSION.casefold():
            raise ProjectFormatError(
                "Pilih file Script Management Project (.smproj)."
            )

        if not path.exists():
            raise FileNotFoundError(f"Project file not found: {path}")

        if not path.is_file():
            raise ProjectFormatError(
                f"Project harus berupa satu file .smproj: {path}"
            )

        try:
            connection = sqlite3.connect(path)
            connection.row_factory = sqlite3.Row
            try:
                table = connection.execute(
                    """
                    SELECT 1
                    FROM sqlite_master
                    WHERE type = 'table' AND name = 'smproj_meta'
                    """
                ).fetchone()
                if table is None:
                    raise ProjectFormatError(
                        "File bukan Script Management Project yang valid."
                    )

                rows = connection.execute(
                    "SELECT key, value FROM smproj_meta"
                ).fetchall()
                meta = {
                    str(row["key"]): str(row["value"])
                    for row in rows
                }
            finally:
                connection.close()
        except ProjectFormatError:
            raise
        except sqlite3.DatabaseError as exc:
            raise ProjectFormatError(
                f"File .smproj tidak dapat dibaca sebagai SQLite database: {exc}"
            ) from exc

        if meta.get("format_id") != PROJECT_FORMAT_ID:
            raise ProjectFormatError(
                "File bukan Script Management Project yang valid."
            )

        raw_format_version = str(meta.get("format_version", "") or "").strip()
        try:
            format_version = int(raw_format_version)
        except ValueError as exc:
            raise ProjectFormatError(
                f"SMProj format_version tidak valid: {raw_format_version!r}."
            ) from exc

        if format_version not in SUPPORTED_PROJECT_FORMAT_VERSIONS:
            supported = ", ".join(
                str(value)
                for value in sorted(SUPPORTED_PROJECT_FORMAT_VERSIONS)
            )
            raise ProjectFormatError(
                "SMProj format tidak didukung: "
                f"{format_version}; aplikasi mendukung {supported}."
            )

        project_id = str(meta.get("project_id", "") or "").strip()
        if not project_id:
            raise ProjectFormatError(
                "SMProj tidak memiliki project_id."
            )

        database = Database(path)
        try:
            settings_payload = database.load_project_settings()
        except (sqlite3.DatabaseError, DatabaseCompatibilityError) as exc:
            raise ProjectFormatError(
                f"Project settings tidak dapat dibaca: {exc}"
            ) from exc

        project_name = str(
            settings_payload.get("project_name", "") or ""
        ).strip()
        if not project_name:
            raise ProjectFormatError(
                "SMProj tidak memiliki Project Name."
            )

        try:
            settings = ProjectSettings.from_dict(
                settings_payload
            ).normalized()
        except (TypeError, ValueError) as exc:
            raise ProjectFormatError(
                f"Project settings tidak valid: {exc}"
            ) from exc

        settings.project_folder = str(path)

        return cls(
            file_path=path,
            settings=settings,
            project_id=project_id,
            created_at=str(meta.get("created_at", "") or ""),
            updated_at=str(meta.get("updated_at", "") or ""),
        )
