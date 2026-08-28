from __future__ import annotations

import shutil
from pathlib import Path

from core.database import DatabaseCompatibilityError
from core.project import (
    DATABASE_FILE_NAME,
    PROJECT_FILE_NAME,
    PROJECT_PACKAGE_EXTENSION,
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

        raw_folder_name = normalized.project_code or project_name
        if raw_folder_name.casefold().endswith(
            PROJECT_PACKAGE_EXTENSION.casefold()
        ):
            raw_folder_name = raw_folder_name[
                :-len(PROJECT_PACKAGE_EXTENSION)
            ]

        folder_name = self._safe_folder_name(raw_folder_name)

        project_root = parent / f"{folder_name}{PROJECT_PACKAGE_EXTENSION}"

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
        try:
            project = Project.load(path)
        except ProjectFormatError as exc:
            raise ProjectError(str(exc)) from exc

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

    def convert_current_to_package(self) -> Project:
        project = self._require_project()

        if project.is_package:
            return project

        project.save()

        old_root = project.root
        target = old_root.with_name(
            old_root.name + PROJECT_PACKAGE_EXTENSION
        )

        if target.exists():
            raise ProjectError(
                "Target .drsp sudah ada:\n"
                f"{target}"
            )

        original_paths = {
            key: str(getattr(project.settings, key, "") or "")
            for key in (
                "project_folder",
                "source_folder",
                "stem_output_folder",
                "delivery_folder",
            )
        }

        try:
            old_root.rename(target)
        except OSError as exc:
            raise ProjectError(
                "Gagal mengubah project folder menjadi .drsp. "
                "Pastikan folder tidak sedang dikunci aplikasi lain.\n\n"
                f"{exc}"
            ) from exc

        try:
            project.root = target

            for key, raw in original_paths.items():
                setattr(
                    project.settings,
                    key,
                    self._rebase_project_path(
                        raw,
                        old_root=old_root,
                        new_root=target,
                    ),
                )

            project.settings.project_folder = str(target)
            project.save()

            from services.audit_service import AuditService

            AuditService(project.database).record(
                event_type="PROJECT",
                action="CONVERT_TO_DRSP",
                entity_type="project",
                summary=(
                    f"Legacy project converted to {target.name}."
                ),
                details={
                    "old_root": str(old_root),
                    "new_root": str(target),
                },
            )
        except Exception:
            # Best-effort rollback if descriptor update fails after directory
            # rename. Do not overwrite a newly-created old path.
            try:
                if target.exists() and not old_root.exists():
                    target.rename(old_root)
                    project.root = old_root
                    for key, raw in original_paths.items():
                        setattr(project.settings, key, raw)
                    project.settings.project_folder = str(old_root)
                    try:
                        project.save()
                    except Exception:
                        pass
            except OSError:
                pass
            raise

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
    def _rebase_project_path(
        value: str,
        *,
        old_root: Path,
        new_root: Path,
    ) -> str:
        raw = str(value or "").strip()
        if not raw:
            return raw

        path = Path(raw).expanduser()
        try:
            relative = path.resolve(strict=False).relative_to(
                old_root.resolve(strict=False)
            )
        except (OSError, ValueError):
            return raw

        return str(new_root / relative)

    @staticmethod
    def _safe_folder_name(value: str) -> str:
        cleaned = "".join(
            char if char.isalnum() or char in (" ", "-", "_") else "_"
            for char in value.strip()
        )
        cleaned = cleaned.strip(" .")
        return cleaned or "Project"
