from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QDate, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.project_settings import (
    SUPPORTED_AUDIO_BIT_DEPTHS,
    SUPPORTED_AUDIO_CHANNELS,
    SUPPORTED_AUDIO_SAMPLE_RATES,
    ProjectSettings,
    ProjectSettingsIssue,
    validate_project_settings_contract,
)
from services.source_filename_service import SourceFilenameAnalysis
from services.source_setup_validation import (
    SourceFilenameValidation,
    validate_source_filenames as validate_source_filename_setup,
)


class FolderField(QWidget):
    def __init__(
        self,
        value: str = "",
        *,
        browse_caption: str = "Pilih Folder",
        read_only: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.browse_caption = browse_caption

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.edit = QLineEdit(value)
        self.edit.setReadOnly(read_only)
        layout.addWidget(self.edit, 1)

        self.browse_button = QPushButton("Telusuri…")
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

    def setText(self, value: str) -> None:  # noqa: N802 - Qt-style compatibility
        self.edit.setText(str(value or ""))


class ProjectIdentitySection(QGroupBox):
    def __init__(
        self,
        settings: ProjectSettings | None = None,
        *,
        show_project_file: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Proyek", parent)
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignLeft)

        self.project_name = QLineEdit()
        self.project_code = QLineEdit()
        self.client_name = QLineEdit()
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("dd MMMM yyyy")

        form.addRow("Nama Proyek", self.project_name)
        form.addRow("Kode Proyek", self.project_code)
        form.addRow("Klien", self.client_name)
        form.addRow("Tanggal Mulai", self.start_date)

        self.project_file: FolderField | None = None
        if show_project_file:
            self.project_file = FolderField(read_only=True)
            form.addRow("File Proyek", self.project_file)

            note = QLabel(
                "File Proyek hanya menunjukkan lokasi file .smproj yang sedang dibuka. "
                "File dapat dipindahkan saat proyek tidak sedang digunakan."
            )
            note.setWordWrap(True)
            note.setObjectName("PageSubtitle")
            form.addRow("", note)

        self.load_settings(settings or ProjectSettings())

    def load_settings(self, settings: ProjectSettings) -> None:
        self.project_name.setText(settings.project_name)
        self.project_code.setText(settings.project_code)
        self.client_name.setText(settings.client_name)
        parsed = QDate.fromString(settings.start_date, "yyyy-MM-dd")
        self.start_date.setDate(parsed if parsed.isValid() else QDate.currentDate())
        if self.project_file is not None:
            self.project_file.setText(settings.project_folder)

    def values(self) -> dict[str, object]:
        return {
            "project_name": self.project_name.text(),
            "project_code": self.project_code.text(),
            "client_name": self.client_name.text(),
            "start_date": self.start_date.date().toString("yyyy-MM-dd"),
            "project_folder": (
                self.project_file.text() if self.project_file is not None else ""
            ),
        }


class SourceConfigurationSection(QGroupBox):
    validation_changed = Signal(object)

    def __init__(
        self,
        settings: ProjectSettings | None = None,
        *,
        auto_validate: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Naskah Sumber", parent)
        self._source_filename_analysis: SourceFilenameAnalysis | None = None
        self._source_filename_validation: SourceFilenameValidation | None = None
        self._source_filename_examples: list[str] = []
        self._auto_validate = bool(auto_validate)

        self._validation_timer = QTimer(self)
        self._validation_timer.setSingleShot(True)
        self._validation_timer.setInterval(300)
        self._validation_timer.timeout.connect(self.validate_source_filenames)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        source_form = QFormLayout()
        source_form.setLabelAlignment(Qt.AlignLeft)
        self.source_folder = FolderField(
            browse_caption="Pilih Folder Naskah Sumber (Filesystem)"
        )
        source_form.addRow("Folder Sumber", self.source_folder)
        root.addLayout(source_form)

        helper_grid = QGridLayout()
        helper_grid.setContentsMargins(0, 0, 0, 0)
        helper_grid.setHorizontalSpacing(12)
        helper_grid.setColumnStretch(0, 1)
        helper_grid.setColumnStretch(1, 1)

        filename_box = QGroupBox("Nama File Sumber")
        filename_layout = QVBoxLayout(filename_box)
        filename_layout.setContentsMargins(10, 10, 10, 10)
        filename_layout.setSpacing(7)

        self.read_source_filenames_button = QPushButton("Baca Nama File Sumber")
        self.read_source_filenames_button.setProperty("secondary", True)
        self.read_source_filenames_button.clicked.connect(self.read_source_filenames)
        filename_layout.addWidget(self.read_source_filenames_button)

        self.source_pattern_status = QLabel(
            "Belum membaca nama file. Proses ini hanya membaca nama file, "
            "bukan isi workbook."
        )
        self.source_pattern_status.setWordWrap(True)
        self.source_pattern_status.setObjectName("PageSubtitle")
        filename_layout.addWidget(self.source_pattern_status)

        example_row = QHBoxLayout()
        example_row.setContentsMargins(0, 0, 0, 0)
        example_row.setSpacing(6)

        self.source_filename_example = QLineEdit()
        self.source_filename_example.setReadOnly(True)
        self.source_filename_example.setPlaceholderText("Nama file sumber contoh")
        example_row.addWidget(self.source_filename_example, 1)

        self.copy_source_filename_button = QPushButton("Salin")
        self.copy_source_filename_button.setProperty("secondary", True)
        self.copy_source_filename_button.setEnabled(False)
        self.copy_source_filename_button.clicked.connect(self._copy_source_filename)
        example_row.addWidget(self.copy_source_filename_button)
        filename_layout.addLayout(example_row)

        self.source_pattern_details = QLabel("")
        self.source_pattern_details.setWordWrap(True)
        self.source_pattern_details.setObjectName("PageSubtitle")
        filename_layout.addWidget(self.source_pattern_details)

        self.filename_preview = QLabel(
            "Pratinjau Episode: validasi nama file belum dijalankan."
        )
        self.filename_preview.setWordWrap(True)
        self.filename_preview.setObjectName("PageSubtitle")
        filename_layout.addWidget(self.filename_preview)

        delimiter_box = QGroupBox("Pemisah Episode")
        delimiter_form = QFormLayout(delimiter_box)
        delimiter_form.setLabelAlignment(Qt.AlignLeft)

        self.episode_before = QLineEdit()
        self.episode_after = QLineEdit()
        self.episode_before.setPlaceholderText("contoh: 第")
        self.episode_after.setPlaceholderText("contoh: 集")
        delimiter_form.addRow("Sebelum Nomor Episode", self.episode_before)
        delimiter_form.addRow("Setelah Nomor Episode", self.episode_after)

        delimiter_help = QLabel(
            "Pemisah diterapkan ke seluruh nama file pada Folder Sumber. "
            "Isi workbook belum dibaca pada tahap filename validation."
        )
        delimiter_help.setWordWrap(True)
        delimiter_help.setObjectName("PageSubtitle")
        delimiter_form.addRow("", delimiter_help)

        helper_grid.addWidget(filename_box, 0, 0)
        helper_grid.addWidget(delimiter_box, 0, 1)
        root.addLayout(helper_grid)

        self.episode_before.textChanged.connect(self._configuration_changed)
        self.episode_after.textChanged.connect(self._configuration_changed)
        self.source_folder.edit.textChanged.connect(self._configuration_changed)

        self.load_settings(settings or ProjectSettings())

    @property
    def analysis(self) -> SourceFilenameAnalysis | None:
        return self._source_filename_analysis

    @property
    def validation(self) -> SourceFilenameValidation | None:
        return self._source_filename_validation

    def load_settings(self, settings: ProjectSettings) -> None:
        self.source_folder.setText(settings.source_folder)
        self.episode_before.setText(settings.episode_before)
        self.episode_after.setText(settings.episode_after)
        self._configuration_changed()

    def values(self) -> dict[str, object]:
        return {
            "source_folder": self.source_folder.text(),
            "episode_before": self.episode_before.text(),
            "episode_after": self.episode_after.text(),
        }

    def _configuration_changed(self, _value: object = None) -> None:
        self._validation_timer.stop()
        self._source_filename_analysis = None
        self._source_filename_validation = None
        self._source_filename_examples = []
        self.source_filename_example.clear()
        self.copy_source_filename_button.setEnabled(False)
        self.source_pattern_details.clear()
        self.filename_preview.setText(
            "Pratinjau Episode: validasi nama file belum dijalankan."
        )

        if self._auto_validate and self.source_folder.text():
            self.source_pattern_status.setText(
                "Membaca dan memvalidasi seluruh nama file sumber…"
            )
            self._validation_timer.start()
        elif self.source_folder.text():
            self.source_pattern_status.setText(
                "Konfigurasi sumber berubah. Klik Baca Nama File Sumber untuk "
                "memvalidasi ulang seluruh filename."
            )
        else:
            self.source_pattern_status.setText("Folder Sumber belum dipilih.")

        self.validation_changed.emit(None)

    def read_source_filenames(self) -> SourceFilenameValidation:
        return self.validate_source_filenames()

    def validate_source_filenames(self) -> SourceFilenameValidation:
        self._validation_timer.stop()
        result = validate_source_filename_setup(
            self.source_folder.text(),
            episode_before=self.episode_before.text(),
            episode_after=self.episode_after.text(),
        )
        self._source_filename_validation = result
        self._source_filename_analysis = result.analysis
        self._source_filename_examples = [
            item.file_name for item in result.preview_mappings
        ]
        self._render_source_validation(result)
        self.validation_changed.emit(result)
        return result

    def _render_source_validation(self, result: SourceFilenameValidation) -> None:
        analysis = result.analysis
        representative = analysis.representative_filename if analysis is not None else ""
        self.source_filename_example.setText(representative)
        self.copy_source_filename_button.setEnabled(bool(representative))

        if result.errors:
            self.source_pattern_status.setText(
                f"✕ {result.file_count} file sumber ditemukan; "
                f"{len(result.errors)} masalah blocking."
            )
        elif result.warnings:
            self.source_pattern_status.setText(
                f"⚠ {result.file_count} file sumber terbaca; "
                f"{len(result.warnings)} warning."
            )
        else:
            self.source_pattern_status.setText(
                f"✓ {result.file_count} file sumber terbaca dan seluruh episode valid."
            )

        detail_lines: list[str] = []
        if analysis is not None and analysis.patterns:
            for pattern in analysis.patterns[:8]:
                marker = "✓" if len(analysis.patterns) == 1 else "✕"
                detail_lines.append(
                    f"{marker} {pattern.count} × {pattern.pattern}"
                )
            if len(analysis.patterns) > 8:
                detail_lines.append(f"… {len(analysis.patterns) - 8} pola lainnya")

        issue_lines = [
            f"{'⚠' if issue.severity == 'warning' else '✕'} {issue.message}"
            for issue in result.issues[:8]
        ]
        if len(result.issues) > 8:
            issue_lines.append(f"… {len(result.issues) - 8} masalah lainnya")

        self.source_pattern_details.setText(
            "\n".join([*detail_lines, *issue_lines])
        )

        if result.preview_mappings:
            lines = ["Pratinjau Episode (awal / tengah / akhir):"]
            for item in result.preview_mappings:
                lines.append(
                    f"{item.file_name}  →  {item.raw_value} "
                    f"(Episode {item.episode_number})"
                )
            self.filename_preview.setText("\n".join(lines))
        else:
            filename_errors = [
                issue.message
                for issue in result.errors
                if issue.field == "source_filename"
            ]
            if filename_errors:
                self.filename_preview.setText(
                    "Pratinjau Episode:\n"
                    + "\n".join(f"✕ {message}" for message in filename_errors[:3])
                )
            else:
                self.filename_preview.setText(
                    "Pratinjau Episode: belum ada episode yang dapat ditampilkan."
                )

    def _copy_source_filename(self) -> None:
        filename = self.source_filename_example.text().strip()
        if filename:
            QApplication.clipboard().setText(filename)


class AudioOutputSection(QGroupBox):
    SAMPLE_RATE_LABELS = {
        44100: "44.100 Hz",
        48000: "48.000 Hz",
        96000: "96.000 Hz",
        192000: "192.000 Hz",
    }
    BIT_DEPTH_LABELS = {16: "16-bit", 24: "24-bit", 32: "32-bit"}
    CHANNEL_LABELS = {1: "Mono", 2: "Stereo"}

    def __init__(
        self,
        settings: ProjectSettings | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Output Track & Setoran", parent)
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignLeft)

        self.stem_output_folder = FolderField(
            browse_caption="Pilih Folder Stem / Mixdown / Export (Filesystem)"
        )
        self.delivery_folder = FolderField(
            browse_caption="Pilih Folder Setoran (Google Drive Desktop)"
        )

        self.format_value = QLabel("WAV")
        self.format_value.setStyleSheet("font-weight: 700;")

        self.audio_sample_rate = QComboBox()
        for value in SUPPORTED_AUDIO_SAMPLE_RATES:
            self.audio_sample_rate.addItem(self.SAMPLE_RATE_LABELS[value], value)

        self.audio_bit_depth = QComboBox()
        for value in SUPPORTED_AUDIO_BIT_DEPTHS:
            self.audio_bit_depth.addItem(self.BIT_DEPTH_LABELS[value], value)

        self.audio_channels = QComboBox()
        for value in SUPPORTED_AUDIO_CHANNELS:
            self.audio_channels.addItem(self.CHANNEL_LABELS[value], value)

        form.addRow("Stem / Mixdown / Export", self.stem_output_folder)
        form.addRow("Folder Setoran", self.delivery_folder)
        form.addRow("Format Audio", self.format_value)
        form.addRow("Laju Sampel", self.audio_sample_rate)
        form.addRow("Kedalaman Bit", self.audio_bit_depth)
        form.addRow("Kanal", self.audio_channels)

        note = QLabel(
            "Kedua folder adalah filesystem path; Setoran dapat langsung menunjuk "
            "folder Google Drive Desktop. WAV 32-bit menerima PCM integer maupun "
            "32-bit float dari DAW."
        )
        note.setWordWrap(True)
        note.setObjectName("PageSubtitle")
        form.addRow("", note)

        self.load_settings(settings or ProjectSettings())

    def load_settings(self, settings: ProjectSettings) -> None:
        self.stem_output_folder.setText(settings.stem_output_folder)
        self.delivery_folder.setText(settings.delivery_folder)
        self._select_combo_data(
            self.audio_sample_rate,
            int(settings.audio_sample_rate or 48000),
            48000,
        )
        self._select_combo_data(
            self.audio_bit_depth,
            int(settings.audio_bit_depth or 24),
            24,
        )
        self._select_combo_data(
            self.audio_channels,
            int(settings.audio_channels or 1),
            1,
        )

    @staticmethod
    def _select_combo_data(combo: QComboBox, value: int, fallback: int) -> None:
        index = combo.findData(int(value))
        if index < 0:
            index = combo.findData(int(fallback))
        combo.setCurrentIndex(max(index, 0))

    def values(self) -> dict[str, object]:
        return {
            "stem_output_folder": self.stem_output_folder.text(),
            "delivery_folder": self.delivery_folder.text(),
            "audio_format": "WAV",
            "audio_sample_rate": int(self.audio_sample_rate.currentData() or 48000),
            "audio_bit_depth": int(self.audio_bit_depth.currentData() or 24),
            "audio_channels": int(self.audio_channels.currentData() or 1),
        }


class DriveLinksSection(QGroupBox):
    def __init__(
        self,
        settings: ProjectSettings | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Tautan Drive Klien", parent)
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignLeft)

        self.main_drive_url = QLineEdit()
        self.material_drive_url = QLineEdit()
        self.delivery_drive_url = QLineEdit()
        self.main_drive_url.setPlaceholderText("https://drive.google.com/...")
        self.material_drive_url.setPlaceholderText("opsional")
        self.delivery_drive_url.setPlaceholderText("opsional")

        form.addRow("Drive Utama", self.main_drive_url)
        form.addRow("Folder Material", self.material_drive_url)
        form.addRow("Setoran", self.delivery_drive_url)

        self.load_settings(settings or ProjectSettings())

    def load_settings(self, settings: ProjectSettings) -> None:
        self.main_drive_url.setText(settings.main_drive_url)
        self.material_drive_url.setText(settings.material_drive_url)
        self.delivery_drive_url.setText(settings.delivery_drive_url)

    def values(self) -> dict[str, object]:
        return {
            "main_drive_url": self.main_drive_url.text(),
            "material_drive_url": self.material_drive_url.text(),
            "delivery_drive_url": self.delivery_drive_url.text(),
        }


@dataclass
class ProjectConfigurationSections:
    identity: ProjectIdentitySection
    source: SourceConfigurationSection
    audio: AudioOutputSection
    links: DriveLinksSection

    def load_settings(self, settings: ProjectSettings) -> None:
        self.identity.load_settings(settings)
        self.source.load_settings(settings)
        self.audio.load_settings(settings)
        self.links.load_settings(settings)

    def to_settings(self, *, project_folder: str = "") -> ProjectSettings:
        values: dict[str, object] = {}
        values.update(self.identity.values())
        values.update(self.source.values())
        values.update(self.audio.values())
        values.update(self.links.values())
        if project_folder:
            values["project_folder"] = project_folder
        return ProjectSettings.from_dict(values).normalized()

    def validate_basic(
        self,
        *,
        strict_new_project: bool = False,
    ) -> tuple[ProjectSettingsIssue, ...]:
        return validate_project_settings_contract(
            self.to_settings(),
            strict_new_project=strict_new_project,
        )
