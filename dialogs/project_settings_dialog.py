from __future__ import annotations

from PySide6.QtCore import QDate, Qt
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
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.project_settings import ProjectSettings


class FolderField(QWidget):
    def __init__(
        self,
        value: str = "",
        *,
        browse_caption: str = "Select Folder",
        read_only: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        self.browse_caption = browse_caption

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.edit = QLineEdit(value)
        self.edit.setReadOnly(read_only)
        layout.addWidget(self.edit, 1)

        self.browse_button = QPushButton("Browse…")
        self.browse_button.setProperty("secondary", True)
        self.browse_button.setEnabled(not read_only)
        self.browse_button.clicked.connect(self.browse)
        layout.addWidget(self.browse_button)

    def browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            self.browse_caption,
            self.edit.text().strip(),
        )
        if folder:
            self.edit.setText(folder)

    def text(self) -> str:
        return self.edit.text().strip()


class ProjectSettingsDialog(QDialog):
    def __init__(
        self,
        settings: ProjectSettings,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        self.setWindowTitle("Project Settings")
        self.resize(720, 700)
        self.setMinimumSize(650, 580)

        self._result_settings = settings

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Project Settings")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "Konfigurasi ini melekat pada project dan nantinya disimpan di project.json."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        root.addWidget(scroll, 1)

        content = QWidget()
        scroll.setWidget(content)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(2, 2, 8, 2)
        content_layout.setSpacing(12)

        project_group = QGroupBox("Project")
        project_form = QFormLayout(project_group)
        project_form.setLabelAlignment(Qt.AlignLeft)

        self.project_name = QLineEdit(settings.project_name)
        self.project_code = QLineEdit(settings.project_code)
        self.client_name = QLineEdit(settings.client_name)

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("dd MMMM yyyy")
        parsed_date = QDate.fromString(settings.start_date, "yyyy-MM-dd")
        self.start_date.setDate(
            parsed_date if parsed_date.isValid() else QDate.currentDate()
        )

        self.project_folder = FolderField(
            settings.project_folder,
            read_only=True,
        )

        project_form.addRow("Project Name", self.project_name)
        project_form.addRow("Project Code", self.project_code)
        project_form.addRow("Client", self.client_name)
        project_form.addRow("Start Date", self.start_date)
        project_form.addRow("Project Location", self.project_folder)

        location_note = QLabel(
            "Lokasi project ditampilkan di sini tetapi tidak diedit langsung. "
            "Perpindahan project nanti dilakukan melalui fitur Move Project."
        )
        location_note.setWordWrap(True)
        location_note.setObjectName("PageSubtitle")
        project_form.addRow("", location_note)

        content_layout.addWidget(project_group)

        source_group = QGroupBox("Source Script")
        source_form = QFormLayout(source_group)
        source_form.setLabelAlignment(Qt.AlignLeft)

        self.source_folder = FolderField(
            settings.source_folder,
            browse_caption="Select Source Script Folder",
        )

        self.episode_before = QLineEdit(settings.episode_before)
        self.episode_after = QLineEdit(settings.episode_after)
        self.episode_before.setPlaceholderText("contoh: EP")
        self.episode_after.setPlaceholderText("contoh: _")

        source_form.addRow("Source Folder", self.source_folder)
        source_form.addRow("Before Episode Number", self.episode_before)
        source_form.addRow("After Episode Number", self.episode_after)

        delimiter_help = QLabel(
            "Contoh: AA23_EP001_SCRIPT.xlsx. "
            "Before = EP dan After = _ akan menghasilkan episode 001."
        )
        delimiter_help.setWordWrap(True)
        delimiter_help.setObjectName("PageSubtitle")
        source_form.addRow("", delimiter_help)

        self.filename_sample = QLineEdit()
        self.filename_sample.setPlaceholderText(
            "Tes nama file, mis. AA23_EP001_SCRIPT.xlsx"
        )
        self.filename_preview = QLabel("Episode preview: -")
        self.filename_preview.setObjectName("PageSubtitle")

        self.filename_sample.textChanged.connect(self._update_episode_preview)
        self.episode_before.textChanged.connect(self._update_episode_preview)
        self.episode_after.textChanged.connect(self._update_episode_preview)

        source_form.addRow("Test Filename", self.filename_sample)
        source_form.addRow("", self.filename_preview)

        content_layout.addWidget(source_group)

        drive_group = QGroupBox("Client Drive Links")
        drive_form = QFormLayout(drive_group)
        drive_form.setLabelAlignment(Qt.AlignLeft)

        self.main_drive_url = QLineEdit(settings.main_drive_url)
        self.material_drive_url = QLineEdit(settings.material_drive_url)
        self.delivery_drive_url = QLineEdit(settings.delivery_drive_url)

        self.main_drive_url.setPlaceholderText("https://drive.google.com/...")
        self.material_drive_url.setPlaceholderText("optional")
        self.delivery_drive_url.setPlaceholderText("optional")

        drive_form.addRow("Main Drive", self.main_drive_url)
        drive_form.addRow("Material Folder", self.material_drive_url)
        drive_form.addRow("Delivery / Setoran", self.delivery_drive_url)

        content_layout.addWidget(drive_group)
        content_layout.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._accept_settings)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @property
    def result_settings(self) -> ProjectSettings:
        return self._result_settings

    def _update_episode_preview(self) -> None:
        episode = self._extract_episode_preview(
            self.filename_sample.text(),
            self.episode_before.text(),
            self.episode_after.text(),
        )

        self.filename_preview.setText(
            f"Episode preview: {episode}" if episode else "Episode preview: -"
        )

    @staticmethod
    def _extract_episode_preview(
        filename: str,
        before: str,
        after: str,
    ) -> str | None:
        text = filename.strip()
        if not text:
            return None

        start = 0

        if before:
            index = text.find(before)
            if index < 0:
                return None
            start = index + len(before)

        if after:
            end = text.find(after, start)
            if end < 0:
                return None
            result = text[start:end]
        else:
            remainder = text[start:]
            digits = []
            started = False

            for char in remainder:
                if char.isdigit():
                    digits.append(char)
                    started = True
                elif started:
                    break

            result = "".join(digits)

        result = result.strip()
        return result if result else None

    def _accept_settings(self) -> None:
        self._result_settings = ProjectSettings(
            project_name=self.project_name.text(),
            project_code=self.project_code.text(),
            client_name=self.client_name.text(),
            start_date=self.start_date.date().toString("yyyy-MM-dd"),
            project_folder=self.project_folder.text(),
            source_folder=self.source_folder.text(),
            episode_before=self.episode_before.text(),
            episode_after=self.episode_after.text(),
            main_drive_url=self.main_drive_url.text(),
            material_drive_url=self.material_drive_url.text(),
            delivery_drive_url=self.delivery_drive_url.text(),
        ).normalized()

        self.accept()
