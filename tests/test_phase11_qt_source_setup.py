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
    from widgets.wizard_milestone_rail import WizardMilestoneState


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


def _touch(path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"filename-only-validation")


def _prepare_identity(dialog, tmp_path, qapp) -> None:
    dialog.project_name.setText("AA23 Project")
    dialog.project_code.setText("AA23")
    dialog.client_name.setText("Client")
    dialog.location_edit.setText(str(tmp_path / "project"))
    dialog._create_destination_folder()
    qapp.processEvents()
    assert dialog._step_states[0] == WizardMilestoneState.VALID


def test_source_milestone_blocks_until_all_filenames_validate(qapp, tmp_path):
    dialog = NewProjectDialog()
    _prepare_identity(dialog, tmp_path, qapp)

    dialog._go_next()
    qapp.processEvents()
    assert dialog.current_step == 1
    assert dialog._step_states[1] == WizardMilestoneState.ERROR
    assert dialog.next_button.isEnabled() is False

    source = tmp_path / "source-valid"
    _touch(source / "AA23_EP001_SCRIPT.xlsx")
    _touch(source / "AA23_EP002_SCRIPT.xlsm")
    _touch(source / "AA23_EP003_SCRIPT.xlsx")

    dialog.source_folder.setText(str(source))
    dialog.episode_before.setText("EP")
    dialog.episode_after.setText("_")
    result = dialog.source_section.validate_source_filenames()
    qapp.processEvents()

    assert result.is_valid
    assert result.file_count == 3
    assert result.episode_numbers == (1, 2, 3)
    assert dialog._step_states[1] == WizardMilestoneState.VALID
    assert dialog.next_button.isEnabled() is True
    assert "3 file sumber" in dialog.validation_status.text()
    assert "awal / tengah / akhir" in dialog.source_section.filename_preview.text()

    dialog.episode_after.setText("-WRONG-")
    qapp.processEvents()
    assert dialog._step_states[1] == WizardMilestoneState.ERROR
    assert dialog.next_button.isEnabled() is False

    invalid = dialog.source_section.validate_source_filenames()
    assert invalid.is_valid is False
    assert len(invalid.errors) == 3

    dialog.reject()
    dialog.close()
    qapp.processEvents()


def test_source_milestone_gap_is_warning_not_blocker(qapp, tmp_path):
    dialog = NewProjectDialog()
    _prepare_identity(dialog, tmp_path, qapp)
    dialog._go_next()

    source = tmp_path / "source-gap"
    _touch(source / "AA23_EP001_SCRIPT.xlsx")
    _touch(source / "AA23_EP003_SCRIPT.xlsx")

    dialog.source_folder.setText(str(source))
    dialog.episode_before.setText("EP")
    dialog.episode_after.setText("_")
    result = dialog.source_section.validate_source_filenames()
    qapp.processEvents()

    assert result.is_valid
    assert result.missing_episodes == (2,)
    assert dialog._step_states[1] == WizardMilestoneState.WARNING
    assert dialog.next_button.isEnabled() is True
    assert "Gap episode" in dialog.validation_status.text()

    dialog.reject()
    dialog.close()
    qapp.processEvents()
