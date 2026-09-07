from __future__ import annotations

import importlib.util
import os

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PYSIDE_AVAILABLE = importlib.util.find_spec("PySide6") is not None

pytestmark = pytest.mark.skipif(
    not PYSIDE_AVAILABLE,
    reason="PySide6 is only installed in the Qt runtime CI job.",
)

if PYSIDE_AVAILABLE:
    from PySide6.QtWidgets import QApplication, QDialog

    from dialogs.transactional_new_project_dialog import (
        TransactionalNewProjectDialog,
    )
    from import_engine.source_sync import SourceSyncProgress, SourceSyncReport
    from services.initial_project_creation_service import (
        InitialProjectSourceChangedError,
    )
    from services.source_preflight_service import (
        SourcePreflightFileResult,
        SourcePreflightReport,
    )
    from widgets.wizard_milestone_rail import WizardMilestoneState


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


def _prepare_ready_dialog(dialog: TransactionalNewProjectDialog, tmp_path) -> None:
    project_dir = tmp_path / "project"
    source_dir = tmp_path / "source"
    stem_dir = tmp_path / "stem"
    delivery_dir = tmp_path / "delivery"
    for folder in (project_dir, source_dir, stem_dir, delivery_dir):
        folder.mkdir()

    dialog.project_name.setText("Initial Sync UI")
    dialog.project_code.setText("ISUI")
    dialog.project_code.textEdited.emit("ISUI")
    dialog.client_name.setText("Client")
    dialog.location_edit.setText(str(project_dir))

    source_file = source_dir / "AA23_EP001_SCRIPT.xlsx"
    source_file.write_bytes(b"filename-only")
    dialog.source_folder.setText(str(source_dir))
    dialog.episode_before.setText("EP")
    dialog.episode_after.setText("_")
    source_result = dialog.source_section.validate_source_filenames()
    mapping = source_result.mappings[0]
    dialog._source_preflight_finished(
        SourcePreflightReport(
            files=[
                SourcePreflightFileResult(
                    file_path=mapping.file_path,
                    file_name=mapping.file_name,
                    episode_number=mapping.episode_number,
                    inspected=True,
                    parsed=True,
                    dialogue_count=7,
                    layout_detection="header",
                )
            ]
        )
    )

    dialog.stem_output_folder.setText(str(stem_dir))
    dialog.delivery_folder.setText(str(delivery_dir))
    dialog._show_step(4)


def test_final_wizard_stays_open_during_initial_sync_and_retry_preserves_input(
    qapp,
    tmp_path,
):
    dialog = TransactionalNewProjectDialog()
    _prepare_ready_dialog(dialog, tmp_path)
    dialog.show()
    qapp.processEvents()
    requested: list[bool] = []
    dialog.create_requested.connect(lambda: requested.append(True))

    dialog._accept()
    qapp.processEvents()

    assert requested == [True]
    assert dialog.creation_running is True
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert dialog.initial_sync_panel.isVisible() is True
    assert dialog.create_button.isEnabled() is False
    assert dialog.cancel_button.isEnabled() is False

    dialog.update_creation_progress(
        SourceSyncProgress(
            stage="parsing",
            current=1,
            total=2,
            message="Parsing scripts 1/2",
            file_name="EP001.xlsx",
        )
    )
    assert dialog.initial_sync_panel.progress_bar.maximum() == 2
    assert dialog.initial_sync_panel.progress_bar.value() == 1
    assert "EP001.xlsx" in dialog.initial_sync_panel.status_label.text()

    dialog.creation_failed(RuntimeError("workbook berubah"))
    qapp.processEvents()

    assert dialog.creation_running is False
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert dialog.project_name.text() == "Initial Sync UI"
    assert dialog.source_folder.text().endswith("source")
    assert dialog.create_button.isEnabled() is True
    assert dialog.cancel_button.isEnabled() is True
    assert "workbook berubah" in dialog.initial_sync_panel.details.toPlainText()

    dialog._accept()
    qapp.processEvents()
    assert requested == [True, True]
    assert dialog.creation_running is True

    dialog.creation_succeeded(
        SourceSyncReport(
            scanned=1,
            parsed_dialogues=7,
            auto_locked=2,
            unresolved_cast=1,
        )
    )
    qapp.processEvents()

    assert dialog.result() == QDialog.DialogCode.Accepted
    dialog.close()
    qapp.processEvents()


def test_stale_preflight_routes_back_to_source_and_requires_rerun(qapp, tmp_path):
    dialog = TransactionalNewProjectDialog()
    _prepare_ready_dialog(dialog, tmp_path)
    dialog.show()
    qapp.processEvents()

    dialog._accept()
    qapp.processEvents()
    assert dialog.creation_running is True

    dialog.creation_failed(
        InitialProjectSourceChangedError(
            "Source berubah sejak Source Preflight. Jalankan Source Preflight ulang."
        )
    )
    qapp.processEvents()

    assert dialog.creation_running is False
    assert dialog.current_step == 1
    assert dialog.source_preflight_report is None
    assert dialog._step_states[1] == WizardMilestoneState.ERROR
    assert dialog.next_button.isEnabled() is False
    assert dialog.source_preflight_panel.start_button.isEnabled() is True
    assert "Source berubah" in dialog.source_preflight_panel.details.toPlainText()

    dialog.close()
    qapp.processEvents()
