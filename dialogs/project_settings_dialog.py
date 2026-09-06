from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.project_settings import ProjectSettings
from widgets.project_configuration import (
    AudioOutputSection,
    DriveLinksSection,
    ProjectConfigurationSections,
    ProjectIdentitySection,
    SourceConfigurationSection,
)


class ProjectSettingsDialog(QDialog):
    def __init__(
        self,
        settings: ProjectSettings,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        self.setWindowTitle("Pengaturan Proyek")
        self.resize(840, 720)
        self.setMinimumSize(720, 620)

        self._result_settings = settings

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel("Pengaturan Proyek")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "Kolom folder menggunakan filesystem path. Folder Google Drive Desktop "
            "diperlakukan seperti folder filesystem biasa (mis. D:\\My Drive\\...). "
            "Tautan Drive Klien adalah URL browser dan tidak digunakan untuk membaca file."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        self.identity_section = ProjectIdentitySection(
            settings,
            show_project_file=True,
        )
        self.source_section = SourceConfigurationSection(settings)
        self.audio_section = AudioOutputSection(settings)
        self.links_section = DriveLinksSection(settings)
        self.sections = ProjectConfigurationSections(
            identity=self.identity_section,
            source=self.source_section,
            audio=self.audio_section,
            links=self.links_section,
        )

        # Compatibility aliases keep existing integrations stable while all
        # collection/loading logic now lives in the reusable sections.
        self.project_name = self.identity_section.project_name
        self.project_code = self.identity_section.project_code
        self.client_name = self.identity_section.client_name
        self.start_date = self.identity_section.start_date
        self.project_file = self.identity_section.project_file
        self.source_folder = self.source_section.source_folder
        self.read_source_filenames_button = (
            self.source_section.read_source_filenames_button
        )
        self.source_pattern_status = self.source_section.source_pattern_status
        self.source_filename_example = self.source_section.source_filename_example
        self.copy_source_filename_button = (
            self.source_section.copy_source_filename_button
        )
        self.source_pattern_details = self.source_section.source_pattern_details
        self.filename_preview = self.source_section.filename_preview
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

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_project_tab(), "Proyek")
        self.tabs.addTab(self._build_track_output_tab(), "Output Track & Setoran")
        root.addWidget(self.tabs, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._accept_settings)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @property
    def result_settings(self) -> ProjectSettings:
        return self._result_settings

    def _build_project_tab(self) -> QScrollArea:
        scroll, content, layout = self._scroll_tab()
        layout.addWidget(self.identity_section)
        layout.addWidget(self.source_section)
        layout.addWidget(self.links_section)
        layout.addStretch(1)
        scroll.setWidget(content)
        return scroll

    def _build_track_output_tab(self) -> QScrollArea:
        scroll, content, layout = self._scroll_tab()
        layout.addWidget(self.audio_section)
        layout.addStretch(1)
        scroll.setWidget(content)
        return scroll

    @staticmethod
    def _scroll_tab() -> tuple[QScrollArea, QWidget, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(6, 8, 10, 8)
        layout.setSpacing(12)
        return scroll, content, layout

    def _read_source_filenames(self) -> None:
        self.source_section.read_source_filenames()

    def _accept_settings(self) -> None:
        project_folder = (
            self.project_file.text()
            if self.project_file is not None
            else ""
        )
        self._result_settings = self.sections.to_settings(
            project_folder=project_folder,
        )
        self.accept()
