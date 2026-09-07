from __future__ import annotations

import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Callable

from core.app_paths import project_runtime_root
from core.database import DatabaseCompatibilityError
from core.project import (
    PROJECT_FILE_EXTENSION,
    Project,
    ProjectFormatError,
)
from core.project_filename import new_project_destination
from core.project_settings import ProjectSettings


class ProjectError(RuntimeError):
    pass


class ProjectManager:
    def __init__(self):
        self.current: Project | None = None

    @property
    def is_open(self) -> bool:
        return self.current is not None

    def preview_new_project_file(
        self,
        settings: ProjectSettings,
        parent_folder: str | Path,
    ) -> Path:
        normalized = settings.normalized()
        project_name = normalized.project_name.strip()
        if not project_name:
            raise ProjectError("Project Name wajib diisi.")

        # New Project UI requires an explicit code, while the manager keeps a
        # safe fallback for backward-compatible programmatic/test callers.
        project_code = normalized.project_code.strip() or project_name
        return new_project_destination(
            Path(parent_folder).expanduser(),
            project_code,
            project_name,
        )

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

        project_file = self.preview_new_project_file(normalized, parent)

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
            self._cleanup_created_project_artifacts(
                project_file,
                project_id,
            )
            raise

        self.current = project
        return project

    def create_transactional(
        self,
        settings: ProjectSettings,
        parent_folder: str | Path,
        *,
        after_create: Callable[[Project], None] | None = None,
    ) -> Project:
        """Create a project and rollback if a later creation stage fails.

        ``after_create`` is intentionally generic. Phase 11 initial source
        sync plugs into this transaction in a later step; keeping the wrapper
        here avoids a second project-creation path and makes cleanup semantics
        available to any post-create validation/sync stage.
        """
        previous = self.current
        project = self.create(settings, parent_folder)

        try:
            if after_create is not None:
                after_create(project)
        except Exception:
            self.rollback_created_project(
                project,
                restore_current=previous,
            )
            raise

        return project

    def rollback_created_project(
        self,
        project: Project,
        *,
        restore_current: Project | None = None,
    ) -> None:
        """Remove a not-yet-finalized project and its runtime artifacts."""
        if self.current is project:
            self.current = restore_current

        self._cleanup_created_project_artifacts(
            project.project_file,
            project.project_id,
        )

    @staticmethod
    def _cleanup_created_project_artifacts(
        project_file: str | Path,
        project_id: str,
    ) -> None:
        path = Path(project_file).expanduser()

        # Delete SQLite sidecars as well as the database itself. Sidecars can
        # be left by WAL/journal mode even when the primary operation failed.
        for candidate in (
            Path(str(path) + "-journal"),
            Path(str(path) + "-wal"),
            Path(str(path) + "-shm"),
            path,
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

        try:
            from services.audit_service import AuditService

            AuditService(saved.database).record(
                event_type="PROJECT",
                action="SAVE_AS",
                entity_type="project",
                summary=(
                    f"Project saved as {target.name}."
                ),
                details={
                    "source_file": str(project.project_file),
                    "target_file": str(target),
                    "project_id": saved.project_id,
                },
            )
        except Exception:
            pass

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
        *,
        expected_project_id: str = "",
    ) -> Project:
        backup = Path(backup_file).expanduser().resolve(strict=False)
        if not backup.is_file():
            raise ProjectError(
                f"Backup file tidak ditemukan:\n{backup}"
            )

        try:
            backup_project = Project.load(backup)
        except (ProjectFormatError, FileNotFoundError) as exc:
            raise ProjectError(
                f"Backup bukan .smproj yang valid: {exc}"
            ) from exc

        expected_id = str(expected_project_id or "").strip()
        if expected_id and backup_project.project_id != expected_id:
            raise ProjectError(
                "Backup berasal dari project yang berbeda."
            )

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
        """Legacy helper kept for compatibility with older external callers."""
        cleaned = "".join(
            char if char.isalnum() or char in (" ", "-", "_") else "_"
            for char in value.strip()
        )
        cleaned = cleaned.strip(" .")
        return cleaned or "Project"
