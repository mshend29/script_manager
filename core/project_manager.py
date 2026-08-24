from __future__ import annotations

import shutil
from pathlib import Path

from core.database import DatabaseCompatibilityError
from core.project import DATABASE_FILE_NAME, PROJECT_FILE_NAME, Project
from core.project_settings import ProjectSettings


class ProjectError(RuntimeError):
    pass


class ProjectManager:
    def __init__(self):
        self.current: Project | None = None

    @property
    def is_open(self) -> bool:
        return self.current is not None

    def create(
        self,
        settings: ProjectSettings,
        parent_folder: str | Path,
    ) -> Project:
        normalized = settings.normalized()

        project_name = normalized.project_name.strip()
        if not project_name:
            raise ProjectError("Project Name wajib diisi.")

        parent = Path(parent_folder).expanduser()
        parent.mkdir(parents=True, exist_ok=True)

        folder_name = self._safe_folder_name(
            normalized.project_code or project_name
        )

        project_root = parent / folder_name

        if project_root.exists() and any(project_root.iterdir()):
            raise ProjectError(
                f"Folder project sudah ada dan tidak kosong:\n{project_root}"
            )

        project_root.mkdir(parents=True, exist_ok=True)

        normalized.project_folder = str(project_root)

        project = Project(
            root=project_root,
            settings=normalized,
        )

        try:
            project.ensure_structure()
            project.database.initialize()
            project.save()
        except Exception:
            # Jika create gagal di tengah jalan, hapus folder hanya jika
            # folder tersebut baru dan aman untuk dibersihkan.
            try:
                if project_root.exists():
                    shutil.rmtree(project_root)
            except Exception:
                pass
            raise

        self.current = project
        return project

    def open(self, path: str | Path) -> Project:
        project = Project.load(path)

        try:
            if not project.database_file.exists():
                # Project lama / database hilang: buat struktur database kosong.
                project.database.initialize()
            else:
                # Tetap jalankan initialize untuk migration-safe CREATE IF NOT EXISTS.
                project.database.initialize()
        except DatabaseCompatibilityError as exc:
            raise ProjectError(str(exc)) from exc

        project.ensure_structure()
        self.current = project
        return project

    def save(self) -> None:
        self._require_project().save()

    def update_settings(self, settings: ProjectSettings) -> None:
        project = self._require_project()

        normalized = settings.normalized()
        normalized.project_folder = str(project.root)

        project.settings = normalized
        project.save()

    def close(self) -> None:
        if self.current is not None:
            self.current.save()
        self.current = None

    def get_dashboard_counts(self) -> dict[str, int]:
        project = self._require_project()
        return project.database.get_counts()

    def _require_project(self) -> Project:
        if self.current is None:
            raise ProjectError("Tidak ada project yang sedang dibuka.")
        return self.current

    @staticmethod
    def _safe_folder_name(value: str) -> str:
        cleaned = "".join(
            char if char.isalnum() or char in (" ", "-", "_") else "_"
            for char in value.strip()
        )
        cleaned = cleaned.strip(" .")
        return cleaned or "Project"
