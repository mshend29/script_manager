from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from core.project import Project
from import_engine.source_sync import SourceSyncEngine


class SourceSyncWorker(QObject):
    """Run the source synchronization pipeline outside the Qt GUI thread."""

    progress = Signal(object)
    completed = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(
        self,
        engine: SourceSyncEngine,
        project: Project,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._project = project

    @Slot()
    def run(self) -> None:
        try:
            report = self._engine.synchronize(
                self._project,
                progress_callback=self.progress.emit,
            )
        except Exception as exc:  # noqa: BLE001 - forwarded to the GUI boundary
            self.failed.emit(exc)
        else:
            self.completed.emit(report)
        finally:
            self.finished.emit()
