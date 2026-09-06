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


def test_new_project_wizard_shell_navigates_and_preserves_state(qapp, tmp_path):
    dialog = NewProjectDialog()

    assert dialog.page_stack.count() == 5
    assert len(dialog.milestone_rail.items) == 5
    assert dialog.current_step == 0
    assert dialog.back_button.isEnabled() is False
    assert dialog.next_button.isHidden() is False
    assert dialog.create_button.isHidden() is True
    assert dialog.help_button.accessibleName() == "Bantuan setup proyek"

    dialog.project_name.setText("AA23 Project")
    dialog.project_code.setText("AA23")
    dialog.client_name.setText("Client")
    dialog.location_edit.setText(str(tmp_path))
    qapp.processEvents()

    dialog._go_next()
    assert dialog.current_step == 1
    assert dialog.project_name.text() == "AA23 Project"
    assert dialog.project_code.text() == "AA23"

    dialog._go_back()
    assert dialog.current_step == 0
    assert dialog.project_name.text() == "AA23 Project"

    dialog.set_step_state(
        0,
        WizardMilestoneState.ERROR,
        "Blocking test",
    )
    assert dialog.next_button.isEnabled() is False
    dialog._go_next()
    assert dialog.current_step == 0

    dialog.set_step_state(0, WizardMilestoneState.WARNING, "Warning test")
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
