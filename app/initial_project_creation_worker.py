from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from core.project_manager import ProjectManager
from core.project_settings import ProjectSettings
from import_engine.source_sync import SourceSyncEngine
from services.initial_project_creation_service import InitialProjectCreationService
from services.source_preflight_service import SourcePreflightReport


class InitialProjectCreationWorker(QObject):
    """Run transactional project creation and initial sync off the GUI thread."""

    progress = Signal(object)
    completed = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(
        self,
        project_manager: ProjectManager,
        source_sync_engine: SourceSyncEngine,
        settings: ProjectSettings,
        parent_folder: str | Path,
        parent: QObject | None = None,
        *,
        preflight_report: SourcePreflightReport | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = InitialProjectCreationService(
            project_manager,
            source_sync_engine,
        )
        self._settings = settings
        self._parent_folder = parent_folder
        self._preflight_report = preflight_report

    @Slot()
    def run(self) -> None:
        try:
            result = self._service.run(
                self._settings,
                self._parent_folder,
                progress_callback=self.progress.emit,
                preflight_report=self._preflight_report,
            )
        except Exception as exc:  # noqa: BLE001 - worker boundary
            self.failed.emit(exc)
        else:
            self.completed.emit(result)
        finally:
            self.finished.emit()
