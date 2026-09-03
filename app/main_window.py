from __future__ import annotations

import webbrowser
from pathlib import Path

from PySide6.QtCore import QThread, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.project_data_state import DATA_PAGE_NAMES, ProjectDataRevisionState
from app.source_sync_controller import SourceSyncController
from app.update_check_worker import UpdateCheckWorker
from core.app_paths import project_backups_dir
from core.project_manager import ProjectManager
from core.recent_projects import RecentProjectsStore
from core.version import APP_VERSION
from dialogs.new_project_dialog import NewProjectDialog
from dialogs.project_settings_dialog import ProjectSettingsDialog
from dialogs.source_refresh_preview_dialog import SourceRefreshPreviewDialog
from import_engine.source_sync import (
    SourceSyncEngine,
    SourceSyncProgress,
    SourceSyncReport,
)
from pages.data_alias_page import AliasDataPage as DataPage
from pages.dialog_page import DialogPage
from pages.help_page import HelpPage
from pages.project_page import ProjectPage
from pages.script_page import ScriptPage
from pages.tools_page import ToolsPage
from pages.tracking_compact_page import CompactTrackingPage as TrackingPage
from services.application_info_service import ApplicationInfoService
from services.backup_service import BackupService
from services.problem_report_service import ProblemReportService
from services.project_dashboard_service import ProjectDashboardService
from widgets.page_header import PageHeader
from widgets.sidebar_nav import SidebarNavigation


