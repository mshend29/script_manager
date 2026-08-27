from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from core.project import Project
from import_engine.source_sync import SourceSyncEngine, SourceSyncReport


class SourceSyncWorker(QObject):
    """Run source prepare/apply operations outside the Qt GUI thread."""

    progress = Signal(object)
    completed = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(
        self,
        engine: SourceSyncEngine,
        project: Project,
        *,
        operation: str = "prepare",
        report: SourceSyncReport | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._project = project
        self._operation = str(operation).strip().casefold()
        self._report = report

    @Slot()
    def run(self) -> None:
        try:
            if self._operation == "prepare":
                result = self._engine.prepare(
                    self._project,
                    progress_callback=self.progress.emit,
                )
            elif self._operation == "apply":
                if self._report is None:
                    raise RuntimeError(
                        "Source apply worker membutuhkan prepared report."
                    )
                result = self._engine.apply(
                    self._project,
                    self._report,
                    progress_callback=self.progress.emit,
                )
            else:
                raise RuntimeError(
                    f"Source sync operation tidak dikenal: {self._operation}"
                )
        except Exception as exc:  # noqa: BLE001 - forwarded to GUI boundary
            self.failed.emit(exc)
        else:
            self.completed.emit(result)
        finally:
            self.finished.emit()
