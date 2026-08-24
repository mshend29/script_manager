from __future__ import annotations

import webbrowser
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.ribbon import Ribbon
from core.project import PROJECT_FILE_NAME
from core.project_manager import ProjectError, ProjectManager
from dialogs.new_project_dialog import NewProjectDialog
from dialogs.project_settings_dialog import ProjectSettingsDialog
from pages.data_page import DataPage
from pages.dialog_page import DialogPage
from pages.project_page import ProjectPage
from pages.script_page import ScriptPage
from pages.tools_page import ToolsPage
from pages.tracking_page import TrackingPage


class MainWindow(QMainWindow):
    PAGE_ORDER = [
        "PROJECT",
        "SCRIPT",
        "DIALOG",
        "TRACKING",
        "DATA",
        "TOOLS",
    ]

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Script Manager")
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)

        self.project_manager = ProjectManager()

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.ribbon = Ribbon()
        root.addWidget(self.ribbon)

        self.page_stack = QStackedWidget()
        root.addWidget(self.page_stack, 1)

        self.pages = {
            "PROJECT": ProjectPage(),
            "SCRIPT": ScriptPage(),
            "DIALOG": DialogPage(),
            "TRACKING": TrackingPage(),
            "DATA": DataPage(),
            "TOOLS": ToolsPage(),
        }

        for page_name in self.PAGE_ORDER:
            self.page_stack.addWidget(self.pages[page_name])

        self.setCentralWidget(central)

        self.ribbon.tab_changed.connect(self.set_page)
        self.ribbon.action_triggered.connect(
            self.handle_ribbon_action
        )

        project_page = self.pages["PROJECT"]
        project_page.new_button.clicked.connect(self.new_project)
        project_page.open_button.clicked.connect(self.open_project)

        self.statusBar().showMessage("Ready")
        self.set_page("PROJECT")
        self.refresh_project_page()

    def set_page(self, page_name: str) -> None:
        if page_name not in self.pages:
            return

        self.page_stack.setCurrentWidget(self.pages[page_name])
        self.statusBar().showMessage(f"{page_name.title()} page")

    # ------------------------------------------------------------------
    # PROJECT
    # ------------------------------------------------------------------

    def new_project(self) -> None:
        dialog = NewProjectDialog(self)

        if not dialog.exec():
            return

        try:
            project = self.project_manager.create(
                dialog.settings,
                dialog.parent_folder,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "New Project",
                str(exc),
            )
            return

        self.refresh_project_page()
        self.setWindowTitle(
            f"{project.settings.project_name} - Script Manager"
        )
        self.statusBar().showMessage(
            f"Project created: {project.root}",
            5000,
        )

    def open_project(self) -> None:
        start_dir = ""

        if self.project_manager.current:
            start_dir = str(self.project_manager.current.root.parent)

        project_file, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            start_dir,
            "Script Manager Project (project.json);;JSON Files (*.json)",
        )

        if not project_file:
            return

        try:
            project = self.project_manager.open(project_file)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Open Project",
                f"Gagal membuka project.\n\n{exc}",
            )
            return

        self.refresh_project_page()
        self.setWindowTitle(
            f"{project.settings.project_name} - Script Manager"
        )
        self.statusBar().showMessage(
            f"Project opened: {project.root}",
            5000,
        )

    def save_project(self) -> None:
        if not self.project_manager.is_open:
            QMessageBox.information(
                self,
                "Save Project",
                "Belum ada project yang dibuka.",
            )
            return

        try:
            self.project_manager.save()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Save Project",
                f"Gagal menyimpan project.\n\n{exc}",
            )
            return

        self.refresh_project_page()
        self.statusBar().showMessage("Project saved", 3000)

    def close_project(self) -> None:
        if not self.project_manager.is_open:
            return

        try:
            self.project_manager.close()
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Close Project",
                f"Project ditutup, tetapi terjadi error saat save:\n{exc}",
            )

        self.setWindowTitle("Script Manager")
        self.refresh_project_page()
        self.set_page("PROJECT")
        self.statusBar().showMessage("Project closed", 3000)

    def open_project_settings(self) -> None:
        project = self.project_manager.current

        if project is None:
            QMessageBox.information(
                self,
                "Project Settings",
                "Buka atau buat project terlebih dahulu.",
            )
            return

        dialog = ProjectSettingsDialog(
            project.settings,
            self,
        )

        if not dialog.exec():
            return

        try:
            self.project_manager.update_settings(
                dialog.result_settings
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Project Settings",
                f"Gagal menyimpan settings.\n\n{exc}",
            )
            return

        self.refresh_project_page()

        current = self.project_manager.current
        if current:
            self.setWindowTitle(
                f"{current.settings.project_name} - Script Manager"
            )

        self.statusBar().showMessage(
            "Project settings saved",
            3000,
        )

    def open_client_drive(self) -> None:
        project = self.project_manager.current

        if project is None:
            QMessageBox.information(
                self,
                "Client Drive",
                "Buka atau buat project terlebih dahulu.",
            )
            return

        url = project.settings.main_drive_url.strip()

        if not url:
            QMessageBox.information(
                self,
                "Client Drive",
                "Main Drive URL belum diisi di Project Settings.",
            )
            return

        webbrowser.open(url)

    def refresh_project_page(self) -> None:
        page = self.pages["PROJECT"]
        project = self.project_manager.current

        if project is None:
            page.reset_view()
            return

        settings = project.settings

        page.project_name.setText(
            settings.project_name or "Unnamed Project"
        )
        page.project_location.setText(
            f"Location: {project.root}"
        )
        page.source_path.setText(
            f"Source: {settings.source_folder or '-'}"
        )
        page.start_date.setText(
            f"Start date: {settings.start_date or '-'}"
        )
        page.last_refresh.setText("Last refresh: -")

        try:
            counts = self.project_manager.get_dashboard_counts()
        except Exception:
            counts = {}

        page.set_counts(counts)

        page.info_title.setText(
            f"{settings.project_name or 'Project'} ready"
        )
        page.info_text.setText(
            "Project system dan SQLite sudah aktif. "
            "Tahap berikutnya adalah Import Source / Refresh Data otomatis."
        )

    # ------------------------------------------------------------------
    # RIBBON
    # ------------------------------------------------------------------

    def handle_ribbon_action(self, action_id: str) -> None:
        handlers = {
            "project.new": self.new_project,
            "project.open": self.open_project,
            "project.save": self.save_project,
            "project.settings": self.open_project_settings,
            "project.close": self.close_project,
            "client.drive": self.open_client_drive,

            "dialog.check_all": (
                lambda: self.pages["DIALOG"].set_all_checked(True)
            ),
            "dialog.uncheck_all": (
                lambda: self.pages["DIALOG"].set_all_checked(False)
            ),
        }

        handler = handlers.get(action_id)

        if handler:
            handler()
            return

        self.statusBar().showMessage(
            f"Action: {action_id}",
            3000,
        )

    def closeEvent(self, event) -> None:
        if self.project_manager.is_open:
            try:
                self.project_manager.save()
            except Exception:
                pass

        event.accept()
