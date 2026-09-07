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
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QPushButton

    from dialogs.new_project_dialog import NewProjectDialog
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


def _prepare_ready_dialog(dialog: NewProjectDialog, tmp_path) -> None:
    project_dir = tmp_path / "project"
    source_dir = tmp_path / "source"
    stem_dir = tmp_path / "stem"
    delivery_dir = tmp_path / "delivery"
    for folder in (project_dir, source_dir, stem_dir, delivery_dir):
        folder.mkdir()

    dialog.project_name.setText("Cinta di Ujung Senja")
    dialog.project_code.setText("AA23")
    dialog.project_code.textEdited.emit("AA23")
    dialog.client_name.setText("Client A")
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
    dialog.main_drive_url.setText("https://drive.google.com/drive/folders/main")
    dialog.material_drive_url.setText("https://drive.google.com/drive/folders/material")
    dialog.delivery_drive_url.setText("https://drive.google.com/drive/folders/delivery")


def test_review_contains_all_required_configuration_and_is_ready(qapp, tmp_path):
    dialog = NewProjectDialog()
    _prepare_ready_dialog(dialog, tmp_path)
    qapp.processEvents()

    dialog._show_step(4)
    qapp.processEvents()

    assert dialog._step_states[4] == WizardMilestoneState.VALID
    assert dialog.create_button.isEnabled() is True
    assert len(dialog.review_panel.sections) == 4

    all_details = "\n".join(
        detail
        for section in dialog.review_panel.sections
        for detail in section.details
    )
    assert "Cinta di Ujung Senja" in all_details
    assert "AA23 - Cinta di Ujung Senja.smproj" in all_details
    assert "Folder Sumber:" in all_details
    assert "Workbook: 1" in all_details
    assert "Episode: 1–1" in all_details
    assert "Delimiter:" in all_details
    assert "Preflight: 1 workbook / 7 dialog" in all_details
    assert "Audio: WAV" in all_details
    assert "48 kHz" in all_details
    assert "24-bit" in all_details
    assert "Mono" in all_details
    assert "Folder Stem:" in all_details
    assert "Folder Setoran:" in all_details
    assert "Drive Utama: https://drive.google.com/drive/folders/main" in all_details
    assert "Material: https://drive.google.com/drive/folders/material" in all_details
    assert "Setoran: https://drive.google.com/drive/folders/delivery" in all_details

    source_edit = next(
        button
        for button in dialog.review_panel.findChildren(QPushButton)
        if button.accessibleName() == "Ubah Sumber Naskah"
    )
    source_edit.click()
    qapp.processEvents()
    assert dialog.current_step == 1

    dialog.close()
    qapp.processEvents()


def test_review_blocks_create_and_enter_does_not_accept(qapp, tmp_path):
    dialog = NewProjectDialog()
    _prepare_ready_dialog(dialog, tmp_path)
    qapp.processEvents()

    missing_stem = tmp_path / "missing-stem"
    dialog.stem_output_folder.setText(str(missing_stem))
    dialog._show_step(4)
    qapp.processEvents()

    assert dialog._step_states[4] == WizardMilestoneState.ERROR
    assert dialog.create_button.isEnabled() is False
    assert any(
        section.status == "error" and section.step_index == 2
        for section in dialog.review_panel.sections
    )

    # Restore a valid output folder, then ensure Return does not accept the
    # final dialog even when the Create button has focus.
    stem = tmp_path / "stem-restored"
    stem.mkdir()
    dialog.stem_output_folder.setText(str(stem))
    dialog._show_step(4)
    qapp.processEvents()
    assert dialog.create_button.isEnabled() is True

    dialog.create_button.setFocus()
    QTest.keyClick(dialog.create_button, Qt.Key.Key_Return)
    qapp.processEvents()
    assert dialog.result() == 0

    dialog.close()
    qapp.processEvents()
