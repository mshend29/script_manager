from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.project_settings import ProjectSettings
from services.source_filename_service import (
    SourceFilenameAnalysis,
    read_source_filenames,
)


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
    SAMPLE_RATE_OPTIONS = (
        ("44.100 Hz", 44100),
        ("48.000 Hz", 48000),
        ("96.000 Hz", 96000),
        ("192.000 Hz", 192000),
    )
    BIT_DEPTH_OPTIONS = (
        ("16-bit", 16),
        ("24-bit", 24),
        ("32-bit", 32),
    )
    CHANNEL_OPTIONS = (
        ("Mono", 1),
        ("Stereo", 2),
    )

    def __init__(
        self,
        settings: ProjectSettings,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        self.setWindowTitle("Project Settings")
        self.resize(840, 720)
        self.setMinimumSize(720, 620)

        self._result_settings = settings
        self._source_filename_analysis: SourceFilenameAnalysis | None = None
        self._source_filename_examples: list[str] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel("Project Settings")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "Folder fields menggunakan filesystem path. Folder Google Drive Desktop "
            "diperlakukan seperti folder filesystem biasa (mis. D:\\My Drive\\...). "
            "Client Drive Links pada tab Project adalah URL browser dan tidak digunakan "
            "untuk membaca file."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_project_tab(settings), "Project")
        self.tabs.addTab(
            self._build_track_output_tab(settings),
            "Track Output & Delivery",
        )
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

    # ------------------------------------------------------------------
    # PROJECT TAB
    # ------------------------------------------------------------------

    def _build_project_tab(self, settings: ProjectSettings) -> QScrollArea:
        scroll, content, layout = self._scroll_tab()

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
            "Project Location ditampilkan sebagai informasi. Perpindahan project "
            "dilakukan melalui fitur Move Project."
        )
        location_note.setWordWrap(True)
        location_note.setObjectName("PageSubtitle")
        project_form.addRow("", location_note)
        layout.addWidget(project_group)

        layout.addWidget(self._build_source_group(settings))

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
        layout.addWidget(drive_group)
        layout.addStretch(1)

        scroll.setWidget(content)
        return scroll

    def _build_source_group(self, settings: ProjectSettings) -> QGroupBox:
        source_group = QGroupBox("Source Script")
        root = QVBoxLayout(source_group)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        source_form = QFormLayout()
        source_form.setLabelAlignment(Qt.AlignLeft)
        self.source_folder = FolderField(
            settings.source_folder,
            browse_caption="Select Source Script Folder (Filesystem)",
        )
        source_form.addRow("Source Folder", self.source_folder)
        root.addLayout(source_form)

        helper_grid = QGridLayout()
        helper_grid.setContentsMargins(0, 0, 0, 0)
        helper_grid.setHorizontalSpacing(12)
        helper_grid.setColumnStretch(0, 1)
        helper_grid.setColumnStretch(1, 1)

        filename_box = QGroupBox("Source Filename")
        filename_layout = QVBoxLayout(filename_box)
        filename_layout.setContentsMargins(10, 10, 10, 10)
        filename_layout.setSpacing(7)

        self.read_source_filenames_button = QPushButton("Get Source Filenames")
        self.read_source_filenames_button.setProperty("secondary", True)
        self.read_source_filenames_button.clicked.connect(
            self._read_source_filenames
        )
        filename_layout.addWidget(self.read_source_filenames_button)

        self.source_pattern_status = QLabel(
            "Belum membaca filename. Proses ini hanya membaca nama file, "
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
        self.source_filename_example.setPlaceholderText(
            "Representative source filename"
        )
        example_row.addWidget(self.source_filename_example, 1)

        self.copy_source_filename_button = QPushButton("Copy")
        self.copy_source_filename_button.setProperty("secondary", True)
        self.copy_source_filename_button.setEnabled(False)
        self.copy_source_filename_button.clicked.connect(
            self._copy_source_filename
        )
        example_row.addWidget(self.copy_source_filename_button)
        filename_layout.addLayout(example_row)

        self.source_pattern_details = QLabel("")
        self.source_pattern_details.setWordWrap(True)
        self.source_pattern_details.setObjectName("PageSubtitle")
        filename_layout.addWidget(self.source_pattern_details)

        self.filename_preview = QLabel(
            "Episode Preview: klik Get Source Filenames terlebih dahulu."
        )
        self.filename_preview.setWordWrap(True)
        self.filename_preview.setObjectName("PageSubtitle")
        filename_layout.addWidget(self.filename_preview)

        delimiter_box = QGroupBox("Episode Delimiter")
        delimiter_form = QFormLayout(delimiter_box)
        delimiter_form.setLabelAlignment(Qt.AlignLeft)

        self.episode_before = QLineEdit(settings.episode_before)
        self.episode_after = QLineEdit(settings.episode_after)
        self.episode_before.setPlaceholderText("contoh: 第")
        self.episode_after.setPlaceholderText("contoh: 集")

        delimiter_form.addRow("Before Episode Number", self.episode_before)
        delimiter_form.addRow("After Episode Number", self.episode_after)

        delimiter_help = QLabel(
            "Delimiter diterapkan ke filename yang dibaca dari Source Folder. "
            "Import Source tetap diperlukan untuk membaca isi naskah."
        )
        delimiter_help.setWordWrap(True)
        delimiter_help.setObjectName("PageSubtitle")
        delimiter_form.addRow("", delimiter_help)

        helper_grid.addWidget(filename_box, 0, 0)
        helper_grid.addWidget(delimiter_box, 0, 1)
        root.addLayout(helper_grid)

        self.episode_before.textChanged.connect(self._update_episode_preview)
        self.episode_after.textChanged.connect(self._update_episode_preview)
        self.source_folder.edit.textChanged.connect(self._source_folder_changed)

        return source_group

    # ------------------------------------------------------------------
    # TRACK OUTPUT & DELIVERY TAB
    # ------------------------------------------------------------------

    def _build_track_output_tab(
        self,
        settings: ProjectSettings,
    ) -> QScrollArea:
        scroll, content, layout = self._scroll_tab()

        track_group = QGroupBox("Track Output & Delivery")
        track_form = QFormLayout(track_group)
        track_form.setLabelAlignment(Qt.AlignLeft)

        self.stem_output_folder = FolderField(
            settings.stem_output_folder,
            browse_caption="Select Stem / Mixdown / Export Folder (Filesystem)",
        )
        self.delivery_folder = FolderField(
            settings.delivery_folder,
            browse_caption="Select Setoran Folder (Google Drive Desktop)",
        )

        format_value = QLabel("WAV")
        format_value.setStyleSheet("font-weight: 700;")

        self.audio_sample_rate = QComboBox()
        for label, value in self.SAMPLE_RATE_OPTIONS:
            self.audio_sample_rate.addItem(label, value)
        self._select_combo_data(
            self.audio_sample_rate,
            int(settings.audio_sample_rate or 48000),
            48000,
        )

        self.audio_bit_depth = QComboBox()
        for label, value in self.BIT_DEPTH_OPTIONS:
            self.audio_bit_depth.addItem(label, value)
        self._select_combo_data(
            self.audio_bit_depth,
            int(settings.audio_bit_depth or 24),
            24,
        )

        self.audio_channels = QComboBox()
        for label, value in self.CHANNEL_OPTIONS:
            self.audio_channels.addItem(label, value)
        self._select_combo_data(
            self.audio_channels,
            int(settings.audio_channels or 1),
            1,
        )

        track_form.addRow("Stem / Mixdown / Export", self.stem_output_folder)
        track_form.addRow("Setoran Folder", self.delivery_folder)
        track_form.addRow("Audio Format", format_value)
        track_form.addRow("Sample Rate", self.audio_sample_rate)
        track_form.addRow("Bit Depth", self.audio_bit_depth)
        track_form.addRow("Channels", self.audio_channels)

        track_help = QLabel(
            "Kedua folder adalah filesystem path; Setoran dapat langsung menunjuk "
            "folder Google Drive Desktop. WAV 32-bit menerima PCM integer maupun "
            "32-bit float dari DAW."
        )
        track_help.setWordWrap(True)
        track_help.setObjectName("PageSubtitle")
        track_form.addRow("", track_help)

        layout.addWidget(track_group)
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

    @staticmethod
    def _select_combo_data(
        combo: QComboBox,
        value: int,
        fallback: int,
    ) -> None:
        index = combo.findData(int(value))
        if index < 0:
            index = combo.findData(int(fallback))
        combo.setCurrentIndex(max(index, 0))

    # ------------------------------------------------------------------
    # SOURCE FILENAME HELPER
    # ------------------------------------------------------------------

    def _source_folder_changed(self) -> None:
        self._source_filename_analysis = None
        self._source_filename_examples = []
        self.source_filename_example.clear()
        self.copy_source_filename_button.setEnabled(False)
        self.source_pattern_status.setText(
            "Source Folder berubah. Klik Get Source Filenames untuk membaca ulang."
        )
        self.source_pattern_details.clear()
        self.filename_preview.setText(
            "Episode Preview: klik Get Source Filenames terlebih dahulu."
        )

    def _read_source_filenames(self) -> None:
        try:
            analysis = read_source_filenames(self.source_folder.text())
        except Exception as exc:
            self._source_filename_analysis = None
            self._source_filename_examples = []
            self.source_filename_example.clear()
            self.copy_source_filename_button.setEnabled(False)
            self.source_pattern_status.setText(f"⚠ {exc}")
            self.source_pattern_details.clear()
            self._update_episode_preview()
            return

        self._source_filename_analysis = analysis
        self._source_filename_examples = self._preview_examples(
            list(analysis.filenames)
        )

        if not analysis.filenames:
            self.source_filename_example.clear()
            self.copy_source_filename_button.setEnabled(False)
            self.source_pattern_status.setText(
                "⚠ Tidak ada file .xlsx/.xlsm pada Source Folder."
            )
            self.source_pattern_details.clear()
            self._update_episode_preview()
            return

        representative = analysis.representative_filename
        self.source_filename_example.setText(representative)
        self.copy_source_filename_button.setEnabled(bool(representative))

        if analysis.is_consistent:
            pattern = analysis.patterns[0]
            self.source_pattern_status.setText(
                f"✓ {pattern.count} filename mengikuti satu pola."
            )
            self.source_pattern_details.setText(
                f"Pattern: {pattern.pattern}"
            )
        else:
            self.source_pattern_status.setText(
                "⚠ Ditemukan lebih dari satu pola filename atau lebih dari satu "
                "bagian angka yang berubah."
            )
            details = []
            for pattern in analysis.patterns[:8]:
                marker = "✓" if pattern.is_episode_candidate else "⚠"
                details.append(
                    f"{marker} {pattern.count} × {pattern.pattern}"
                )
            if len(analysis.patterns) > 8:
                details.append(
                    f"… {len(analysis.patterns) - 8} pola lainnya"
                )
            self.source_pattern_details.setText("\n".join(details))

        self._update_episode_preview()

    def _copy_source_filename(self) -> None:
        filename = self.source_filename_example.text().strip()
        if filename:
            QApplication.clipboard().setText(filename)

    @staticmethod
    def _preview_examples(filenames: list[str]) -> list[str]:
        if not filenames:
            return []
        indexes = {0, len(filenames) // 2, len(filenames) - 1}
        return [filenames[index] for index in sorted(indexes)]

    def _update_episode_preview(self) -> None:
        if not self._source_filename_examples:
            self.filename_preview.setText(
                "Episode Preview: klik Get Source Filenames terlebih dahulu."
            )
            return

        before = self.episode_before.text()
        after = self.episode_after.text()
        lines = ["Episode Preview:"]
        for filename in self._source_filename_examples:
            episode = self._extract_episode_preview(
                filename,
                before,
                after,
            )
            lines.append(
                f"{filename}  →  {episode if episode else '⚠ tidak terbaca'}"
            )
        self.filename_preview.setText("\n".join(lines))

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
        return result if result and result.isdigit() else None

    # ------------------------------------------------------------------
    # SAVE
    # ------------------------------------------------------------------

    def _accept_settings(self) -> None:
        self._result_settings = ProjectSettings(
            project_name=self.project_name.text(),
            project_code=self.project_code.text(),
            client_name=self.client_name.text(),
            start_date=self.start_date.date().toString("yyyy-MM-dd"),
            project_folder=self.project_folder.text(),
            source_folder=self.source_folder.text(),
            stem_output_folder=self.stem_output_folder.text(),
            delivery_folder=self.delivery_folder.text(),
            audio_format="WAV",
            audio_sample_rate=int(self.audio_sample_rate.currentData() or 48000),
            audio_bit_depth=int(self.audio_bit_depth.currentData() or 24),
            audio_channels=int(self.audio_channels.currentData() or 1),
            episode_before=self.episode_before.text(),
            episode_after=self.episode_after.text(),
            main_drive_url=self.main_drive_url.text(),
            material_drive_url=self.material_drive_url.text(),
            delivery_drive_url=self.delivery_drive_url.text(),
        ).normalized()

        self.accept()
