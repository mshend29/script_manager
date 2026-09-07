from __future__ import annotations

from PySide6.QtCore import Signal, Slot

from dialogs.new_project_dialog import NewProjectDialog
from import_engine.source_sync import SourceSyncProgress, SourceSyncReport
from services.initial_project_creation_service import InitialProjectSourceChangedError
from services.project_setup_validation import validate_project_identity_destination
from services.source_preflight_service import SourcePreflightReport
from widgets.initial_source_sync_panel import InitialSourceSyncPanel
from widgets.wizard_milestone_rail import WizardMilestoneState


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
            "Memverifikasi Source Preflight, membuat .smproj, lalu menjalankan "
            "Initial Source Sync. Wizard tetap terbuka sampai proses selesai."
        )
        self._set_creation_controls_enabled(False)
        self.create_requested.emit()

    def reject(self) -> None:
        if self._creation_running:
            return
        super().reject()

    def _go_next(self) -> None:
        """Keep keyboard users at the first blocker when navigation is denied."""
        previous_step = self.current_step
        super()._go_next()
        if (
            self.current_step == previous_step
            and self._step_states[previous_step] == WizardMilestoneState.ERROR
        ):
            self._focus_current_blocker()

    def _focus_current_blocker(self) -> None:
        step = self.current_step
        widget = None

        if step == 0:
            validation = validate_project_identity_destination(
                self.sections.to_settings(),
                self.location_edit.text(),
            )
            field = validation.issues[0].field if validation.issues else ""
            widget = {
                "project_name": self.project_name,
                "project_code": self.project_code,
                "client_name": self.client_name,
                "start_date": self.start_date,
                "project_destination": self.location_edit,
                "project_file": self.location_edit,
            }.get(field)

        elif step == 1:
            validation = self.source_section.validation
            if validation is not None and validation.errors:
                field = validation.errors[0].field
                widget = {
                    "source_folder": self.source_folder,
                    "episode_before": self.episode_before,
                    "episode_after": self.episode_after,
                }.get(field)
                if widget is None:
                    widget = (
                        self.episode_before
                        if self.source_folder.text().strip()
                        else self.source_folder
                    )
            elif self.source_preflight_panel.start_button.isEnabled():
                widget = self.source_preflight_panel.start_button
            else:
                widget = self.source_folder

        elif step == 2:
            validation = self.audio_validation
            field = (
                validation.errors[0].field
                if validation is not None and validation.errors
                else ""
            )
            widget = {
                "stem_output_folder": self.stem_output_folder.edit,
                "delivery_folder": self.delivery_folder.edit,
                "audio_sample_rate": self.audio_sample_rate,
                "audio_bit_depth": self.audio_bit_depth,
                "audio_channels": self.audio_channels,
            }.get(field)

        elif step == 3:
            validation = self.folder_links_validation
            field = (
                validation.errors[0].field
                if validation is not None and validation.errors
                else ""
            )
            widget = {
                "source_folder": self.source_folder,
                "stem_output_folder": self.stem_output_folder.edit,
                "delivery_folder": self.delivery_folder.edit,
                "main_drive_url": self.main_drive_url,
                "material_drive_url": self.material_drive_url,
                "delivery_drive_url": self.delivery_drive_url,
            }.get(field)

        if widget is not None and widget.isEnabled():
            widget.setFocus()

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
        stale_preflight = isinstance(error, InitialProjectSourceChangedError)

        if stale_preflight:
            # The filename configuration can still be correct while workbook
            # bytes changed. Invalidate only the expensive preflight readiness
            # and route the operator back to Milestone 2 for an explicit rerun.
            self._source_preflight_report = None
            self.source_preflight_panel.set_report(
                SourcePreflightReport(problems=[str(error)])
            )
            self.set_step_state(
                1,
                "error",
                "Source berubah sejak Source Preflight. Jalankan Source Preflight ulang.",
            )

        # Rollback removes the destination again. Re-run the existing final
        # validation so the same preserved input becomes retryable after the
        # relevant blocker is resolved.
        self._refresh_review()
        self._set_creation_controls_enabled(True)

        if stale_preflight:
            self._show_step(1)
            if self.source_preflight_panel.start_button.isEnabled():
                self.source_preflight_panel.start_button.setFocus()
            else:
                self.source_folder.setFocus()
            return

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