class MainWindow(QMainWindow):
    project_data_changed = Signal(int)

    PAGE_ORDER = [
        "PROJECT",
        "SCRIPT",
        "DIALOG",
        "TRACKING",
        "DATA",
        "TOOLS",
        "HELP",
    ]

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Script Manager")
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)

        self.project_manager = ProjectManager()
        self.recent_projects = RecentProjectsStore()
        self.source_sync_engine = SourceSyncEngine()
        self.source_sync_controller = SourceSyncController(
            self.source_sync_engine,
            self,
        )
        self._project_data_state = ProjectDataRevisionState()
        self._update_check_thread: QThread | None = None
        self._update_check_worker: UpdateCheckWorker | None = None

        central = QWidget()
        central.setObjectName("AppShell")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = SidebarNavigation()
        root.addWidget(self.sidebar)

        workspace = QWidget()
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)

        self.page_header = PageHeader()
        workspace_layout.addWidget(self.page_header)

        self.page_stack = QStackedWidget()
        workspace_layout.addWidget(self.page_stack, 1)

        root.addWidget(workspace, 1)

        self.pages = {
            "PROJECT": ProjectPage(),
            "SCRIPT": ScriptPage(),
            "DIALOG": DialogPage(),
            "TRACKING": TrackingPage(),
            "DATA": DataPage(),
            "TOOLS": ToolsPage(),
            "HELP": HelpPage(),
        }

        for page_name in self.PAGE_ORDER:
            self.page_stack.addWidget(self.pages[page_name])

        self.setCentralWidget(central)

        self.sidebar.page_requested.connect(self.set_page)
        self.page_header.action_requested.connect(self.handle_ribbon_action)

        project_page = self.pages["PROJECT"]
        project_page.new_button.clicked.connect(self.new_project)
        project_page.open_button.clicked.connect(self.open_project)
        project_page.action_requested.connect(
            self.handle_project_dashboard_action
        )

        tracking_page = self.pages["TRACKING"]
        tracking_page.drive_button.clicked.connect(self.open_client_drive)

        data_page = self.pages["DATA"]
        data_page.tracking_navigation_requested.connect(self.open_tracking_scope)

        for page_name in ("DIALOG", "TRACKING", "DATA"):
            page = self.pages[page_name]
            if hasattr(page, "data_changed"):
                page.data_changed.connect(
                    lambda page_name=page_name:
                        self._workspace_data_changed(page_name)
                )

        self.project_data_changed.connect(
            self._project_data_revision_changed
        )

        tools_page = self.pages["TOOLS"]
        tools_page.action_requested.connect(self.handle_ribbon_action)

        help_page = self.pages["HELP"]
        help_page.action_requested.connect(self.handle_ribbon_action)
        help_page.release_requested.connect(self.open_update_release)
        help_page.issue_requested.connect(self.open_problem_issue)

        self.source_sync_controller.progress.connect(
            self._source_sync_progress
        )
        self.source_sync_controller.prepared.connect(
            self._source_sync_prepared
        )
        self.source_sync_controller.applied.connect(
            self._source_sync_applied
        )
        self.source_sync_controller.failed.connect(
            self._source_sync_failed
        )
        self.source_sync_controller.phase_started.connect(
            self._source_sync_phase_started
        )

        self._init_source_sync_progress_ui()
        self._init_keyboard_shortcuts()
        self.statusBar().showMessage("Ready")
        self.set_page("PROJECT")
        self.refresh_project_page()

    def _init_keyboard_shortcuts(self) -> None:
        self._keyboard_shortcuts: list[QShortcut] = []

        bindings = (
            ("Ctrl+N", self.new_project),
            ("Ctrl+O", self.open_project),
            ("Ctrl+S", self.save_project),
            ("Ctrl+Shift+S", self.save_project_as),
            ("Ctrl+W", self.close_project),
            ("Ctrl+F", self.open_script_search),
            ("F5", self.sync_source),
            ("F1", self.open_getting_started),
        )

        for sequence, handler in bindings:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(handler)
            self._keyboard_shortcuts.append(shortcut)

    def set_page(self, page_name: str) -> None:
        if page_name not in self.pages:
            return

        project = self.project_manager.current

        if page_name in DATA_PAGE_NAMES:
            self._refresh_data_page_if_needed(page_name, project)

        elif page_name == "TOOLS":
            self.pages["TOOLS"].set_project(project)

        self.page_stack.setCurrentWidget(self.pages[page_name])
        self.sidebar.select_page(page_name)
        self.page_header.set_page(page_name)
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
        self._project_data_state.reset(mark_dirty=True)
        self.refresh_project_page()
        self.setWindowTitle(
            f"{project.settings.project_name} - Script Manager"
        )
        self._record_recent_project(project)
        self.statusBar().showMessage(
            f"Project created: {project.project_file}",
            5000,
        )

    def open_project(self) -> None:
        if self._block_project_change_during_sync("Open Project"):
            return

        start_dir = ""

        if self.project_manager.current:
            start_dir = str(
                self.project_manager.current.project_file.parent
            )

        project_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Script Management Project",
            start_dir,
            "Script Management Project (*.smproj);;All Files (*)",
        )

        if not project_path:
            return

        self.open_project_path(project_path)

    def open_project_path(
        self,
        project_path: str | Path,
        *,
        show_errors: bool = True,
    ) -> bool:
        if self._source_sync_running():
            if show_errors:
                QMessageBox.information(
                    self,
                    "Open Project",
                    "Sync Source sedang berjalan.",
                )
            return False

        try:
            project = self.project_manager.open(project_path)
        except Exception as exc:
            if show_errors:
                QMessageBox.critical(
                    self,
                    "Open Project",
                    f"Gagal membuka project.\n\n{exc}",
                )
            return False

        self._clear_data_pages()
        self._project_data_state.reset(mark_dirty=True)
        self.refresh_project_page()
        self.setWindowTitle(
            f"{project.settings.project_name} - Script Manager"
        )
        self._record_recent_project(project)
        self.statusBar().showMessage(
            f"Project opened: {project.project_file}",
            5000,
        )
        return True

    def open_recent_project(self) -> None:
        if self._block_project_change_during_sync("Open Recent"):
            return

        recent = self.recent_projects.list(existing_only=True)
        if not recent:
            QMessageBox.information(
                self,
                "Open Recent",
                "Belum ada recent project yang masih tersedia.",
            )
            return

        labels = [
            f"{item.project_name or Path(item.file_path).stem} — {item.file_path}"
            for item in recent
        ]
        selected, accepted = QInputDialog.getItem(
            self,
            "Open Recent",
            "Recent Projects",
            labels,
            0,
            False,
        )
        if not accepted or not selected:
            return

        index = labels.index(selected)
        self.open_project_path(recent[index].file_path)

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
        current = self.project_manager.current
        if current is not None:
            self._record_recent_project(current)
        self.statusBar().showMessage("Project saved", 3000)

    def save_project_as(self) -> None:
        if self._block_project_change_during_sync("Save Project As"):
            return

        project = self.project_manager.current
        if project is None:
            QMessageBox.information(
                self,
                "Save Project As",
                "Buka atau buat project terlebih dahulu.",
            )
            return

        default_path = project.project_file.with_name(
            f"{project.project_file.stem} Copy.smproj"
        )
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project As",
            str(default_path),
            "Script Management Project (*.smproj)",
        )
        if not target:
            return

        old_path = project.project_file
        try:
            saved = self.project_manager.save_as(target)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Save Project As",
                f"Save As gagal.\n\n{exc}",
            )
            return

        self.recent_projects.replace_project_path(
            project_id=saved.project_id,
            old_path=old_path,
            new_path=saved.project_file,
            project_name=saved.settings.project_name,
        )
        self._refresh_after_project_switch(saved)
        self.statusBar().showMessage(
            f"Project saved as: {saved.project_file}",
            5000,
        )

    def duplicate_project(self) -> None:
        if self._block_project_change_during_sync("Duplicate Project"):
            return

        project = self.project_manager.current
        if project is None:
            QMessageBox.information(
                self,
                "Duplicate Project",
                "Buka atau buat project terlebih dahulu.",
            )
            return

        default_path = project.project_file.with_name(
            f"{project.project_file.stem} Copy.smproj"
        )
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Duplicate Project",
            str(default_path),
            "Script Management Project (*.smproj)",
        )
        if not target:
            return

        try:
            duplicated = self.project_manager.duplicate(target)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Duplicate Project",
                f"Duplicate gagal.\n\n{exc}",
            )
            return

        self._record_recent_project(duplicated)
        self._refresh_after_project_switch(duplicated)
        self.statusBar().showMessage(
            f"Duplicate opened: {duplicated.project_file}",
            5000,
        )

    def recover_project(self) -> None:
        if self._block_project_change_during_sync("Recover Project"):
            return

        recent = self.recent_projects.list(existing_only=False)
        if not recent:
            QMessageBox.information(
                self,
                "Recover Project",
                "Belum ada project history untuk mencari backup.",
            )
            return

        candidates = []
        for item in recent:
            backup_dir = project_backups_dir(item.project_id)
            backups = sorted(
                backup_dir.glob("*.smproj"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            ) if backup_dir.is_dir() else []
            if backups:
                candidates.append((item, backups))

        if not candidates:
            QMessageBox.information(
                self,
                "Recover Project",
                "Tidak ada backup .smproj yang tersedia.",
            )
            return

        labels = [
            (
                f"{item.project_name or Path(item.file_path).stem} "
                f"({len(backups)} backup)"
            )
            for item, backups in candidates
        ]
        selected, accepted = QInputDialog.getItem(
            self,
            "Recover Project",
            "Project",
            labels,
            0,
            False,
        )
        if not accepted or not selected:
            return

        item, backups = candidates[labels.index(selected)]
        backup_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Recovery Backup",
            str(backups[0].parent),
            "Script Management Project Backup (*.smproj)",
        )
        if not backup_path:
            return

        original = Path(item.file_path).expanduser()
        default_target = (
            original
            if not original.exists()
            else original.with_name(f"{original.stem} Recovered.smproj")
        )
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Save Recovered Project",
            str(default_target),
            "Script Management Project (*.smproj)",
        )
        if not target:
            return

        try:
            recovered = self.project_manager.recover_from_backup(
                backup_path,
                target,
                expected_project_id=item.project_id,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Recover Project",
                f"Recovery gagal.\n\n{exc}",
            )
            return

        self._record_recent_project(recovered)
        self._refresh_after_project_switch(recovered)
        QMessageBox.information(
            self,
            "Recover Project",
            (
                "Project berhasil direcover.\n\n"
                f"{recovered.project_file}"
            ),
        )

    def _record_recent_project(self, project) -> None:
        try:
            self.recent_projects.add(
                project_id=project.project_id,
                project_name=project.settings.project_name,
                file_path=project.project_file,
            )
        except Exception:
            pass

    def _refresh_after_project_switch(self, project) -> None:
        self._clear_data_pages()
        self._project_data_state.reset(mark_dirty=True)
        self.refresh_project_page()
        self.setWindowTitle(
            f"{project.settings.project_name} - Script Manager"
        )
        self.pages["TOOLS"].set_project(
            project,
            run_diagnostics=False,
        )

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
        self.pages["TOOLS"].set_project(None)
        self._project_data_state.reset(mark_dirty=False)

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

    # ------------------------------------------------------------------
    # TOOLS / MAINTENANCE
    # ------------------------------------------------------------------

    def run_tools_diagnostics(self) -> None:
        project = self.project_manager.current
        if project is None:
            QMessageBox.information(
                self,
                "Project Diagnostics",
                "Buka atau buat project terlebih dahulu.",
            )
            return

        self.sidebar.select_tab("TOOLS")
        page = self.pages["TOOLS"]
        page.set_project(project, run_diagnostics=False)
        page.refresh_view()
        self.statusBar().showMessage("Project diagnostics refreshed", 3000)

    def focus_tools_audit(self) -> None:
        project = self.project_manager.current
        if project is None:
            QMessageBox.information(
                self,
                "Audit History",
                "Buka atau buat project terlebih dahulu.",
            )
            return

        self.sidebar.select_tab("TOOLS")
        page = self.pages["TOOLS"]
        page.set_project(project, run_diagnostics=False)
        page.audit_table.setFocus()
        if page.audit_table.rowCount() > 0:
            page.audit_table.selectRow(0)

    def open_tools_path(self, kind: str) -> None:
        project = self.project_manager.current
        if project is None:
            QMessageBox.information(
                self,
                "Open Folder",
                "Buka atau buat project terlebih dahulu.",
            )
            return

        project.ensure_structure()
        settings = project.settings
        paths = {
            "project": project.project_file.parent,
            "source": Path(settings.source_folder)
                if settings.source_folder.strip()
                else None,
            "output": Path(settings.stem_output_folder)
                if settings.stem_output_folder.strip()
                else None,
            "delivery": Path(settings.delivery_folder)
                if settings.delivery_folder.strip()
                else None,
            "backups": project.backups_folder,
            "logs": project.logs_folder,
        }
        path = paths.get(str(kind).strip().casefold())

        if path is None:
            QMessageBox.information(
                self,
                "Open Folder",
                "Folder belum dikonfigurasi di Project Settings.",
            )
            return

        path = Path(path)
        if not path.is_dir():
            QMessageBox.warning(
                self,
                "Open Folder",
                f"Folder tidak ditemukan:\n{path}",
            )
            return

        opened = QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(path.resolve()))
        )
        if not opened:
            QMessageBox.warning(
                self,
                "Open Folder",
                f"Sistem tidak dapat membuka folder:\n{path}",
            )

    def open_tools_drive(self, kind: str) -> None:
        project = self.project_manager.current
        if project is None:
            QMessageBox.information(
                self,
                "Drive Link",
                "Buka atau buat project terlebih dahulu.",
            )
            return

        settings = project.settings
        urls = {
            "main": settings.main_drive_url,
            "material": settings.material_drive_url,
            "delivery": settings.delivery_drive_url,
        }
        url = str(urls.get(str(kind).strip().casefold(), "") or "").strip()
        if not url:
            QMessageBox.information(
                self,
                "Drive Link",
                "Drive URL belum dikonfigurasi di Project Settings.",
            )
            return

        webbrowser.open(url)

    def restore_database_backup(self) -> None:
        if self._block_project_change_during_sync("Restore Backup"):
            return

        project = self.project_manager.current
        if project is None:
            QMessageBox.information(
                self,
                "Restore Backup",
                "Buka atau buat project terlebih dahulu.",
            )
            return

        project.ensure_structure()
        backup_path, _ = QFileDialog.getOpenFileName(
            self,
            "Restore Database Backup",
            str(project.backups_folder),
            "Script Management Project Backup (*.smproj);;All Files (*)",
        )
        if not backup_path:
            return

        service = BackupService(project.database)
        valid, detail = service.validate_backup(backup_path)
        if not valid:
            QMessageBox.critical(
                self,
                "Restore Backup",
                detail,
            )
            return

        answer = QMessageBox.question(
            self,
            "Restore Backup",
            (
                f"{detail}\n\n"
                f"Restore database dari:\n{backup_path}\n\n"
                "Current database akan dibackup otomatis terlebih dahulu. "
                "Source files dan audio files tidak diubah.\n\n"
                "Lanjutkan restore?"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            safety_backup, schema = service.restore(backup_path)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Restore Backup",
                f"Restore gagal.\n\n{exc}",
            )
            return

        self._clear_data_pages()
        self.refresh_project_page()
        self.pages["TOOLS"].set_project(project)
        self.statusBar().showMessage("Database backup restored", 5000)

        QMessageBox.information(
            self,
            "Restore Backup",
            (
                "Database berhasil direstore.\n\n"
                f"Schema aktif: v{schema}\n"
                f"Safety backup current database:\n{safety_backup}"
            ),
        )

    def _source_sync_running(self) -> bool:
        return self.source_sync_controller.is_running

    def _block_project_change_during_sync(self, action_title: str) -> bool:
        if not self._source_sync_running():
            return False

        QMessageBox.information(
            self,
            action_title,
            "Sync Source sedang berjalan. "
            "Project tidak dapat diganti sampai proses selesai.",
        )
        return True

    def _init_source_sync_progress_ui(self) -> None:
        self._source_sync_progress_label = QLabel()
        self._source_sync_progress_label.setMaximumWidth(360)
        self._source_sync_progress_label.hide()

        self._source_sync_progress_bar = QProgressBar()
        self._source_sync_progress_bar.setFixedWidth(180)
        self._source_sync_progress_bar.setTextVisible(True)
        self._source_sync_progress_bar.hide()

        self.statusBar().addPermanentWidget(
            self._source_sync_progress_label,
        )
        self.statusBar().addPermanentWidget(
            self._source_sync_progress_bar,
        )

    def _hide_source_sync_progress(self) -> None:
        self._source_sync_progress_label.clear()
        self._source_sync_progress_label.setToolTip("")
        self._source_sync_progress_label.hide()
        self._source_sync_progress_bar.reset()
        self._source_sync_progress_bar.hide()

    @Slot(object)
    def _source_sync_progress(self, progress: SourceSyncProgress) -> None:
        message = progress.message or progress.stage.replace("_", " ").title()
        self._source_sync_progress_label.setText(message)
        self._source_sync_progress_label.setToolTip(progress.file_name)

        if progress.is_determinate:
            self._source_sync_progress_bar.setRange(0, progress.total)
            self._source_sync_progress_bar.setValue(
                min(max(progress.current, 0), progress.total)
            )
            self._source_sync_progress_bar.setFormat("%v/%m")
        else:
            self._source_sync_progress_bar.setRange(0, 0)
            self._source_sync_progress_bar.setFormat("")

        self._source_sync_progress_label.show()
        self._source_sync_progress_bar.show()

    # ------------------------------------------------------------------
    # SOURCE SYNC
    # ------------------------------------------------------------------

    def sync_source(self) -> None:
        self._run_source_sync("Sync Source")

    def _run_source_sync(self, title: str) -> None:
        if self._source_sync_running():
            active_title = self.source_sync_controller.title or "Source Sync"
            self.statusBar().showMessage(
                f"{active_title} masih berjalan",
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

        self.source_sync_controller.start_prepare(
            project,
            title=title,
        )

    @Slot(str, str)
    def _source_sync_phase_started(
        self,
        title: str,
        operation: str,
    ) -> None:
        phase_text = (
            "preparing preview"
            if operation == "prepare"
            else "applying changes"
        )
        self.statusBar().showMessage(
            f"{title} — {phase_text}; aplikasi tetap dapat digunakan"
        )

    @Slot(str, object)
    def _source_sync_prepared(
        self,
        title: str,
        report: SourceSyncReport,
    ) -> None:
        project = self.project_manager.current
        self._hide_source_sync_progress()

        if project is None:
            self.statusBar().showMessage(
                f"{title} preview selesai, tetapi project sudah tidak tersedia",
                5000,
            )
            return

        if report.has_errors:
            self._show_source_sync_errors(title, report)
            self.statusBar().showMessage(
                f"{title} preview selesai dengan masalah",
                5000,
            )
            return

        preview = report.preview
        if preview is None:
            QMessageBox.critical(
                self,
                title,
                "Source preview tidak dapat dibuat.",
            )
            return

        dialog = SourceRefreshPreviewDialog(
            preview,
            warnings=report.warnings,
            parent=self,
        )
        accepted = bool(dialog.exec())

        if not accepted:
            self.statusBar().showMessage(
                f"{title} dibatalkan — database tidak diubah",
                5000,
            )
            return

        if not preview.has_changes:
            self.statusBar().showMessage(
                f"{title}: tidak ada perubahan source",
                5000,
            )
            return

        self.source_sync_controller.apply_after_prepare(
            project,
            report,
            title=title,
        )
        self.statusBar().showMessage(
            "Preview disetujui — menunggu apply phase...",
            3000,
        )

    @Slot(str, object)
    def _source_sync_applied(
        self,
        title: str,
        report: SourceSyncReport,
    ) -> None:
        project = self.project_manager.current
        self._hide_source_sync_progress()

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

        revision = self._project_data_state.mark_changed()
        self.project_data_changed.emit(revision)

        backup_text = (
            f"\n\nSafety backup:\n{report.backup_path}"
            if report.backup_path
            else ""
        )
        QMessageBox.information(
            self,
            title,
            "Source refresh berhasil diterapkan.\n\n"
            + report.summary()
            + backup_text,
        )

        self.statusBar().showMessage(
            f"{title} selesai — {report.scanned} file",
            5000,
        )

    @Slot(str, str, object)
    def _source_sync_failed(
        self,
        title: str,
        operation: str,
        exc: object,
    ) -> None:
        self._hide_source_sync_progress()
        QMessageBox.critical(
            self,
            title,
            f"Gagal pada phase {operation}.\n\n{exc}",
        )
        self.statusBar().showMessage(f"{title} gagal", 5000)

    def _current_page_name(self) -> str:
        current_page = self.page_stack.currentWidget()
        for page_name, page in self.pages.items():
            if page is current_page:
                return page_name
        return ""

    def _refresh_data_page_if_needed(
        self,
        page_name: str,
        project,
        *,
        force: bool = False,
    ) -> None:
        if page_name not in DATA_PAGE_NAMES:
            return

        page = self.pages[page_name]
        if project is None:
            page.set_database(None)
            self._project_data_state.mark_clean(page_name)
            return

        if not force and not self._project_data_state.is_dirty(page_name):
            return

        if (
            page_name == "TRACKING"
            and hasattr(page, "configure_track_files")
        ):
            page.configure_track_files(project.settings)

        if hasattr(page, "refresh_from_database"):
            page.refresh_from_database(project.database)
        else:
            page.set_database(project.database)

        self._project_data_state.mark_clean(page_name)

    @Slot(int)
    def _project_data_revision_changed(self, revision: int) -> None:
        project = self.project_manager.current
        if project is None:
            return

        # Project dashboard is small and should always reflect the latest
        # committed application state immediately.
        self.refresh_project_page()

        current_page_name = self._current_page_name()
        if current_page_name in DATA_PAGE_NAMES:
            self._refresh_data_page_if_needed(
                current_page_name,
                project,
            )

    def _workspace_data_changed(self, source_page_name: str) -> None:
        project = self.project_manager.current
        if project is None:
            return

        revision = self._project_data_state.mark_changed()

        # The emitting page has already updated its own UI after committing the
        # change. Keep it clean while all sibling workspaces stay lazy-dirty.
        self._project_data_state.mark_clean(source_page_name)
        self.project_data_changed.emit(revision)

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
            f"Project file: {project.project_file}"
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

        try:
            snapshot = ProjectDashboardService(
                project.database,
                settings,
            ).build()
        except Exception:
            snapshot = None

        if snapshot is not None:
            page.set_dashboard(snapshot)

        page.info_title.setText(
            f"{settings.project_name or 'Project'} ready"
        )
        if snapshot is None:
            page.info_text.setText(
                "Project aktif. Dashboard workflow belum dapat dihitung."
            )
        elif snapshot.actions:
            page.info_text.setText(
                f"{len(snapshot.actions)} jenis pekerjaan membutuhkan perhatian. "
                "Gunakan What Needs Attention untuk langsung membuka workflow terkait."
            )
        else:
            page.info_text.setText(
                "✓ Project data healthy dan tidak ada action penting yang tertunda."
            )

    def handle_project_dashboard_action(self, action_key: str) -> None:
        key = str(action_key or "").strip().casefold()

        if key in {"project.open_recent", "project.recover"}:
            self.handle_ribbon_action(key)
            return

        project = self.project_manager.current
        if project is None:
            return

        if key == "needs_review":
            self.sidebar.select_tab("DATA")
            page = self.pages["DATA"]
            page.set_database(project.database)
            page.show_section("Unresolved")
            return

        if key in {"system_errors", "workflow_warnings"}:
            self.sidebar.select_tab("DATA")
            page = self.pages["DATA"]
            page.set_database(project.database)
            page.show_section("Validation")
            return

        if key == "recording":
            self.sidebar.select_tab("DIALOG")
            self.pages["DIALOG"].set_database(project.database)
            return

        if key in {
            "revision",
            "ready_to_stem",
            "pending_delivery",
            "file_warnings",
        }:
            self.sidebar.select_tab("TRACKING")
            page = self.pages["TRACKING"]
            if hasattr(page, "configure_track_files"):
                page.configure_track_files(project.settings)
            page.set_database(project.database)

            if hasattr(page, "show_workspace"):
                if key == "file_warnings":
                    page.show_workspace("output_health")
                elif key in {"ready_to_stem", "pending_delivery"}:
                    page.show_workspace("track_files")
                else:
                    page.show_workspace("tracking")
            return

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
        if page is None or page_name not in DATA_PAGE_NAMES:
            return

        self._refresh_data_page_if_needed(
            page_name,
            project,
            force=True,
        )
        self.statusBar().showMessage(f"{page_name.title()} view refreshed", 3000)

    def focus_script_search(self) -> None:
        page = self.pages["SCRIPT"]
        page.search_edit.setFocus()
        page.search_edit.selectAll()
        self.statusBar().showMessage("Script search focused", 2000)

    def open_script_search(self) -> None:
        if self.project_manager.current is None:
            QMessageBox.information(
                self,
                "Search Script",
                "Buka atau buat project terlebih dahulu.",
            )
            return

        self.sidebar.select_tab("SCRIPT")
        self.focus_script_search()

    def open_dialog_source(self) -> None:
        page = self.pages["DIALOG"]
        if not page.open_source_button.isEnabled():
            self.statusBar().showMessage(
                "Pilih character dan episode yang memiliki source file.",
                3000,
            )
            return

        page.open_source_button.click()

    def open_tracking_scope(
        self,
        talent_id: int,
        character_id: int,
        episode_number: int,
    ) -> None:
        project = self.project_manager.current
        if project is None:
            return

        self.sidebar.select_tab("TRACKING")
        page = self.pages["TRACKING"]
        if hasattr(page, "show_workspace"):
            page.show_workspace("tracking")
        page.reload(
            preferred_talent=int(talent_id),
            preferred_episode=int(episode_number),
        )

        for row in page._workspace_rows:
            for chip in row.chips:
                if (
                    chip.talent_id == int(talent_id)
                    and chip.character_id == int(character_id)
                    and chip.episode_number == int(episode_number)
                ):
                    page._select_episode_detail(chip)
                    return

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

        tools_page = self.pages["TOOLS"]
        tools_page.set_project(project, run_diagnostics=False)
        if self.page_stack.currentWidget() is tools_page:
            tools_page.refresh_view()

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
    # HELP
    # ------------------------------------------------------------------

    def open_getting_started(self) -> None:
        self.sidebar.select_tab("HELP")
        page = self.pages["HELP"]
        page.show_getting_started()
        self.statusBar().showMessage("Getting Started", 3000)

    def open_user_guide(self) -> None:
        self.sidebar.select_tab("HELP")
        page = self.pages["HELP"]
        page.show_user_guide()
        self.statusBar().showMessage("User Guide", 3000)

    def open_keyboard_shortcuts(self) -> None:
        self.sidebar.select_tab("HELP")
        page = self.pages["HELP"]
        page.show_keyboard_shortcuts()
        self.statusBar().showMessage("Keyboard Shortcuts", 3000)

    def check_for_updates(self) -> None:
        self.sidebar.select_tab("HELP")
        page = self.pages["HELP"]

        if self._update_check_running():
            self.statusBar().showMessage(
                "Update check masih berjalan",
                3000,
            )
            return

        page.show_update_checking(APP_VERSION)
        self.statusBar().showMessage("Checking for updates…")

        thread = QThread(self)
        worker = UpdateCheckWorker()
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.completed.connect(self._update_check_completed)
        worker.failed.connect(self._update_check_failed)

        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.completed.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(self._update_check_thread_finished)
        thread.finished.connect(thread.deleteLater)

        self._update_check_thread = thread
        self._update_check_worker = worker
        thread.start()

    def _update_check_running(self) -> bool:
        thread = self._update_check_thread
        return thread is not None and thread.isRunning()

    @Slot(object)
    def _update_check_completed(self, result: object) -> None:
        page = self.pages["HELP"]
        page.show_update_result(result)

        if getattr(result, "update_available", False):
            latest = str(
                getattr(result, "latest_version", "") or ""
            )
            self.statusBar().showMessage(
                f"Update available: {latest}",
                5000,
            )
        elif getattr(result, "has_release", False):
            self.statusBar().showMessage(
                "Script Manager is up to date",
                5000,
            )
        else:
            self.statusBar().showMessage(
                "No GitHub Release published yet",
                5000,
            )

    @Slot(object)
    def _update_check_failed(self, exc: object) -> None:
        self.pages["HELP"].show_update_error(
            str(exc),
            APP_VERSION,
        )
        self.statusBar().showMessage(
            "Update check failed",
            5000,
        )

    @Slot()
    def _update_check_thread_finished(self) -> None:
        self._update_check_thread = None
        self._update_check_worker = None

    def open_update_release(self, url: str) -> None:
        target = str(url or "").strip()
        if not target:
            return

        opened = QDesktopServices.openUrl(QUrl(target))
        if not opened:
            QMessageBox.warning(
                self,
                "Check for Updates",
                "Sistem tidak dapat membuka halaman release.",
            )

    def open_about(self) -> None:
        self.sidebar.select_tab("HELP")
        info = ApplicationInfoService().build()
        self.pages["HELP"].show_about(info)
        self.statusBar().showMessage(
            f"About {info.app_name} {info.app_version}",
            3000,
        )

    def report_problem(self) -> None:
        self.sidebar.select_tab("HELP")
        report = ProblemReportService().build()
        self.pages["HELP"].show_report_problem(report)
        self.statusBar().showMessage(
            "Problem report template ready",
            3000,
        )

    def open_problem_issue(self, url: str) -> None:
        target = str(url or "").strip()
        if not target:
            return

        opened = QDesktopServices.openUrl(QUrl(target))
        if not opened:
            QMessageBox.warning(
                self,
                "Report a Problem",
                "Sistem tidak dapat membuka halaman GitHub Issue. "
                "Gunakan Copy Report Template sebagai alternatif.",
            )

    # ------------------------------------------------------------------
    # CONTEXTUAL ACTION ROUTING
    # ------------------------------------------------------------------

    def handle_ribbon_action(self, action_id: str) -> None:
        handlers = {
            "project.new": self.new_project,
            "project.open": self.open_project,
            "project.open_recent": self.open_recent_project,
            "project.save": self.save_project,
            "project.save_as": self.save_project_as,
            "project.duplicate": self.duplicate_project,
            "project.recover": self.recover_project,
            "project.settings": self.open_project_settings,
            "project.close": self.close_project,
            "client.drive": self.open_client_drive,
            "source.sync": self.sync_source,
            "script.search": self.focus_script_search,
            "dialog.open_source": self.open_dialog_source,
            "dialog.check_all": (
                lambda: self.pages["DIALOG"].set_all_checked(True)
            ),
            "dialog.uncheck_all": (
                lambda: self.pages["DIALOG"].set_all_checked(False)
            ),
            "tracking.open_drive": self.open_client_drive,
            "data.rebuild": self.rebuild_data_indexes,
            "data.characters": lambda: self.show_data_section("characters"),
            "data.talents": lambda: self.show_data_section("talents"),
            "data.cast": lambda: self.show_data_section("cast"),
            "data.validate": self.validate_data,
            "data.backup": self.backup_database,
            "tools.diagnostics": self.run_tools_diagnostics,
            "tools.audit": self.focus_tools_audit,
            "tools.backup": self.backup_database,
            "tools.restore_backup": self.restore_database_backup,
            "tools.open_project_folder": (
                lambda: self.open_tools_path("project")
            ),
            "tools.open_source_folder": (
                lambda: self.open_tools_path("source")
            ),
            "tools.open_output_folder": (
                lambda: self.open_tools_path("output")
            ),
            "tools.open_delivery_folder": (
                lambda: self.open_tools_path("delivery")
            ),
            "tools.open_backups": (
                lambda: self.open_tools_path("backups")
            ),
            "tools.open_logs": (
                lambda: self.open_tools_path("logs")
            ),
            "tools.open_main_drive": (
                lambda: self.open_tools_drive("main")
            ),
            "tools.open_material_drive": (
                lambda: self.open_tools_drive("material")
            ),
            "tools.open_delivery_drive": (
                lambda: self.open_tools_drive("delivery")
            ),
            "help.getting_started": self.open_getting_started,
            "help.user_guide": self.open_user_guide,
            "help.keyboard_shortcuts": self.open_keyboard_shortcuts,
            "help.check_updates": self.check_for_updates,
            "help.report_problem": self.report_problem,
            "help.about": self.open_about,
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
        if self._update_check_running():
            event.ignore()
            QMessageBox.information(
                self,
                "Check for Updates",
                "Pemeriksaan update sedang berjalan. "
                "Aplikasi tetap terbuka sampai pemeriksaan selesai.",
            )
            return

        if self._source_sync_running():
            event.ignore()
            QMessageBox.information(
                self,
                "Source Sync",
                "Sync Source sedang berjalan. "
                "Aplikasi tetap terbuka untuk menjaga proses database tetap aman.",
            )
            return

        if self.project_manager.is_open:
            try:
                self.project_manager.save()
            except Exception:
                pass

        event.accept()
