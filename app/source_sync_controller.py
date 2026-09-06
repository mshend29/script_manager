from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot

from app.source_sync_worker import SourceSyncWorker
from core.project import Project
from import_engine.source_sync import (
    SourceSyncEngine,
    SourceSyncProgress,
    SourceSyncReport,
)


class SourceSyncController(QObject):
    """Own the asynchronous prepare/apply lifecycle for Source Sync.

    MainWindow remains responsible for operator-facing decisions such as
    accepting the preview. This controller owns only thread/worker lifecycle
    and guarantees that an approved Apply starts after Prepare has unwound.
    """

    progress = Signal(object)
    prepared = Signal(str, object)
    applied = Signal(str, object)
    failed = Signal(str, str, object)
    phase_started = Signal(str, str)
    busy_changed = Signal(bool)

    def __init__(
        self,
        engine: SourceSyncEngine | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine or SourceSyncEngine()

        self._thread: QThread | None = None
        self._worker: SourceSyncWorker | None = None
        self._title = ""
        self._operation = ""

        self._pending_project: Project | None = None
        self._pending_report: SourceSyncReport | None = None
        self._pending_title = ""

    @property
    def is_running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.isRunning()

    @property
    def title(self) -> str:
        return self._title

    @property
    def operation(self) -> str:
        return self._operation

    def start_prepare(self, project: Project, *, title: str) -> bool:
        if self.is_running:
            return False
        self._start(
            project=project,
            title=title,
            operation="prepare",
            report=None,
        )
        return True

    def apply_after_prepare(
        self,
        project: Project,
        report: SourceSyncReport,
        *,
        title: str,
    ) -> None:
        """Apply now or defer until the Prepare thread has fully stopped."""
        if self.is_running:
            self._pending_project = project
            self._pending_report = report
            self._pending_title = title
            return

        self._start(
            project=project,
            title=title,
            operation="apply",
            report=report,
        )

    def clear_pending_apply(self) -> None:
        self._pending_project = None
        self._pending_report = None
        self._pending_title = ""

    def _start(
        self,
        *,
        project: Project,
        title: str,
        operation: str,
        report: SourceSyncReport | None,
    ) -> None:
        if self.is_running:
            raise RuntimeError("Source Sync worker is already running.")

        thread = QThread(self)
        worker = SourceSyncWorker(
            self.engine,
            project,
            operation=operation,
            report=report,
        )
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(
            self._forward_progress,
            Qt.ConnectionType.QueuedConnection,
        )
        if operation == "prepare":
            worker.completed.connect(
                self._prepare_completed,
                Qt.ConnectionType.QueuedConnection,
            )
        else:
            worker.completed.connect(
                self._apply_completed,
                Qt.ConnectionType.QueuedConnection,
            )
        worker.failed.connect(
            self._worker_failed,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._thread_finished)

        self._thread = thread
        self._worker = worker
        self._title = str(title or "Source Sync")
        self._operation = operation

        phase_text = (
            "preparing preview"
            if operation == "prepare"
            else "applying changes"
        )
        self.busy_changed.emit(True)
        self.phase_started.emit(self._title, operation)
        self.progress.emit(
            SourceSyncProgress(
                stage="starting",
                message=f"{self._title}: {phase_text}...",
            )
        )
        thread.start()

    @Slot(object)
    def _forward_progress(self, progress: SourceSyncProgress) -> None:
        self.progress.emit(progress)

    @Slot(object)
    def _prepare_completed(self, report: SourceSyncReport) -> None:
        self.prepared.emit(self._title or "Source Sync", report)

    @Slot(object)
    def _apply_completed(self, report: SourceSyncReport) -> None:
        self.applied.emit(self._title or "Source Sync", report)

    @Slot(object)
    def _worker_failed(self, exc: object) -> None:
        self.clear_pending_apply()
        self.failed.emit(
            self._title or "Source Sync",
            self._operation or "source sync",
            exc,
        )

    @Slot()
    def _thread_finished(self) -> None:
        pending_project = self._pending_project
        pending_report = self._pending_report
        pending_title = self._pending_title

        self._thread = None
        self._worker = None
        self._title = ""
        self._operation = ""
        self.clear_pending_apply()
        self.busy_changed.emit(False)

        if pending_project is not None and pending_report is not None:
            self._start(
                project=pending_project,
                title=pending_title or "Source Sync",
                operation="apply",
                report=pending_report,
            )
