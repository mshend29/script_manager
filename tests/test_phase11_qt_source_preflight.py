from __future__ import annotations

import importlib.util
import os
import time

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PYSIDE_AVAILABLE = importlib.util.find_spec("PySide6") is not None

pytestmark = pytest.mark.skipif(
    not PYSIDE_AVAILABLE,
    reason="PySide6 is only installed in the Qt runtime CI job.",
)

if PYSIDE_AVAILABLE:
    from openpyxl import Workbook
    from PySide6.QtWidgets import QApplication

    from dialogs.new_project_dialog import NewProjectDialog
    from widgets.wizard_milestone_rail import WizardMilestoneState


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


def _write_script(path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["IN", "OUT", "DIALOG", "TOKOH", "TALENT"])
    sheet.append(["00:00:01", "00:00:02", "Halo", "INDAH", "Talent A"])
    sheet.append(["00:00:03", "00:00:04", "Apa kabar?", "TEGUH", "Talent B"])
    workbook.save(path)
    workbook.close()


def _prepare_source_step(dialog, tmp_path, qapp, source) -> None:
    dialog.project_name.setText("AA23 Project")
    dialog.project_code.setText("AA23")
    dialog.client_name.setText("Client")
    dialog.location_edit.setText(str(tmp_path / "project"))
    dialog._create_destination_folder()
    dialog._go_next()
    dialog.source_folder.setText(str(source))
    dialog.episode_before.setText("EP")
    dialog.episode_after.setText("_")
    validation = dialog.source_section.validate_source_filenames()
    qapp.processEvents()
    assert validation.is_valid
    assert dialog.current_step == 1
    assert dialog.source_preflight_panel.start_button.isEnabled()


def _wait_for_preflight(dialog, qapp, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if not dialog._preflight_running and dialog.source_preflight_report is not None:
            return
        time.sleep(0.01)
    raise AssertionError("Source preflight tidak selesai dalam runtime test.")


def test_source_preflight_success_enables_milestone_navigation(qapp, tmp_path):
    source = tmp_path / "source"
    _write_script(source / "AA23_EP001_SCRIPT.xlsx")
    _write_script(source / "AA23_EP002_SCRIPT.xlsx")

    dialog = NewProjectDialog()
    _prepare_source_step(dialog, tmp_path, qapp, source)

    dialog.source_preflight_panel.start_button.click()
    qapp.processEvents()
    _wait_for_preflight(dialog, qapp)

    report = dialog.source_preflight_report
    assert report is not None
    assert report.is_valid
    assert report.inspected_files == 2
    assert report.parsed_files == 2
    assert report.parsed_dialogues == 4
    assert dialog._step_states[1] == WizardMilestoneState.VALID
    assert dialog.next_button.isEnabled() is True
    assert "Workbook dapat dibuka (2/2)" in dialog.source_preflight_panel.summary_label.text()
    assert "2 episode siap diimpor" in dialog.source_preflight_panel.summary_label.text()

    dialog.reject()
    dialog.close()
    qapp.processEvents()


def test_source_preflight_corrupt_workbook_keeps_milestone_blocking(qapp, tmp_path):
    source = tmp_path / "source-corrupt"
    _write_script(source / "AA23_EP001_SCRIPT.xlsx")
    corrupt = source / "AA23_EP002_SCRIPT.xlsx"
    corrupt.write_bytes(b"not-an-excel-workbook")

    dialog = NewProjectDialog()
    _prepare_source_step(dialog, tmp_path, qapp, source)

    dialog.source_preflight_panel.start_button.click()
    _wait_for_preflight(dialog, qapp)

    report = dialog.source_preflight_report
    assert report is not None
    assert report.is_valid is False
    assert report.problems
    assert dialog._step_states[1] == WizardMilestoneState.ERROR
    assert dialog.next_button.isEnabled() is False
    assert "AA23_EP002_SCRIPT.xlsx" in dialog.source_preflight_panel.details.toPlainText()
    assert "Workbook tidak dapat dibuka" in dialog.source_preflight_panel.details.toPlainText()

    dialog.reject()
    dialog.close()
    qapp.processEvents()


def test_preflight_panel_exposes_explicit_cancel_action(qapp):
    dialog = NewProjectDialog()
    signals = []
    dialog.source_preflight_panel.cancel_requested.connect(lambda: signals.append(True))

    dialog.source_preflight_panel.set_running(True)
    assert dialog.source_preflight_panel.cancel_button.isHidden() is False
    dialog.source_preflight_panel.cancel_button.click()
    qapp.processEvents()

    assert signals == [True]
    dialog.source_preflight_panel.set_running(False)
    dialog.reject()
    dialog.close()
    qapp.processEvents()
