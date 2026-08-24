from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.project_settings import ProjectSettings


class NewProjectDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.setWindowTitle("New Project")
        self.resize(680, 560)
        self.setMinimumWidth(620)

        self._settings = ProjectSettings()
        self._parent_folder = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("New Project")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "Project akan dibuat sebagai satu folder yang berisi project.json, "
            "project.db, backups, dan logs."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        group = QGroupBox("Project")
        form = QFormLayout(group)

        self.project_name = QLineEdit()
        self.project_code = QLineEdit()
        self.client_name = QLineEdit()

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setDisplayFormat("dd MMMM yyyy")

        location_widget = QWidget()
        location_layout = QHBoxLayout(location_widget)
        location_layout.setContentsMargins(0, 0, 0, 0)
        location_layout.setSpacing(6)

        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText(
            "Folder induk tempat project akan dibuat"
        )
        location_layout.addWidget(self.location_edit, 1)

        browse = QPushButton("Browse…")
        browse.setProperty("secondary", True)
        browse.clicked.connect(self._browse_location)
        location_layout.addWidget(browse)

        form.addRow("Project Name", self.project_name)
        form.addRow("Project Code", self.project_code)
        form.addRow("Client", self.client_name)
        form.addRow("Start Date", self.start_date)
        form.addRow("Save Project In", location_widget)

        root.addWidget(group)

        source_group = QGroupBox("Initial Source")
        source_form = QFormLayout(source_group)

        source_widget = QWidget()
        source_layout = QHBoxLayout(source_widget)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.setSpacing(6)

        self.source_folder = QLineEdit()
        self.source_folder.setPlaceholderText(
            "Boleh dikosongkan dan diatur kemudian"
        )
        source_layout.addWidget(self.source_folder, 1)

        source_browse = QPushButton("Browse…")
        source_browse.setProperty("secondary", True)
        source_browse.clicked.connect(self._browse_source)
        source_layout.addWidget(source_browse)

        self.episode_before = QLineEdit()
        self.episode_after = QLineEdit()
        self.episode_before.setPlaceholderText("contoh: EP")
        self.episode_after.setPlaceholderText("contoh: _")

        source_form.addRow("Source Folder", source_widget)
        source_form.addRow("Before Episode Number", self.episode_before)
        source_form.addRow("After Episode Number", self.episode_after)

        root.addWidget(source_group)

        drive_group = QGroupBox("Client Drive")
        drive_form = QFormLayout(drive_group)

        self.main_drive_url = QLineEdit()
        self.main_drive_url.setPlaceholderText("optional")

        drive_form.addRow("Main Drive URL", self.main_drive_url)

        root.addWidget(drive_group)
        root.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        save_button = buttons.button(QDialogButtonBox.Save)
        save_button.setText("Create Project")

        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        root.addWidget(buttons)

        self.project_name.textChanged.connect(self._sync_project_code)

    @property
    def settings(self) -> ProjectSettings:
        return self._settings

    @property
    def parent_folder(self) -> str:
        return self._parent_folder

    def _sync_project_code(self, value: str) -> None:
        if not self.project_code.text().strip():
            self.project_code.setText(value.strip())

    def _browse_location(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Project Location",
            self.location_edit.text().strip(),
        )
        if folder:
            self.location_edit.setText(folder)

    def _browse_source(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Source Script Folder",
            self.source_folder.text().strip(),
        )
        if folder:
            self.source_folder.setText(folder)

    def _accept(self) -> None:
        name = self.project_name.text().strip()
        location = self.location_edit.text().strip()

        if not name:
            QMessageBox.warning(
                self,
                "New Project",
                "Project Name wajib diisi.",
            )
            return

        if not location:
            QMessageBox.warning(
                self,
                "New Project",
                "Lokasi penyimpanan project wajib dipilih.",
            )
            return

        self._settings = ProjectSettings(
            project_name=name,
            project_code=self.project_code.text().strip(),
            client_name=self.client_name.text().strip(),
            start_date=self.start_date.date().toString("yyyy-MM-dd"),
            project_folder="",
            source_folder=self.source_folder.text().strip(),
            episode_before=self.episode_before.text(),
            episode_after=self.episode_after.text(),
            main_drive_url=self.main_drive_url.text().strip(),
        ).normalized()

        self._parent_folder = location
        self.accept()
