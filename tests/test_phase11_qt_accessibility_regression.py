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
    from PySide6.QtWidgets import QApplication, QDialog, QScrollArea

    from dialogs.transactional_new_project_dialog import TransactionalNewProjectDialog
    from services.source_preflight_service import SourcePreflightReport
    from widgets.wizard_milestone_rail import WizardMilestoneState


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


def test_blocking_step_routes_focus_to_first_field(qapp, tmp_path):
    dialog = TransactionalNewProjectDialog()
    dialog.show()
    qapp.processEvents()

    dialog._show_step(0)
    qapp.processEvents()
    assert QApplication.focusWidget() is dialog.project_name

    dialog.project_name.setText("Focus Project")
    dialog.client_name.clear()
    dialog.location_edit.setText(str(tmp_path))
    dialog._show_step(0)
    qapp.processEvents()
    assert QApplication.focusWidget() is dialog.client_name

    dialog.client_name.setText("Client")
    dialog._show_step(1)
    qapp.processEvents()
    assert dialog._step_states[1] == WizardMilestoneState.ERROR
    assert QApplication.focusWidget() is dialog.source_folder

    dialog.close()
    qapp.processEvents()


def test_keyboard_tab_order_and_help_are_reachable(qapp):
    dialog = TransactionalNewProjectDialog()
    dialog.show()
    qapp.processEvents()

    dialog.project_name.setFocus()
    QTest.keyClick(dialog.project_name, Qt.Key.Key_Tab)
    qapp.processEvents()
    assert QApplication.focusWidget() is dialog.project_code

    assert dialog.help_button.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert dialog.help_button.accessibleName() == "Bantuan folder dan Google Drive"

    dialog.close()
    qapp.processEvents()


def test_escape_cancels_wizard_when_no_background_operation_is_running(qapp):
    dialog = TransactionalNewProjectDialog()
    dialog.show()
    qapp.processEvents()
    assert dialog.isVisible()

    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    qapp.processEvents()

    assert dialog.isVisible() is False
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_long_labels_remain_inside_scrollable_wizard_page(qapp, tmp_path):
    dialog = TransactionalNewProjectDialog()
    long_name = "Project " + ("Sangat Panjang " * 20)
    long_location = tmp_path / ("Folder Panjang " * 10)

    dialog.project_name.setText(long_name)
    dialog.location_edit.setText(str(long_location))
    dialog.resize(760, 560)
    dialog.show()
    qapp.processEvents()

    page = dialog.page_stack.currentWidget()
    assert isinstance(page, QScrollArea)
    assert page.widgetResizable() is True
    assert dialog.destination_preview.wordWrap() is True
    assert dialog.validation_status.wordWrap() is True
    assert dialog.cancel_button.isVisible()
    assert dialog.milestone_rail.isVisible()

    dialog.close()
    qapp.processEvents()


def test_preflight_error_details_are_scrollable(qapp):
    dialog = TransactionalNewProjectDialog()
    dialog.show()
    dialog._show_step(1)
    dialog.source_preflight_panel.set_report(
        SourcePreflightReport(
            problems=[
                f"Workbook {index:02d}: detail error yang cukup panjang untuk operator."
                for index in range(40)
            ]
        )
    )
    qapp.processEvents()

    details = dialog.source_preflight_panel.details
    assert details.isReadOnly() is True
    assert details.verticalScrollBar().maximum() > 0

    dialog.close()
    qapp.processEvents()


def test_milestone_state_uses_symbols_not_only_color(qapp):
    dialog = TransactionalNewProjectDialog()
    dialog.show()
    qapp.processEvents()

    dialog.set_step_state(0, WizardMilestoneState.VALID, "siap")
    dialog.set_step_state(1, WizardMilestoneState.WARNING, "warning")
    dialog.set_step_state(2, WizardMilestoneState.ERROR, "error")
    dialog.set_step_state(3, WizardMilestoneState.PENDING, "")
    dialog._show_step(3)
    qapp.processEvents()

    symbols = [item.symbol.text() for item in dialog.milestone_rail.items]
    assert symbols[0] == "✓"
    assert symbols[1] == "⚠"
    assert symbols[2] == "✕"
    assert symbols[3] == "●"

    dialog.close()
    qapp.processEvents()
