from __future__ import annotations

import webbrowser
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.ribbon import Ribbon
from app.source_sync_worker import SourceSyncWorker
from core.project_manager import ProjectManager
from dialogs.new_project_dialog import NewProjectDialog
from dialogs.project_settings_dialog import ProjectSettingsDialog
from import_engine.source_sync import (
    SourceSyncEngine,
    SourceSyncReport,
)
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
        self.source_sync_engine = SourceSyncEngine()
        self._source_sync_thread: QThread | None = None
        self._source_sync_worker: SourceSyncWorker | None = None
        self._source_sync_title = ""

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
        self.ribbon.action_triggered.connect(self.handle_ribbon_action)

        project_page = self.pages["PROJECT"]
        project_page.new_button.clicked.connect(self.new_project)
        project_page.open_button.clicked.connect(self.open_project)

        tracking_page = self.pages["TRACKING"]
        tracking_page.drive_button.clicked.connect(self.open_client_drive)

        self.statusBar().showMessage("Ready")
        self.set_page("PROJECT")
        self.refresh_project_page()

    def set_page(self, page_name: str) -> None:
        if page_name not in self.pages:
            return

        project = self.project_manager.current
        database = project.database if project is not None else None

        if page_name == "SCRIPT":
            self.pages["SCRIPT"].set_database(database)

        elif page_name == "DIALOG":
            self.pages["DIALOG"].set_database(database)

        elif page_name == "TRACKING":
            self.pages["TRACKING"].set_database(database)

        elif page_name == "DATA":
            self.pages["DATA"].set_database(database)

        self.page_stack.setCurrentWidget(self.pages[page_name])
        self.statusBar().showMessage(f"{page_name.title()} page")

    # ------------------------------------------------------------------
    # PROJECT
    # ------------------------------------------------------------------

    def new_project(self) -> None:
        if self._block_project_change_during_sync("New Project"):
            return

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

        self._clear_data_pages()
        self.refresh_project_page()
        self.setWindowTitle(
            f"{project.settings.project_name} - Script Manager"
        )
        self.statusBar().showMessage(
            f"Project created: {project.root}",
            5000,
        )

    def open_project(self) -> None:
        if self._block_project_change_during_sync("Open Project"):
            return

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

        self._clear_data_pages()
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
        if self._block_project_change_during_sync("Close Project"):
            return

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

        self._clear_data_pages()
        self.setWindowTitle("Script Manager")
        self.refresh_project_page()
        self.set_page("PROJECT")
        self.statusBar().showMessage("Project closed", 3000)

    def _clear_data_pages(self) -> None:
        self.pages["SCRIPT"].set_database(None)
        self.pages["DIALOG"].set_database(None)
        self.pages["TRACKING"].set_database(None)
        self.pages["DATA"].set_database(None)

    def open_project_settings(self) -> None:
        if self._block_project_change_during_sync("Project Settings"):
            return

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

    def _source_sync_running(self) -> bool:
        thread = self._source_sync_thread
        return thread is not None and thread.isRunning()

    def _block_project_change_during_sync(self, action_title: str) -> bool:
        if not self._source_sync_running():
            return False

        QMessageBox.information(
            self,
            action_title,
            "Source Import/Refresh sedang berjalan. "
            "Project tidak dapat diganti sampai proses selesai.",
        )
        return True

    # ------------------------------------------------------------------
    # SOURCE IMPORT / REFRESH
    # ------------------------------------------------------------------

    def import_source(self) -> None:
        self._run_source_sync("Import Source")

    def refresh_source(self) -> None:
        self._run_source_sync("Refresh Data")

    def _run_source_sync(self, title: str) -> None:
        if self._source_sync_running():
            self.statusBar().showMessage(
                f"{self._source_sync_title or 'Source sync'} masih berjalan",
                3000,
            )
            return

        project = self.project_manager.current

        if project is None:
            QMessageBox.information(
                self,
                title,
                "Buka atau buat project terlebih dahulu.",
            )
            return

        if not project.settings.source_folder.strip():
            QMessageBox.information(
                self,
                title,
                (
                    "Source Folder belum diisi.\n\n"
                    "Isi melalui PROJECT → Project Settings."
                ),
            )
            return

        thread = QThread(self)
        worker = SourceSyncWorker(self.source_sync_engine, project)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.completed.connect(
            self._source_sync_completed,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.failed.connect(
            self._source_sync_failed,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._source_sync_thread_finished)

        self._source_sync_thread = thread
        self._source_sync_worker = worker
        self._source_sync_title = title
        self.statusBar().showMessage(
            f"{title} berjalan — aplikasi tetap dapat digunakan"
        )
        thread.start()

    @Slot(object)
    def _source_sync_completed(self, report: SourceSyncReport) -> None:
        title = self._source_sync_title or "Source Sync"
        project = self.project_manager.current

        if project is None:
            self.statusBar().showMessage(
                f"{title} selesai, tetapi project sudah tidak tersedia",
                5000,
            )
            return

        if report.has_errors:
            self._show_source_sync_errors(title, report)
            self.statusBar().showMessage(
                f"{title} selesai dengan masalah",
                5000,
            )
            return

        self.refresh_project_page()
        self._refresh_current_data_page(project)

        QMessageBox.information(
            self,
            title,
            "Source scan selesai.\n\n" + report.summary(),
        )

        self.statusBar().showMessage(
            f"{title} selesai — {report.scanned} file",
            5000,
        )

    @Slot(object)
    def _source_sync_failed(self, exc: object) -> None:
        title = self._source_sync_title or "Source Sync"
        QMessageBox.critical(
            self,
            title,
            f"Gagal membaca Source Folder.\n\n{exc}",
        )
        self.statusBar().showMessage(f"{title} gagal", 5000)

    @Slot()
    def _source_sync_thread_finished(self) -> None:
        self._source_sync_thread = None
        self._source_sync_worker = None
        self._source_sync_title = ""

    def _refresh_current_data_page(self, project) -> None:
        current_page = self.page_stack.currentWidget()

        if current_page is self.pages["SCRIPT"]:
            self.pages["SCRIPT"].set_database(project.database)

        elif current_page is self.pages["DIALOG"]:
            self.pages["DIALOG"].set_database(project.database)

        elif current_page is self.pages["TRACKING"]:
            self.pages["TRACKING"].set_database(project.database)

        elif current_page is self.pages["DATA"]:
            self.pages["DATA"].set_database(project.database)

    def _show_source_sync_errors(
        self,
        title: str,
        report: SourceSyncReport,
    ) -> None:
        sections: list[str] = []

        if report.problems:
            sections.append(
                "FILE YANG TIDAK DAPAT DIPROSES:\n"
                + "\n".join(
                    f"• {item}" for item in report.problems
                )
            )

        if report.duplicate_episodes:
            duplicate_lines: list[str] = []

            for episode, paths in sorted(
                report.duplicate_episodes.items()
            ):
                duplicate_lines.append(f"Episode {episode}:")
                duplicate_lines.extend(
                    f"  • {Path(path).name}"
                    for path in paths
                )

            sections.append(
                "DUPLICATE EPISODE:\n"
                + "\n".join(duplicate_lines)
            )

        QMessageBox.warning(
            self,
            title,
            (
                "Database tidak diubah karena ditemukan masalah."
                "\n\n"
                + "\n\n".join(sections)
            ),
        )

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

        try:
            last_sync = self.source_sync_engine.get_last_sync_at(
                project
            )
        except Exception:
            last_sync = ""

        page.last_refresh.setText(
            f"Last refresh: {last_sync or '-'}"
        )

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
            "Source Import / Refresh scanner sudah terhubung."
        )

    # ------------------------------------------------------------------
    # VIEW ACTIONS
    # ------------------------------------------------------------------

    def refresh_data_view(self, page_name: str) -> None:
        project = self.project_manager.current
        if project is None:
            QMessageBox.information(
                self,
                "Refresh View",
                "Buka atau buat project terlebih dahulu.",
            )
            return

        page = self.pages.get(page_name)
        if page is None or not hasattr(page, "set_database"):
            return

        page.set_database(project.database)
        self.statusBar().showMessage(f"{page_name.title()} view refreshed", 3000)

    def focus_script_search(self) -> None:
        page = self.pages["SCRIPT"]
        page.search_edit.setFocus()
        page.search_edit.selectAll()
        self.statusBar().showMessage("Script search focused", 2000)

    def open_dialog_source(self) -> None:
        page = self.pages["DIALOG"]
        if not page.open_source_button.isEnabled():
            self.statusBar().showMessage(
                "Pilih character dan episode yang memiliki source file.",
                3000,
            )
            return

        page.open_source_button.click()

    # ------------------------------------------------------------------
    # DATA ADMIN
    # ------------------------------------------------------------------

    def show_data_section(self, section: str) -> None:
        project = self.project_manager.current
        if project is None:
            QMessageBox.information(
                self,
                "Data",
                "Buka atau buat project terlebih dahulu.",
            )
            return

        self.pages["DATA"].set_database(project.database)
        self.pages["DATA"].show_section(section)

    def validate_data(self) -> None:
        project = self.project_manager.current
        if project is None:
            QMessageBox.information(
                self,
                "Validate Database",
                "Buka atau buat project terlebih dahulu.",
            )
            return

        page = self.pages["DATA"]
        page.set_database(project.database)
        try:
            issues = page.run_validation()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Validate Database",
                f"Validation gagal.\n\n{exc}",
            )
            return

        errors = sum(1 for issue in issues if issue.severity == "ERROR")
        warnings = sum(1 for issue in issues if issue.severity == "WARNING")
        if issues:
            QMessageBox.warning(
                self,
                "Validate Database",
                f"Validation selesai: {errors} error, {warnings} warning.",
            )
        else:
            QMessageBox.information(
                self,
                "Validate Database",
                "Validation passed. Tidak ada issue.",
            )

    def backup_database(self) -> None:
        project = self.project_manager.current
        if project is None:
            QMessageBox.information(
                self,
                "Backup Database",
                "Buka atau buat project terlebih dahulu.",
            )
            return

        page = self.pages["DATA"]
        page.set_database(project.database)
        try:
            backup_path = page.backup_database()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Backup Database",
                f"Backup gagal.\n\n{exc}",
            )
            return

        QMessageBox.information(
            self,
            "Backup Database",
            f"Backup tersimpan:\n{backup_path}",
        )

    def rebuild_data_indexes(self) -> None:
        project = self.project_manager.current
        if project is None:
            QMessageBox.information(
                self,
                "Rebuild Index",
                "Buka atau buat project terlebih dahulu.",
            )
            return

        page = self.pages["DATA"]
        page.set_database(project.database)
        try:
            page.rebuild_indexes()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Rebuild Index",
                f"Rebuild index gagal.\n\n{exc}",
            )
            return

        self.statusBar().showMessage("Database indexes rebuilt", 3000)
        QMessageBox.information(
            self,
            "Rebuild Index",
            "SQLite REINDEX + ANALYZE selesai. Data tidak dihapus.",
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
            "source.import": self.import_source,
            "source.refresh": self.refresh_source,
            "script.refresh": lambda: self.refresh_data_view("SCRIPT"),
            "script.search": self.focus_script_search,
            "dialog.refresh": lambda: self.refresh_data_view("DIALOG"),
            "dialog.open_source": self.open_dialog_source,
            "dialog.check_all": (
                lambda: self.pages["DIALOG"].set_all_checked(True)
            ),
            "dialog.uncheck_all": (
                lambda: self.pages["DIALOG"].set_all_checked(False)
            ),
            "tracking.refresh": lambda: self.refresh_data_view("TRACKING"),
            "tracking.open_drive": self.open_client_drive,
            "data.refresh": self.refresh_source,
            "data.rebuild": self.rebuild_data_indexes,
            "data.characters": lambda: self.show_data_section("characters"),
            "data.talents": lambda: self.show_data_section("talents"),
            "data.cast": lambda: self.show_data_section("cast"),
            "data.validate": self.validate_data,
            "data.backup": self.backup_database,
        }

        handler = handlers.get(action_id)

        if handler:
            handler()
            return

        self.statusBar().showMessage(
            f"Action unavailable: {action_id}",
            3000,
        )

    def closeEvent(self, event) -> None:
        if self._source_sync_running():
            event.ignore()
            QMessageBox.information(
                self,
                "Source Sync",
                "Source Import/Refresh sedang berjalan. "
                "Aplikasi tetap terbuka untuk menjaga proses database tetap aman.",
            )
            return

        if self.project_manager.is_open:
            try:
                self.project_manager.save()
            except Exception:
                pass

        event.accept()