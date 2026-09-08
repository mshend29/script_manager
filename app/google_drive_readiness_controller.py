from __future__ import annotations

from PySide6.QtCore import QSettings, QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QMenu

from core.version import APP_VERSION
from dialogs.google_drive_readiness_dialog import GoogleDriveReadinessDialog
from services.windows_prerequisite_service import (
    GoogleDriveReadinessService,
    GoogleDriveReadinessState,
)


class GoogleDriveReadinessController(QObject):
    """Own the non-intrusive first-run Google Drive readiness experience."""

    def __init__(
        self,
        window: QMainWindow,
        *,
        service: GoogleDriveReadinessService | None = None,
        settings: QSettings | None = None,
    ) -> None:
        super().__init__(window)
        self.window = window
        self.service = service or GoogleDriveReadinessService()
        self.settings = settings or QSettings(
            "Script Manager",
            "Script Manager",
        )
        self.notice_key = f"google_drive/readiness_notice/{APP_VERSION}"
        self.status_action: QAction | None = None
        self._install_help_action()

    def _install_help_action(self) -> None:
        help_menu = self._find_help_menu()
        if help_menu is None:
            return

        for action in help_menu.actions():
            if action.text().replace("&", "").strip() == "Status Google Drive":
                self.status_action = action
                return

        action = QAction("Status Google Drive", help_menu)
        action.setObjectName("GoogleDriveStatusAction")
        action.triggered.connect(self.open_status)

        before = next(
            (
                candidate
                for candidate in help_menu.actions()
                if candidate.text().replace("&", "").strip()
                == "Periksa Pembaruan"
            ),
            None,
        )
        if before is None:
            help_menu.addAction(action)
        else:
            help_menu.insertAction(before, action)

        self.status_action = action

    def _find_help_menu(self) -> QMenu | None:
        for action in self.window.menuBar().actions():
            menu = action.menu()
            if menu is None:
                continue
            if menu.title().replace("&", "").strip() == "Bantuan":
                return menu
        return None

    def open_status(self) -> GoogleDriveReadinessDialog:
        dialog = GoogleDriveReadinessDialog(
            service=self.service,
            parent=self.window,
        )
        dialog.exec()
        return dialog

    def show_first_run_if_needed(self) -> bool:
        if self._notice_seen():
            return False

        report = self.service.check()
        if report.state == GoogleDriveReadinessState.UNSUPPORTED_SYSTEM:
            return False

        if report.state == GoogleDriveReadinessState.READY:
            self._mark_notice_seen()
            return False

        self.open_status()
        self._mark_notice_seen()
        return True

    def _notice_seen(self) -> bool:
        return bool(self.settings.value(self.notice_key, False, type=bool))

    def _mark_notice_seen(self) -> None:
        self.settings.setValue(self.notice_key, True)
        self.settings.sync()
