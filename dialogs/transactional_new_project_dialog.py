from __future__ import annotations

from PySide6.QtCore import Signal, Slot

from dialogs.new_project_dialog import NewProjectDialog
from import_engine.source_sync import SourceSyncProgress, SourceSyncReport
from widgets.initial_source_sync_panel import InitialSourceSyncPanel


class TransactionalNewProjectDialog(NewProjectDialog):
    """New Project wizard whose final accept is owned by the async transaction.

    All validation continues to live in ``NewProjectDialog._accept``. The base
    method stores validated settings/parent folder and calls ``self.accept()``;
    this subclass intercepts that call, keeps the modal wizard open, and emits
    ``create_requested``. Only ``creation_succeeded`` performs the real dialog
    accept after initial source sync and verification have completed.
    """

    create_requested = Signal()

    def __init__(self, parent=None) -> None:
        self._creation_running = False
        self._allow_dialog_accept = False
        super().__init__(parent)

        self.initial_sync_panel = InitialSourceSyncPanel()
        final_page = self.page_stack.widget(len(self.STEP_TITLES) - 1)
        final_content = final_page.widget() if final_page is not None else None
        final_layout = final_content.layout() if final_content is not None else None
        if final_layout is not None:
            insert_at = max(final_layout.count() - 1, 0)
            final_layout.insertWidget(insert_at, self.initial_sync_panel)

    @property
    def creation_running(self) -> bool:
        return self._creation_running

    def accept(self) -> None:
        if self._allow_dialog_accept:
            super().accept()
            return
        if self._creation_running:
            return

        self._creation_running = True
        self.initial_sync_panel.set_running()
        self.validation_status.setText(
            "Membuat .smproj dan menjalankan Initial Source Sync. "
            "Wizard tetap terbuka sampai proses selesai."
        )
        self._set_creation_controls_enabled(False)
        self.create_requested.emit()

    def reject(self) -> None:
        if self._creation_running:
            return
        super().reject()

    @Slot(object)
    def update_creation_progress(self, progress: SourceSyncProgress) -> None:
        if not self._creation_running:
            return
        self.initial_sync_panel.update_progress(progress)

    def creation_succeeded(self, report: SourceSyncReport) -> None:
        if not self._creation_running:
            return
        self.initial_sync_panel.set_success(report)
        self.validation_status.setText(
            "✓ Project siap. Membuka Project Dashboard…"
        )
        self._creation_running = False
        self._allow_dialog_accept = True
        super().accept()

    def creation_failed(self, error: object) -> None:
        self._creation_running = False
        self.initial_sync_panel.set_error(str(error))

        # Rollback removes the destination again. Re-run the existing final
        # validation so the same preserved input becomes retryable immediately.
        self._refresh_review()
        self._set_creation_controls_enabled(True)
        self.validation_status.setText(
            "✕ Project belum dibuat. Input tetap dipertahankan; "
            "perbaiki penyebab lalu klik Buat Proyek untuk mencoba lagi."
        )

    def _set_creation_controls_enabled(self, enabled: bool) -> None:
        self.back_button.setEnabled(enabled and self.current_step > 0)
        self.create_button.setEnabled(enabled)
        self.cancel_button.setEnabled(enabled)
        self.help_button.setEnabled(enabled)
        self.review_panel.setEnabled(enabled)
        self.milestone_rail.setEnabled(enabled)

        if enabled:
            # Let the base wizard restore blocker/collision semantics rather
            # than blindly enabling Create after a failed transaction.
            self._update_navigation_buttons()
