from __future__ import annotations

import shutil
import sqlite3
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

    def save_as(self, target_file: str | Path) -> Project:
        project = self._require_project()
        project.save()

        target = self._normalize_target_file(target_file)
        if target == project.project_file.resolve(strict=False):
            project.save()
            return project

        if target.exists():
            raise ProjectError(
                f"Target project file sudah ada:\n{target}"
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        self._copy_database(project.project_file, target)

        saved = Project.load(target)
        saved.save()
        self.current = saved
        return saved

    def duplicate(
        self,
        target_file: str | Path,
    ) -> Project:
        source = self._require_project()
        source.save()

        target = self._normalize_target_file(target_file)
        if target.exists():
            raise ProjectError(
                f"Target project file sudah ada:\n{target}"
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        self._copy_database(source.project_file, target)

        duplicate = Project.load(target)
        duplicate.project_id = str(uuid.uuid4())
        duplicate.created_at = ""
        duplicate.updated_at = ""
        duplicate.settings.project_folder = str(target)
        duplicate.save()

        try:
            from services.audit_service import AuditService

            AuditService(duplicate.database).record(
                event_type="PROJECT",
                action="DUPLICATE_PROJECT",
                entity_type="project",
                summary=(
                    f"Project duplicated from {source.project_file.name}."
                ),
                details={
                    "source_project_id": source.project_id,
                    "source_file": str(source.project_file),
                    "target_file": str(target),
                },
            )
        except Exception:
            pass

        self.current = duplicate
        return duplicate

    def recover_from_backup(
        self,
        backup_file: str | Path,
        target_file: str | Path,
    ) -> Project:
        backup = Path(backup_file).expanduser().resolve(strict=False)
        if not backup.is_file():
            raise ProjectError(
                f"Backup file tidak ditemukan:\n{backup}"
            )

        try:
            Project.load(backup)
        except (ProjectFormatError, FileNotFoundError) as exc:
            raise ProjectError(
                f"Backup bukan .smproj yang valid: {exc}"
            ) from exc

        target = self._normalize_target_file(target_file)
        if target.exists():
            raise ProjectError(
                f"Target recovery sudah ada:\n{target}"
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        self._copy_database(backup, target)

        try:
            recovered = self.open(target)
        except Exception:
            try:
                target.unlink()
            except OSError:
                pass
            raise

        try:
            from services.audit_service import AuditService

            AuditService(recovered.database).record(
                event_type="PROJECT",
                action="RECOVER_PROJECT",
                entity_type="project",
                summary=f"Project recovered from {backup.name}.",
                details={
                    "backup_file": str(backup),
                    "target_file": str(target),
                },
            )
        except Exception:
            pass

        return recovered

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
    def _copy_database(source: Path, target: Path) -> None:
        source_connection = sqlite3.connect(source)
        destination_connection = sqlite3.connect(target)
        try:
            source_connection.backup(destination_connection)
        except Exception:
            destination_connection.close()
            source_connection.close()
            try:
                target.unlink()
            except OSError:
                pass
            raise
        else:
            destination_connection.close()
            source_connection.close()

    @staticmethod
    def _normalize_target_file(value: str | Path) -> Path:
        target = Path(value).expanduser()
        if target.suffix.casefold() != PROJECT_FILE_EXTENSION.casefold():
            target = target.with_suffix(PROJECT_FILE_EXTENSION)
        return target.resolve(strict=False)

    @staticmethod
    def _safe_file_stem(value: str) -> str:
        cleaned = "".join(
            char if char.isalnum() or char in (" ", "-", "_") else "_"
            for char in value.strip()
        )
        cleaned = cleaned.strip(" .")
        return cleaned or "Project"
