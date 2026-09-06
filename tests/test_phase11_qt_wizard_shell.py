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
    from PySide6.QtWidgets import QApplication

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


def _fill_identity(dialog: NewProjectDialog, tmp_path) -> None:
    dialog.project_name.setText("AA23 Project")
    dialog.project_code.setText("AA23")
    dialog.client_name.setText("Client")
    dialog.location_edit.setText(str(tmp_path))


def test_new_project_wizard_shell_navigates_and_preserves_state(qapp, tmp_path):
    dialog = NewProjectDialog()

    assert dialog.page_stack.count() == 5
    assert len(dialog.milestone_rail.items) == 5
    assert dialog.current_step == 0
    assert dialog.back_button.isEnabled() is False
    assert dialog.next_button.isHidden() is False
    assert dialog.next_button.isEnabled() is False
    assert dialog.create_button.isHidden() is True
    assert dialog.help_button.accessibleName() == "Bantuan setup proyek"

    _fill_identity(dialog, tmp_path)
    qapp.processEvents()

    assert dialog._step_states[0] == WizardMilestoneState.VALID
    assert dialog.next_button.isEnabled() is True

    dialog._go_next()
    assert dialog.current_step == 1
    assert dialog.project_name.text() == "AA23 Project"
    assert dialog.project_code.text() == "AA23"

    dialog._go_back()
    assert dialog.current_step == 0
    assert dialog.project_name.text() == "AA23 Project"

    dialog._go_next()
    assert dialog.current_step == 1
    dialog.set_step_state(
        1,
        WizardMilestoneState.ERROR,
        "Blocking test",
    )
    assert dialog.next_button.isEnabled() is False
    dialog._go_next()
    assert dialog.current_step == 1

    source = tmp_path / "source-shell"
    source.mkdir()
    source_file = source / "AA23_EP001_SCRIPT.xlsx"
    source_file.write_bytes(b"filename-only")
    dialog.source_folder.setText(str(source))
    dialog.episode_before.setText("EP")
    dialog.episode_after.setText("_")
    source_result = dialog.source_section.validate_source_filenames()
    qapp.processEvents()
    assert source_result.is_valid
    assert dialog._step_states[1] == WizardMilestoneState.ERROR

    # Shell navigation test does not need to re-run the parser; inject the
    # already-tested successful preflight state so the generic navigation
    # contract can continue through later placeholder steps.
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
                    dialogue_count=1,
                    layout_detection="header",
                )
            ]
        )
    )
    assert dialog._step_states[1] == WizardMilestoneState.VALID
    assert dialog.next_button.isEnabled() is True

    while dialog.current_step < 4:
        dialog._go_next()

    assert dialog.current_step == 4
    assert dialog.next_button.isHidden() is True
    assert dialog.create_button.isHidden() is False
    assert dialog.back_button.isEnabled() is True
    assert not list(tmp_path.glob("*.smproj"))

    dialog.reject()
    dialog.close()
    qapp.processEvents()


def test_milestone1_auto_code_tracks_until_user_edits_code(qapp, tmp_path):
    dialog = NewProjectDialog()

    dialog.project_name.setText("Cinta")
    assert dialog.project_code.text() == "Cinta"

    dialog.project_name.setText("Cinta di Ujung Senja")
    assert dialog.project_code.text() == "Cinta di Ujung Senja"

    dialog.project_code.setText("AA23")
    dialog.project_code.textEdited.emit("AA23")
    dialog.project_name.setText("Judul Berubah")
    assert dialog.project_code.text() == "AA23"

    dialog.client_name.setText("Client A")
    dialog.location_edit.setText(str(tmp_path))
    qapp.processEvents()

    assert dialog._step_states[0] == WizardMilestoneState.VALID
    assert dialog.next_button.isEnabled() is True
    assert "AA23 - Judul Berubah.smproj" in dialog.destination_preview.text()
    assert not list(tmp_path.glob("*.smproj"))

    dialog.reject()
    dialog.close()
    qapp.processEvents()


def test_milestone1_missing_destination_has_explicit_create_folder(qapp, tmp_path):
    dialog = NewProjectDialog()
    target = tmp_path / "nested" / "projects"

    dialog.project_name.setText("Project Baru")
    dialog.project_code.setText("PB01")
    dialog.project_code.textEdited.emit("PB01")
    dialog.client_name.setText("Client")
    dialog.location_edit.setText(str(target))
    qapp.processEvents()

    assert target.exists() is False
    assert dialog._step_states[0] == WizardMilestoneState.ERROR
    assert dialog.create_location_button.isHidden() is False
    assert dialog.next_button.isEnabled() is False

    dialog.create_location_button.click()
    qapp.processEvents()

    assert target.is_dir()
    assert dialog._step_states[0] == WizardMilestoneState.VALID
    assert dialog.create_location_button.isHidden() is True
    assert dialog.next_button.isEnabled() is True
    assert not list(target.glob("*.smproj"))

    dialog.reject()
    dialog.close()
    qapp.processEvents()
