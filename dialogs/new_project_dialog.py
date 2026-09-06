from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.project_filename import new_project_destination
from core.project_settings import ProjectSettings
from services.project_setup_validation import (
    create_project_destination_folder,
    validate_project_identity_destination,
)
from services.source_setup_validation import SourceFilenameValidation
from widgets.project_configuration import (
    AudioOutputSection,
    DriveLinksSection,
    FolderField,
    ProjectConfigurationSections,
    ProjectIdentitySection,
    SourceConfigurationSection,
)
from widgets.wizard_milestone_rail import (
    WizardMilestoneRail,
    WizardMilestoneState,
)


class NewProjectDialog(QDialog):
    STEP_TITLES = (
        "Inisialisasi Proyek",
        "Sumber Naskah",
        "Sumber Audio",
        "Folder & Tautan",
        "Buat Proyek",
    )

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.setWindowTitle("Proyek Baru")
        self.resize(1040, 720)
        self.setMinimumSize(760, 560)

        self._settings = ProjectSettings()
        self._parent_folder = ""
        self._current_step = 0
        self._step_states = [
            WizardMilestoneState.PENDING
            for _ in self.STEP_TITLES
        ]
        self._step_messages = ["" for _ in self.STEP_TITLES]
        self._destination_collision = False
        self._project_code_manually_edited = False

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(12)

        header_text = QVBoxLayout()
        header_text.setContentsMargins(0, 0, 0, 0)
        header_text.setSpacing(2)

        title = QLabel("Proyek Baru")
        title.setObjectName("PageTitle")
        header_text.addWidget(title)

        subtitle = QLabel(
            "Lengkapi lima langkah setup. Project belum dibuat sampai "
            "Buat Proyek dipilih pada langkah terakhir."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        header_text.addWidget(subtitle)
        header.addLayout(header_text, 1)

        self.help_button = QPushButton("?")
        self.help_button.setObjectName("WizardHelpButton")
        self.help_button.setToolTip("Bantuan setup proyek")
        self.help_button.setAccessibleName("Bantuan setup proyek")
        self.help_button.setFixedSize(32, 32)
        self.help_button.setProperty("secondary", True)
        self.help_button.clicked.connect(self._show_setup_help)
        header.addWidget(
            self.help_button,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        root.addLayout(header)

        self.identity_section = ProjectIdentitySection(self._settings)
        self.source_section = SourceConfigurationSection(
            self._settings,
            auto_validate=True,
        )
        self.audio_section = AudioOutputSection(self._settings)
        self.links_section = DriveLinksSection(self._settings)
        self.sections = ProjectConfigurationSections(
            identity=self.identity_section,
            source=self.source_section,
            audio=self.audio_section,
            links=self.links_section,
        )

        # Compatibility aliases for callers/tests that already use the dialog
        # fields directly. The reusable sections remain the single data source.
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

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(14)

        self.milestone_rail = WizardMilestoneRail(self.STEP_TITLES)
        body.addWidget(self.milestone_rail)

        self.page_stack = QStackedWidget()
        self.page_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        body.addWidget(self.page_stack, 1)
        root.addLayout(body, 1)

        self.location_field = FolderField(
            browse_caption="Pilih Lokasi Proyek"
        )
        self.location_edit = self.location_field.edit

        self.create_location_button = QPushButton("Buat Folder")
        self.create_location_button.setProperty("secondary", True)
        self.create_location_button.setToolTip(
            "Buat folder lokasi proyek yang belum tersedia"
        )
        self.create_location_button.clicked.connect(
            self._create_destination_folder
        )
        self.create_location_button.hide()

        self.destination_preview = QLabel("File proyek: -")
        self.destination_preview.setObjectName("PageSubtitle")
        self.destination_preview.setWordWrap(True)

        destination_panel = QWidget()
        destination_layout = QVBoxLayout(destination_panel)
        destination_layout.setContentsMargins(0, 0, 0, 0)
        destination_layout.setSpacing(6)
        destination_label = QLabel("Penyimpanan Proyek")
        destination_label.setStyleSheet("font-weight: 600;")
        destination_layout.addWidget(destination_label)
        destination_layout.addWidget(self.location_field)
        destination_layout.addWidget(self.create_location_button)
        destination_layout.addWidget(self.destination_preview)

        self.page_stack.addWidget(
            self._make_page(
                "1. Inisialisasi Proyek",
                "Tentukan identitas project dan lokasi file .smproj baru.",
                self.identity_section,
                destination_panel,
            )
        )
        self.page_stack.addWidget(
            self._make_page(
                "2. Sumber Naskah",
                "Pilih sumber naskah dan aturan pembacaan nomor episode. "
                "Seluruh filename divalidasi otomatis; isi workbook belum dibaca.",
                self.source_section,
            )
        )
        self.page_stack.addWidget(
            self._make_page(
                "3. Sumber Audio",
                "Tentukan folder output produksi dan spesifikasi WAV.",
                self.audio_section,
            )
        )
        self.page_stack.addWidget(
            self._make_page(
                "4. Folder & Tautan",
                "Tautan browser bersifat opsional dan terpisah dari filesystem path.",
                self.links_section,
            )
        )

        self.review_placeholder = QLabel(
            "Ringkasan final akan menampilkan kesiapan seluruh konfigurasi "
            "sebelum project dibuat."
        )
        self.review_placeholder.setWordWrap(True)
        self.review_placeholder.setObjectName("PageSubtitle")
        self.page_stack.addWidget(
            self._make_page(
                "5. Review & Buat Proyek",
                "Periksa kembali setup sebelum membuat file project.",
                self.review_placeholder,
            )
        )

        footer_line = QFrame()
        footer_line.setFrameShape(QFrame.Shape.HLine)
        footer_line.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(footer_line)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)

        self.validation_status = QLabel("")
        self.validation_status.setObjectName("PageSubtitle")
        self.validation_status.setWordWrap(True)
        footer.addWidget(self.validation_status, 1)

        self.back_button = QPushButton("< Kembali")
        self.back_button.setProperty("secondary", True)
        self.back_button.clicked.connect(self._go_back)
        footer.addWidget(self.back_button)

        self.next_button = QPushButton("Berikutnya >")
        self.next_button.clicked.connect(self._go_next)
        footer.addWidget(self.next_button)

        self.create_button = QPushButton("Buat Proyek")
        self.create_button.clicked.connect(self._accept)
        footer.addWidget(self.create_button)

        self.cancel_button = QPushButton("Batal")
        self.cancel_button.setProperty("secondary", True)
        self.cancel_button.clicked.connect(self.reject)
        footer.addWidget(self.cancel_button)
        root.addLayout(footer)

        self.project_name.textChanged.connect(self._sync_project_code)
        self.project_name.textChanged.connect(self._update_destination_preview)
        self.project_code.textChanged.connect(self._update_destination_preview)
        self.project_code.textEdited.connect(self._mark_project_code_manual)
        self.client_name.textChanged.connect(self._refresh_identity_validation)
        self.start_date.dateChanged.connect(self._refresh_identity_validation)
        self.location_edit.textChanged.connect(self._update_destination_preview)
        self.source_section.validation_changed.connect(
            self._source_validation_changed
        )

        self._refresh_identity_validation()
        self._show_step(0)

    @property
    def settings(self) -> ProjectSettings:
        return self._settings

    @property
    def parent_folder(self) -> str:
        return self._parent_folder

    @property
    def current_step(self) -> int:
        return self._current_step

    def _make_page(
        self,
        title: str,
        description: str,
        *widgets: QWidget,
    ) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 4, 12, 8)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        title_label.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(title_label)

        description_label = QLabel(description)
        description_label.setObjectName("PageSubtitle")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)

        for widget in widgets:
            layout.addWidget(widget)
        layout.addStretch(1)

        scroll.setWidget(content)
        return scroll

    def set_step_state(
        self,
        index: int,
        state: WizardMilestoneState | str,
        message: str = "",
    ) -> None:
        if not 0 <= index < len(self.STEP_TITLES):
            return
        resolved = WizardMilestoneState(state)
        self._step_states[index] = resolved
        self._step_messages[index] = str(message or "")
        self.milestone_rail.set_state(index, resolved)
        if index == self._current_step:
            self.validation_status.setText(self._step_messages[index])
        self._update_navigation_buttons()

    def _can_advance_current_step(self) -> bool:
        return self._step_states[self._current_step] != WizardMilestoneState.ERROR

    def _show_step(self, index: int) -> None:
        index = max(0, min(index, len(self.STEP_TITLES) - 1))
        self._current_step = index
        self.page_stack.setCurrentIndex(index)
        self.milestone_rail.set_active(index)
        self.validation_status.setText(self._step_messages[index])
        self._update_navigation_buttons()

        if index == 1 and self.source_section.validation is None:
            self.source_section.validate_source_filenames()

    def _go_back(self) -> None:
        if self._current_step > 0:
            self._show_step(self._current_step - 1)

    def _go_next(self) -> None:
        if self._current_step == 0:
            self._refresh_identity_validation(verify_writable=True)
        elif self._current_step == 1:
            self.source_section.validate_source_filenames()

        if not self._can_advance_current_step():
            return
        if self._current_step < len(self.STEP_TITLES) - 1:
            self._show_step(self._current_step + 1)

    def _update_navigation_buttons(self) -> None:
        is_final = self._current_step == len(self.STEP_TITLES) - 1
        can_advance = self._can_advance_current_step()
        has_blocking_step = any(
            state == WizardMilestoneState.ERROR
            for state in self._step_states
        )

        self.back_button.setEnabled(self._current_step > 0)
        self.next_button.setVisible(not is_final)
        self.next_button.setEnabled(can_advance)
        self.create_button.setVisible(is_final)
        self.create_button.setEnabled(
            can_advance
            and not has_blocking_step
            and not self._destination_collision
        )

    def _mark_project_code_manual(self, _value: str = "") -> None:
        self._project_code_manually_edited = True
        self._refresh_identity_validation()

    def _sync_project_code(self, value: str) -> None:
        if self._project_code_manually_edited:
            return
        desired = value.strip()
        if self.project_code.text() != desired:
            self.project_code.setText(desired)

    def _update_destination_preview(self, _value: object = None) -> None:
        self._refresh_identity_validation()

    def _refresh_identity_validation(
        self,
        _value: object = None,
        *,
        verify_writable: bool = False,
    ) -> None:
        settings = self.sections.to_settings()
        validation = validate_project_identity_destination(
            settings,
            self.location_edit.text(),
            verify_writable=verify_writable,
        )

        destination = validation.destination_file
        self._destination_collision = any(
            issue.field == "project_file"
            for issue in validation.issues
        )

        parent = validation.parent_folder
        show_create_folder = bool(
            parent is not None
            and not parent.exists()
        )
        self.create_location_button.setVisible(show_create_folder)

        if destination is None:
            self.destination_preview.setText("File proyek: -")
        elif self._destination_collision:
            self.destination_preview.setText(
                f"✕ File proyek sudah ada: {destination}"
            )
        else:
            self.destination_preview.setText(f"File proyek: {destination}")

        if validation.is_valid:
            self.set_step_state(
                0,
                WizardMilestoneState.VALID,
                "✓ Inisialisasi proyek siap.",
            )
            return

        first_issue = validation.issues[0]
        self.set_step_state(
            0,
            WizardMilestoneState.ERROR,
            first_issue.message,
        )

    def _source_validation_changed(
        self,
        result: SourceFilenameValidation | None,
    ) -> None:
        if result is None:
            if self._current_step == 1:
                message = (
                    "Folder Sumber wajib dipilih."
                    if not self.source_folder.text().strip()
                    else "Konfigurasi sumber berubah; validasi ulang sedang disiapkan."
                )
                self.set_step_state(1, WizardMilestoneState.ERROR, message)
            return

        if result.errors:
            self.set_step_state(
                1,
                WizardMilestoneState.ERROR,
                result.errors[0].message,
            )
            return

        episodes = result.episode_numbers
        episode_text = (
            f"episode {episodes[0]}–{episodes[-1]}"
            if episodes
            else "episode belum terbaca"
        )
        if result.warnings:
            self.set_step_state(
                1,
                WizardMilestoneState.WARNING,
                f"⚠ {result.file_count} file valid ({episode_text}). "
                f"{result.warnings[0].message}",
            )
        else:
            self.set_step_state(
                1,
                WizardMilestoneState.VALID,
                f"✓ {result.file_count} file sumber valid ({episode_text}).",
            )

    def _create_destination_folder(self) -> None:
        try:
            create_project_destination_folder(
                self.location_edit.text()
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Buat Folder",
                str(exc),
            )
            self._refresh_identity_validation()
            return

        self._refresh_identity_validation(verify_writable=True)

    def _show_setup_help(self) -> None:
        QMessageBox.information(
            self,
            "Bantuan Proyek Baru",
            (
                "Gunakan Kembali/Berikutnya untuk berpindah langkah. "
                "Project belum ditulis ke disk selama navigasi wizard.\n\n"
                "Bantuan folder filesystem dan Google Drive akan tersedia "
                "secara kontekstual pada langkah Folder & Tautan."
            ),
        )

    def _accept(self) -> None:
        location = self.location_edit.text().strip()
        settings = self.sections.to_settings()
        identity_validation = validate_project_identity_destination(
            settings,
            location,
            verify_writable=True,
        )
        if not identity_validation.is_valid:
            QMessageBox.warning(
                self,
                "Proyek Baru",
                identity_validation.issues[0].message,
            )
            self._refresh_identity_validation()
            self._show_step(0)
            return

        source_validation = self.source_section.validate_source_filenames()
        if not source_validation.is_valid:
            QMessageBox.warning(
                self,
                "Proyek Baru",
                source_validation.errors[0].message,
            )
            self._show_step(1)
            return

        issues = self.sections.validate_basic(strict_new_project=False)
        if issues:
            QMessageBox.warning(
                self,
                "Proyek Baru",
                issues[0].message,
            )
            self._show_step(0)
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
            self._show_step(0)
            return

        parent = Path(location).expanduser()
        if parent.exists() and not parent.is_dir():
            QMessageBox.warning(
                self,
                "Proyek Baru",
                "Lokasi penyimpanan proyek bukan folder.",
            )
            self._show_step(0)
            return

        self._settings = settings
        self._parent_folder = location
        self.accept()
