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


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


@pytest.mark.parametrize(
    ("width", "height"),
    (
        (1920, 1080),
        (1366, 768),
    ),
)
def test_phase11_wizard_controls_remain_usable_at_target_desktop_sizes(
    qapp,
    width,
    height,
):
    dialog = NewProjectDialog()
    dialog.resize(width, height)
    dialog.show()
    qapp.processEvents()

    assert dialog.width() >= dialog.minimumWidth()
    assert dialog.height() >= dialog.minimumHeight()
    assert dialog.milestone_rail.isVisible()
    assert dialog.page_stack.isVisible()
    assert dialog.help_button.isVisible()
    assert dialog.cancel_button.isVisible()
    assert dialog.next_button.isVisible()
    assert dialog.page_stack.width() > dialog.milestone_rail.width()
    assert dialog.page_stack.height() > 300

    dialog.close()
    qapp.processEvents()


def test_phase11_wizard_scale_factor_smoke(qapp):
    scale = float(os.environ.get("QT_SCALE_FACTOR", "1"))
    assert scale in {1.0, 1.25, 1.5}

    dialog = NewProjectDialog()
    dialog.resize(1040, 720)
    dialog.show()
    qapp.processEvents()

    assert dialog.minimumWidth() == 760
    assert dialog.minimumHeight() == 560
    assert dialog.milestone_rail.isVisible()
    assert dialog.page_stack.currentIndex() == 0
    assert dialog.back_button.isVisible()
    assert dialog.next_button.isVisible()
    assert dialog.cancel_button.isVisible()
    assert dialog.validation_status.isVisible()

    dialog.close()
    qapp.processEvents()
