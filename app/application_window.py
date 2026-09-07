from __future__ import annotations

from PySide6.QtCore import QThread, Qt, Slot
from PySide6.QtWidgets import QMessageBox

from app.initial_project_creation_worker import InitialProjectCreationWorker
from app.main_window import MainWindow
from dialogs.project_settings_dialog import ProjectSettingsDialog
from dialogs.transactional_new_project_dialog import TransactionalNewProjectDialog
from services.initial_project_creation_service import InitialProjectCreationResult
from services.project_settings_change_validation import settings_change_flags


class ApplicationWindow(MainWindow):
    """Production orchestration layered over the stable workspace shell."""

    def new_project(self) -> None:
        if self._block_project_change_during_sync("Proyek Baru"):
            return

        active_thread = getattr(self, "_initial_project_thread", None)
        if active_thread is not None and active_thread.isRunning():
            self.statusBar().showMessage(
                "Initial Source Sync masih berjalan",
                3000,
            )
            return

        dialog = TransactionalNewProjectDialog(self)
        self._active_new_project_dialog = dialog
        self._initial_project_result = None
        self._initial_project_report = None
        self._initial_project_error = None
        self._initial_project_outcome = ""

        dialog.create_requested.connect(
            lambda: self._start_initial_project_creation(dialog)
        )

        accepted = bool(dialog.exec())
        project = self._initial_project_result
        self._active_new_project_dialog = None

        if not accepted or project is None:
            return

        self._clear_data_pages()
        self._project_data_state.reset(mark_dirty=True)
        self.refresh_project_page()
        self.setWindowTitle(
            f"{project.settings.project_name} - Script Manager"
        )

        # The project only reaches Recent Projects after .smproj creation,
        # production Source Sync, and post-sync verification all succeed.
        self._record_recent_project(project)
        self.set_page("PROJECT")
        self.statusBar().showMessage(
            f"Proyek dibuat dan sumber tersinkron: {project.project_file}",
            5000,
        )

    def open_project_settings(self) -> None:
        if self._block_project_change_during_sync("Pengaturan Proyek"):
            return

        project = self.project_manager.current
        if project is None:
            QMessageBox.information(
                self,
                "Pengaturan Proyek",
                "Buka atau buat proyek terlebih dahulu.",
            )
            return

        baseline = project.settings.normalized()
        dialog = ProjectSettingsDialog(project.settings, self)
        if not dialog.exec():
            return

        candidate = dialog.result_settings
        source_changed, tracking_changed, _links_changed = settings_change_flags(
            baseline,
            candidate,
        )

        try:
            self.project_manager.update_settings(candidate)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Pengaturan Proyek",
                f"Gagal menyimpan pengaturan.\n\n{exc}",
            )
            return

        current = self.project_manager.current
        self.refresh_project_page()
        if current is not None:
            self.setWindowTitle(
                f"{current.settings.project_name} - Script Manager"
            )

        if source_changed:
            self._invalidate_source_dependent_workspace()

        if tracking_changed:
            # Reuses the existing Tracking/Delivery refresh path. This updates
            # configure_track_files() with the new folders/audio spec and forces
            # a filesystem rescan only when those settings actually changed.
            self._refresh_tracking_files_state()

        if source_changed and tracking_changed:
            message = (
                "Pengaturan tersimpan; sumber berubah (Sinkronkan Sumber/F5 "
                "diperlukan) dan konfigurasi Tracking/Delivery diperbarui"
            )
        elif source_changed:
            message = (
                "Pengaturan tersimpan; sumber berubah — jalankan Sinkronkan "
                "Sumber (F5) sebelum melanjutkan pekerjaan berbasis naskah"
            )
        elif tracking_changed:
            message = (
                "Pengaturan tersimpan; konfigurasi filesystem "
                "Tracking/Delivery diperbarui"
            )
        else:
            message = "Pengaturan proyek tersimpan"

        self.statusBar().showMessage(message, 5000)

    def _invalidate_source_dependent_workspace(self) -> None:
        # Settings changes do not mutate the database. Keep committed data
        # visible, but mark every source-derived workspace dirty so it cannot
        # silently retain a stale cached view after the next source sync.
        for page_name in ("SCRIPT", "DIALOG", "TRACKING", "DELIVERY", "DATA"):
            self._project_data_state.mark_dirty(page_name)

    def _start_initial_project_creation(
        self,
        dialog: TransactionalNewProjectDialog,
    ) -> None:
        active_thread = getattr(self, "_initial_project_thread", None)
        if active_thread is not None and active_thread.isRunning():
            return

        self._initial_project_result = None
        self._initial_project_report = None
        self._initial_project_error = None
        self._initial_project_outcome = ""

        thread = QThread(self)
        worker = InitialProjectCreationWorker(
            self.project_manager,
            self.source_sync_engine,
            dialog.settings,
            dialog.parent_folder,
            preflight_report=dialog.source_preflight_report,
        )
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(
            dialog.update_creation_progress,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.completed.connect(
            self._initial_project_creation_completed,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.failed.connect(
            self._initial_project_creation_failed,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._initial_project_thread_finished)

        self._initial_project_thread = thread
        self._initial_project_worker = worker
        self.statusBar().showMessage(
            "Memverifikasi Source Preflight lalu membuat project…"
        )
        thread.start()

    @Slot(object)
    def _initial_project_creation_completed(
        self,
        result: InitialProjectCreationResult,
    ) -> None:
        self._initial_project_result = result.project
        self._initial_project_report = result.report
        self._initial_project_error = None
        self._initial_project_outcome = "success"

    @Slot(object)
    def _initial_project_creation_failed(self, exc: object) -> None:
        self._initial_project_result = None
        self._initial_project_report = None
        self._initial_project_error = exc
        self._initial_project_outcome = "failure"

    @Slot()
    def _initial_project_thread_finished(self) -> None:
        dialog = getattr(self, "_active_new_project_dialog", None)
        outcome = getattr(self, "_initial_project_outcome", "")
        report = getattr(self, "_initial_project_report", None)
        error = getattr(self, "_initial_project_error", None)

        self._initial_project_thread = None
        self._initial_project_worker = None

        if dialog is None:
            return

        if outcome == "success" and report is not None:
            dialog.creation_succeeded(report)
            return

        dialog.creation_failed(
            error or RuntimeError("Initial Source Sync berhenti tanpa hasil.")
        )
        self.statusBar().showMessage(
            "Pembuatan project gagal; wizard tetap terbuka untuk diperbaiki",
            5000,
        )
