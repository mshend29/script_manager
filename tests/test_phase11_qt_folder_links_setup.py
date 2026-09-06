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


def _prepare_operational_folders(dialog, tmp_path) -> tuple[str, str, str]:
    source = tmp_path / "source"
    stem = tmp_path / "stem"
    delivery = tmp_path / "delivery"
    source.mkdir()
    stem.mkdir()
    delivery.mkdir()
    dialog.source_folder.setText(str(source))
    dialog.stem_output_folder.setText(str(stem))
    dialog.delivery_folder.setText(str(delivery))
    return str(source), str(stem), str(delivery)


def test_folder_links_milestone_shows_read_only_folder_summary(qapp, tmp_path):
    dialog = NewProjectDialog()
    source, stem, delivery = _prepare_operational_folders(dialog, tmp_path)

    dialog._show_step(3)
    qapp.processEvents()

    assert dialog.current_step == 3
    assert dialog._step_states[3] == WizardMilestoneState.VALID
    assert dialog.next_button.isEnabled() is True
    assert dialog.folder_links_summary_panel.source_folder.text() == source
    assert dialog.folder_links_summary_panel.stem_folder.text() == stem
    assert dialog.folder_links_summary_panel.delivery_folder.text() == delivery
    assert dialog.folder_links_summary_panel.source_folder.isReadOnly() is True
    assert dialog.folder_links_summary_panel.stem_folder.isReadOnly() is True
    assert dialog.folder_links_summary_panel.delivery_folder.isReadOnly() is True
    assert "opsional" in dialog.validation_status.text().lower()

    dialog.reject()
    dialog.close()
    qapp.processEvents()


def test_folder_links_milestone_accepts_valid_optional_urls(qapp, tmp_path):
    dialog = NewProjectDialog()
    _prepare_operational_folders(dialog, tmp_path)
    dialog._show_step(3)

    dialog.main_drive_url.setText(
        "https://drive.google.com/drive/folders/main"
    )
    dialog.material_drive_url.setText("https://example.test/material")
    dialog.delivery_drive_url.setText("http://example.test/delivery")
    qapp.processEvents()

    assert dialog._step_states[3] == WizardMilestoneState.VALID
    assert dialog.next_button.isEnabled() is True
    assert "3 tautan browser" in dialog.validation_status.text()

    dialog.reject()
    dialog.close()
    qapp.processEvents()


def test_folder_links_milestone_blocks_invalid_nonempty_url(qapp, tmp_path):
    dialog = NewProjectDialog()
    _prepare_operational_folders(dialog, tmp_path)
    dialog._show_step(3)

    dialog.main_drive_url.setText("G:/Client/AA23")
    qapp.processEvents()

    assert dialog._step_states[3] == WizardMilestoneState.ERROR
    assert dialog.next_button.isEnabled() is False
    assert "URL http/https" in dialog.validation_status.text()

    dialog.main_drive_url.clear()
    qapp.processEvents()
    assert dialog._step_states[3] == WizardMilestoneState.VALID
    assert dialog.next_button.isEnabled() is True

    dialog.reject()
    dialog.close()
    qapp.processEvents()
