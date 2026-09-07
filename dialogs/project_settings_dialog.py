from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.project_settings import ProjectSettings
from services.project_settings_change_validation import (
    IDENTITY_FIELDS,
    LINK_FIELDS,
    SOURCE_FIELDS,
    TRACKING_FIELDS,
    ProjectSettingsChangeValidation,
    validate_existing_project_settings_change,
)
from widgets.folder_drive_help import show_folder_drive_help
from widgets.project_configuration import (
    AudioOutputSection,
    DriveLinksSection,
    ProjectConfigurationSections,
    ProjectIdentitySection,
    SourceConfigurationSection,
)


class ProjectSettingsDialog(QDialog):
    TAB_TITLES = (
        "Proyek",
        "Sumber Naskah",
        "Audio & Setoran",
        "Tautan Drive",
    )

    def __init__(
        self,
        settings: ProjectSettings,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        self.setWindowTitle("Pengaturan Proyek")
        self.resize(900, 720)
        self.setMinimumSize(760, 620)

        self._baseline_settings = settings.normalized()
        self._result_settings = settings
        self._last_validation: ProjectSettingsChangeValidation | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        title = QLabel("Pengaturan Proyek")
        title.setObjectName("PageTitle")
        header.addWidget(title, 1)

        self.help_button = QPushButton("?")
        self.help_button.setObjectName("ProjectSettingsHelpButton")
        self.help_button.setToolTip("Bantuan folder dan Google Drive")
        self.help_button.setAccessibleName("Bantuan folder dan Google Drive")
        self.help_button.setFixedSize(32, 32)
        self.help_button.setProperty("secondary", True)
        self.help_button.clicked.connect(self._show_folder_drive_help)
        header.addWidget(
            self.help_button,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        root.addLayout(header)

        subtitle = QLabel(
            "Pengaturan ini memakai konfigurasi yang sama dengan wizard Proyek Baru. "
            "Folder adalah filesystem path; tautan Google Drive adalah URL browser "
            "dan tidak digunakan aplikasi untuk membaca file."
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
        # collection/loading logic remains owned by the reusable sections.
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
        self.tabs.setObjectName("ProjectSettingsTabs")
        self.tabs.addTab(
            self._build_section_tab(
                self.identity_section,
                "Identitas proyek dan lokasi file .smproj yang sedang dibuka.",
            ),
            self.TAB_TITLES[0],
        )
        self.tabs.addTab(
            self._build_section_tab(
                self.source_section,
                "Folder sumber, pola filename, delimiter, dan pratinjau episode.",
            ),
            self.TAB_TITLES[1],
        )
        self.tabs.addTab(
            self._build_section_tab(
                self.audio_section,
                "Folder Stem/Export, Folder Setoran, dan spesifikasi WAV produksi.",
            ),
            self.TAB_TITLES[2],
        )
        self.tabs.addTab(
            self._build_section_tab(
                self.links_section,
                "Tautan browser bersifat opsional dan terpisah dari filesystem path.",
            ),
            self.TAB_TITLES[3],
        )
        root.addWidget(self.tabs, 1)

        self.validation_status = QLabel()
        self.validation_status.setObjectName("ProjectSettingsValidationStatus")
        self.validation_status.setWordWrap(True)
        self.validation_status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        root.addWidget(self.validation_status)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        self.buttons.accepted.connect(self._accept_settings)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        # Existing external drives may be offline when Settings opens. Surface
        # that state immediately as a warning, never as an open-time blocker.
        self._render_validation(
            validate_existing_project_settings_change(
                self._baseline_settings,
                self._baseline_settings,
                verify_writable=False,
            )
        )

    @property
    def result_settings(self) -> ProjectSettings:
        return self._result_settings

    @property
    def last_validation(self) -> ProjectSettingsChangeValidation | None:
        return self._last_validation

    def _build_section_tab(
        self,
        section: QWidget,
        description: str,
    ) -> QScrollArea:
        scroll, content, layout = self._scroll_tab()

        note = QLabel(description)
        note.setObjectName("PageSubtitle")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addWidget(section)
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

    def _show_folder_drive_help(self) -> None:
        show_folder_drive_help(self)

    def _collect_candidate(self) -> ProjectSettings:
        project_folder = (
            self.project_file.text()
            if self.project_file is not None
            else ""
        )
        return self.sections.to_settings(
            project_folder=project_folder,
        )

    def _accept_settings(self) -> None:
        candidate = self._collect_candidate()
        validation = validate_existing_project_settings_change(
            self._baseline_settings,
            candidate,
            verify_writable=True,
        )
        self._render_validation(validation)

        if not validation.is_valid:
            if validation.errors:
                self._focus_issue(validation.errors[0].field)
            return

        self._result_settings = candidate
        self.accept()

    def _render_validation(
        self,
        validation: ProjectSettingsChangeValidation,
    ) -> None:
        self._last_validation = validation

        if validation.errors:
            lines = [
                f"✕ {issue.message}"
                for issue in validation.errors[:4]
            ]
            remaining = len(validation.errors) - len(lines)
            if remaining > 0:
                lines.append(f"… {remaining} masalah blocking lainnya.")
            self.validation_status.setText(
                "Pengaturan belum dapat disimpan:\n" + "\n".join(lines)
            )
            self.validation_status.setProperty("status", "error")
        elif validation.warnings:
            lines = [
                f"⚠ {issue.message}"
                for issue in validation.warnings[:3]
            ]
            remaining = len(validation.warnings) - len(lines)
            if remaining > 0:
                lines.append(f"… {remaining} warning lainnya.")
            self.validation_status.setText(
                "Project tetap dapat digunakan; periksa bila drive tersedia kembali:\n"
                + "\n".join(lines)
            )
            self.validation_status.setProperty("status", "warning")
        else:
            self.validation_status.setText("✓ Konfigurasi siap disimpan.")
            self.validation_status.setProperty("status", "valid")

        self.validation_status.style().unpolish(self.validation_status)
        self.validation_status.style().polish(self.validation_status)

    def _focus_issue(self, field: str) -> None:
        if field in IDENTITY_FIELDS:
            tab_index = 0
        elif field in SOURCE_FIELDS:
            tab_index = 1
        elif field in TRACKING_FIELDS:
            tab_index = 2
        elif field in LINK_FIELDS:
            tab_index = 3
        else:
            return

        self.tabs.setCurrentIndex(tab_index)
        widget = self._field_widget(field)
        if widget is not None:
            widget.setFocus()

    def _field_widget(self, field: str) -> QWidget | None:
        widgets: dict[str, QWidget] = {
            "project_name": self.project_name,
            "project_code": self.project_code,
            "client_name": self.client_name,
            "start_date": self.start_date,
            "source_folder": self.source_folder.edit,
            "episode_before": self.episode_before,
            "episode_after": self.episode_after,
            "stem_output_folder": self.stem_output_folder.edit,
            "delivery_folder": self.delivery_folder.edit,
            "audio_sample_rate": self.audio_sample_rate,
            "audio_bit_depth": self.audio_bit_depth,
            "audio_channels": self.audio_channels,
            "main_drive_url": self.main_drive_url,
            "material_drive_url": self.material_drive_url,
            "delivery_drive_url": self.delivery_drive_url,
        }
        return widgets.get(field)
