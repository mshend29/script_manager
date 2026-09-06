from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.project_filename import new_project_destination
from core.project_settings import ProjectSettings
from widgets.project_configuration import (
    AudioOutputSection,
    DriveLinksSection,
    FolderField,
    ProjectConfigurationSections,
    ProjectIdentitySection,
    SourceConfigurationSection,
)


class NewProjectDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.setWindowTitle("Proyek Baru")
        self.resize(780, 720)
        self.setMinimumSize(680, 620)

        self._settings = ProjectSettings()
        self._parent_folder = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Proyek Baru")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "Project akan dibuat sebagai satu file Script Management Project "
            "(.smproj). Source Excel, stem, dan file setoran tetap berada "
            "di lokasi eksternal dan hanya direferensikan oleh project."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(2, 2, 8, 2)
        content_layout.setSpacing(12)

        self.identity_section = ProjectIdentitySection(self._settings)
        self.source_section = SourceConfigurationSection(self._settings)
        self.audio_section = AudioOutputSection(self._settings)
        self.links_section = DriveLinksSection(self._settings)
        self.sections = ProjectConfigurationSections(
            identity=self.identity_section,
            source=self.source_section,
            audio=self.audio_section,
            links=self.links_section,
        )

        # Compatibility aliases for callers/tests that already use the dialog
        # fields directly. The reusable sections are the single source of data.
        self.project_name = self.identity_section.project_name
        self.project_code = self.identity_section.project_code
        self.client_name = self.identity_section.client_name
        self.start_date = self.identity_section.start_date
        self.source_folder = self.source_section.source_folder.edit
        self.episode_before = self.source_section.episode_before
        self.episode_after = self.source_section.episode_after
        self.stem_output_folder = self.audio_section.stem_output_folder
        self.delivery_folder = self.audio_section.delivery_folder
        self.audio_sample_rate = self.audio_section.audio_sample_rate
        self.audio_bit_depth = self.audio_section.audio_bit_depth
        self.audio_channels = self.audio_section.audio_channels
        self.main_drive_url = self.links_section.main_drive_url
        self.material_drive_url = self.links_section.material_drive_url
        self.delivery_drive_url = self.links_section.delivery_drive_url

        content_layout.addWidget(self.identity_section)

        destination_group = QWidget()
        destination_layout = QVBoxLayout(destination_group)
        destination_layout.setContentsMargins(0, 0, 0, 0)
        destination_layout.setSpacing(6)

        location_row = QHBoxLayout()
        location_row.setContentsMargins(0, 0, 0, 0)
        location_row.setSpacing(8)
        location_label = QLabel("Simpan Proyek Di")
        location_label.setMinimumWidth(130)
        self.location_field = FolderField(
            browse_caption="Pilih Lokasi Proyek"
        )
        self.location_edit = self.location_field.edit
        location_row.addWidget(location_label)
        location_row.addWidget(self.location_field, 1)
        destination_layout.addLayout(location_row)

        self.destination_preview = QLabel("File proyek: -")
        self.destination_preview.setObjectName("PageSubtitle")
        self.destination_preview.setWordWrap(True)
        destination_layout.addWidget(self.destination_preview)
        content_layout.addWidget(destination_group)

        content_layout.addWidget(self.source_section)
        content_layout.addWidget(self.audio_section)
        content_layout.addWidget(self.links_section)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        self.create_button = buttons.button(QDialogButtonBox.Save)
        self.create_button.setText("Buat Proyek")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.project_name.textChanged.connect(self._sync_project_code)
        self.project_name.textChanged.connect(self._update_destination_preview)
        self.project_code.textChanged.connect(self._update_destination_preview)
        self.location_edit.textChanged.connect(self._update_destination_preview)
        self._update_destination_preview()

    @property
    def settings(self) -> ProjectSettings:
        return self._settings

    @property
    def parent_folder(self) -> str:
        return self._parent_folder

    def _sync_project_code(self, value: str) -> None:
        if not self.project_code.text().strip():
            self.project_code.setText(value.strip())

    def _update_destination_preview(self) -> None:
        parent = self.location_edit.text().strip()
        name = self.project_name.text().strip()
        code = self.project_code.text().strip() or name

        if not parent or not name:
            self.destination_preview.setText("File proyek: -")
            self.create_button.setEnabled(True)
            return

        destination = new_project_destination(parent, code, name)
        if destination.exists():
            self.destination_preview.setText(
                f"✕ File proyek sudah ada: {destination}"
            )
            self.create_button.setEnabled(False)
        else:
            self.destination_preview.setText(f"File proyek: {destination}")
            self.create_button.setEnabled(True)

    def _accept(self) -> None:
        location = self.location_edit.text().strip()
        if not location:
            QMessageBox.warning(
                self,
                "Proyek Baru",
                "Lokasi penyimpanan proyek wajib dipilih.",
            )
            return

        settings = self.sections.to_settings()
        issues = self.sections.validate_basic(strict_new_project=False)
        if issues:
            QMessageBox.warning(
                self,
                "Proyek Baru",
                issues[0].message,
            )
            return

        destination = new_project_destination(
            location,
            settings.project_code or settings.project_name,
            settings.project_name,
        )
        if destination.exists():
            QMessageBox.warning(
                self,
                "Proyek Baru",
                f"File proyek sudah ada:\n{destination}",
            )
            self._update_destination_preview()
            return

        parent = Path(location).expanduser()
        if parent.exists() and not parent.is_dir():
            QMessageBox.warning(
                self,
                "Proyek Baru",
                "Lokasi penyimpanan proyek bukan folder.",
            )
            return

        self._settings = settings
        self._parent_folder = location
        self.accept()
