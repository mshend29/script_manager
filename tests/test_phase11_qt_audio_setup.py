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


def test_audio_milestone_blocks_until_output_folders_exist(qapp, tmp_path):
    dialog = NewProjectDialog()
    dialog._show_step(2)
    qapp.processEvents()

    assert dialog.current_step == 2
    assert dialog._step_states[2] == WizardMilestoneState.ERROR
    assert dialog.next_button.isEnabled() is False
    assert dialog.audio_sample_rate.currentData() == 48000
    assert dialog.audio_bit_depth.currentData() == 24
    assert dialog.audio_channels.currentData() == 1

    stem = tmp_path / "outputs" / "stem"
    delivery = tmp_path / "delivery"
    dialog.stem_output_folder.setText(str(stem))
    dialog.delivery_folder.setText(str(delivery))
    qapp.processEvents()

    assert dialog._step_states[2] == WizardMilestoneState.ERROR
    assert dialog.audio_setup_panel.create_stem_button.isHidden() is False
    assert dialog.audio_setup_panel.create_delivery_button.isHidden() is False
    assert stem.exists() is False
    assert delivery.exists() is False

    dialog.audio_setup_panel.create_stem_button.click()
    qapp.processEvents()
    assert stem.is_dir()
    assert dialog._step_states[2] == WizardMilestoneState.ERROR

    dialog.audio_setup_panel.create_delivery_button.click()
    qapp.processEvents()
    assert delivery.is_dir()
    assert dialog._step_states[2] == WizardMilestoneState.VALID
    assert dialog.next_button.isEnabled() is True
    assert "konfigurasi WAV siap" in dialog.validation_status.text()

    dialog._go_next()
    qapp.processEvents()
    assert dialog.current_step == 3
    assert not list(stem.glob(".script_manager_audio_write_test_*"))
    assert not list(delivery.glob(".script_manager_audio_write_test_*"))

    dialog.reject()
    dialog.close()
    qapp.processEvents()


def test_audio_milestone_rejects_browser_url(qapp, tmp_path):
    dialog = NewProjectDialog()
    dialog._show_step(2)

    delivery = tmp_path / "delivery"
    delivery.mkdir()
    dialog.stem_output_folder.setText(
        "https://drive.google.com/drive/folders/example"
    )
    dialog.delivery_folder.setText(str(delivery))
    qapp.processEvents()

    assert dialog._step_states[2] == WizardMilestoneState.ERROR
    assert dialog.next_button.isEnabled() is False
    assert "URL browser" in dialog.validation_status.text()

    dialog.reject()
    dialog.close()
    qapp.processEvents()
