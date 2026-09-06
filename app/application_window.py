from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from app.main_window import MainWindow
from dialogs.new_project_dialog import NewProjectDialog


class ApplicationWindow(MainWindow):
    """Production window orchestration layered over the stable workspace shell.

    Phase 11 keeps the existing MainWindow workspaces untouched while the New
    Project lifecycle gains transactional retry semantics. Initial source sync
    is intentionally not added here until 11.14.
    """

    def new_project(self) -> None:
        if self._block_project_change_during_sync("Proyek Baru"):
            return

        dialog = NewProjectDialog(self)

        while True:
            if not dialog.exec():
                return

            try:
                project = self.project_manager.create_transactional(
                    dialog.settings,
                    dialog.parent_folder,
                )
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "Proyek Baru",
                    (
                        "Project belum dibuat. Semua input wizard tetap "
                        "dipertahankan agar dapat diperbaiki lalu dicoba lagi.\n\n"
                        f"{exc}"
                    ),
                )
                # Re-run final validation before the same dialog instance is
                # shown again. This catches late destination collisions or
                # filesystem changes without discarding any user input.
                refresh_review = getattr(dialog, "_refresh_review", None)
                if callable(refresh_review):
                    refresh_review()
                continue

            break

        self._clear_data_pages()
        self._project_data_state.reset(mark_dirty=True)
        self.refresh_project_page()
        self.setWindowTitle(
            f"{project.settings.project_name} - Script Manager"
        )
        # Recent Projects is deliberately recorded only after the transaction
        # has succeeded. A failed/rolled-back project never reaches this line.
        self._record_recent_project(project)
        self.statusBar().showMessage(
            f"Proyek dibuat: {project.project_file}",
            5000,
        )
