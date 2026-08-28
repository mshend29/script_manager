from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from core.app_paths import project_runtime_root
from core.database import DatabaseCompatibilityError
from core.project import (
    PROJECT_FILE_EXTENSION,
    Project,
    ProjectFormatError,
)
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

        raw_name = normalized.project_code or project_name
        if raw_name.casefold().endswith(
            PROJECT_FILE_EXTENSION.casefold()
        ):
            raw_name = raw_name[:-len(PROJECT_FILE_EXTENSION)]

        file_stem = self._safe_file_stem(raw_name)
        project_file = parent / f"{file_stem}{PROJECT_FILE_EXTENSION}"

        if project_file.exists():
            raise ProjectError(
                f"Project file sudah ada:\n{project_file}"
            )

        project_id = str(uuid.uuid4())
        normalized.project_folder = str(project_file)

        project = Project(
            file_path=project_file,
            settings=normalized,
            project_id=project_id,
        )

        try:
            project.save()
        except Exception:
            for candidate in (
                project_file,
                Path(str(project_file) + "-journal"),
                Path(str(project_file) + "-wal"),
                Path(str(project_file) + "-shm"),
            ):
                try:
                    if candidate.exists():
                        candidate.unlink()
                except OSError:
                    pass

            try:
                runtime = project_runtime_root(project_id)
                if runtime.exists():
                    shutil.rmtree(runtime)
            except OSError:
                pass
            raise

        self.current = project
        return project

    def open(self, path: str | Path) -> Project:
        try:
            project = Project.load(path)
        except ProjectFormatError as exc:
            raise ProjectError(str(exc)) from exc

        try:
            # initialize() is migration-safe and rejects future schemas before
            # modifying the project file.
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
        normalized.project_folder = str(project.project_file)

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
    def _safe_file_stem(value: str) -> str:
        cleaned = "".join(
            char if char.isalnum() or char in (" ", "-", "_") else "_"
            for char in value.strip()
        )
        cleaned = cleaned.strip(" .")
        return cleaned or "Project"
