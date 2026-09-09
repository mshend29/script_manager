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
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication, QMainWindow

    from app.google_drive_readiness_controller import (
        GoogleDriveReadinessController,
    )
    from dialogs.google_drive_readiness_dialog import (
        GoogleDriveReadinessDialog,
    )
    from services.windows_prerequisite_service import (
        GoogleDriveInstallationReport,
        GoogleDriveInstallState,
        GoogleDriveReadinessReport,
        GoogleDriveReadinessState,
    )


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


def _installation(*, installed: bool = True):
    return GoogleDriveInstallationReport(
        state=(
            GoogleDriveInstallState.INSTALLED
            if installed
            else GoogleDriveInstallState.NOT_INSTALLED
        ),
        display_name="Google Drive for desktop" if installed else "",
    )


def _report(state: "GoogleDriveReadinessState"):
    installed = state not in {
        GoogleDriveReadinessState.NOT_INSTALLED,
        GoogleDriveReadinessState.UNSUPPORTED_SYSTEM,
    }
    roots = ("R:\\",) if state == GoogleDriveReadinessState.READY else ()
    return GoogleDriveReadinessReport(
        state=state,
        installation=_installation(installed=installed),
        running=state
        in {
            GoogleDriveReadinessState.RUNNING_NOT_READY,
            GoogleDriveReadinessState.READY,
        },
        filesystem_ready=state == GoogleDriveReadinessState.READY,
        drive_roots=roots,
    )


class FakeReadinessService:
    def __init__(self, reports, *, launch_result: bool = True):
        self.reports = list(reports)
        self.launch_result = launch_result
        self.check_count = 0
        self.launch_count = 0

    def check(self):
        index = min(self.check_count, len(self.reports) - 1)
        self.check_count += 1
        return self.reports[index]

    def launch(self) -> bool:
        self.launch_count += 1
        return self.launch_result


def test_dialog_retry_moves_from_not_ready_to_ready(qapp):
    service = FakeReadinessService(
        [
            _report(GoogleDriveReadinessState.RUNNING_NOT_READY),
            _report(GoogleDriveReadinessState.READY),
        ]
    )
    dialog = GoogleDriveReadinessDialog(service=service)

    assert dialog.windowTitle() == "Status Google Drive"
    assert dialog.isModal()
    assert "belum siap" in dialog.status_label.text().casefold()
    assert dialog.open_button.isVisible() is False

    dialog.show()
    qapp.processEvents()
    assert dialog.open_button.isVisible() is True

    dialog.retry_button.click()
    qapp.processEvents()
    assert dialog.status_label.text() == "Siap digunakan"
    assert "R:\\" in dialog.detail_label.text()
    assert dialog.open_button.isVisible() is False

    dialog.close()
    qapp.processEvents()


def test_dialog_can_launch_google_drive_without_credentials(qapp):
    service = FakeReadinessService(
        [_report(GoogleDriveReadinessState.INSTALLED_NOT_RUNNING)]
    )
    dialog = GoogleDriveReadinessDialog(service=service)
    dialog.show()
    qapp.processEvents()

    dialog.open_button.click()
    qapp.processEvents()

    assert service.launch_count == 1
    assert dialog.status_label.text() == "Google Drive dibuka"
    assert "login" in dialog.detail_label.text().casefold()

    dialog.close()
    qapp.processEvents()


def test_controller_adds_help_action_and_only_notices_once_per_version(
    qapp,
    tmp_path,
    monkeypatch,
):
    window = QMainWindow()
    help_menu = window.menuBar().addMenu("&Bantuan")
    help_menu.addAction("Mulai")
    help_menu.addSeparator()
    help_menu.addAction("Periksa Pembaruan")

    settings = QSettings(
        str(tmp_path / "phase12-google-drive.ini"),
        QSettings.Format.IniFormat,
    )
    service = FakeReadinessService(
        [_report(GoogleDriveReadinessState.RUNNING_NOT_READY)]
    )
    controller = GoogleDriveReadinessController(
        window,
        service=service,
        settings=settings,
    )

    action_texts = [action.text() for action in help_menu.actions()]
    assert "Status Google Drive" in action_texts
    assert action_texts.index("Status Google Drive") < action_texts.index(
        "Periksa Pembaruan"
    )

    opened: list[bool] = []
    monkeypatch.setattr(
        controller,
        "open_status",
        lambda: opened.append(True),
    )

    assert controller.show_first_run_if_needed() is True
    assert opened == [True]
    assert controller.show_first_run_if_needed() is False
    assert opened == [True]

    window.close()
    qapp.processEvents()


def test_ready_state_does_not_show_first_run_dialog(qapp, tmp_path, monkeypatch):
    window = QMainWindow()
    window.menuBar().addMenu("&Bantuan")
    settings = QSettings(
        str(tmp_path / "phase12-google-drive-ready.ini"),
        QSettings.Format.IniFormat,
    )
    service = FakeReadinessService(
        [_report(GoogleDriveReadinessState.READY)]
    )
    controller = GoogleDriveReadinessController(
        window,
        service=service,
        settings=settings,
    )

    opened: list[bool] = []
    monkeypatch.setattr(
        controller,
        "open_status",
        lambda: opened.append(True),
    )

    assert controller.show_first_run_if_needed() is False
    assert opened == []
    assert settings.value(controller.notice_key, False, type=bool) is True

    window.close()
    qapp.processEvents()
