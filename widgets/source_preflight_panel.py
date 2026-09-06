from __future__ import annotations

from threading import Event

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from services.source_preflight_service import (
    SourcePreflightProgress,
    SourcePreflightReport,
    SourcePreflightService,
)
from services.source_setup_validation import SourceFilenameValidation


class SourcePreflightWorker(QObject):
    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        filename_validation: SourceFilenameValidation,
        *,
        service: SourcePreflightService | None = None,
    ) -> None:
        super().__init__()
        self.filename_validation = filename_validation
        self.service = service or SourcePreflightService()
        self._cancel_event = Event()

    def request_cancel(self) -> None:
        self._cancel_event.set()

    @Slot()
    def run(self) -> None:
        try:
            report = self.service.run(
                self.filename_validation,
                progress_callback=self.progress.emit,
                cancel_callback=self._cancel_event.is_set,
            )
        except Exception as exc:  # noqa: BLE001 - worker boundary
            self.failed.emit(str(exc))
            return
        self.finished.emit(report)


class SourcePreflightPanel(QGroupBox):
    start_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("Preflight Workbook", parent)
        self._filename_validation: SourceFilenameValidation | None = None
        self._running = False

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        help_label = QLabel(
            "Preflight membuka workbook secara read-only memakai inspector dan parser "
            "yang sama dengan Sinkronkan Sumber. Tidak ada data yang ditulis ke project."
        )
        help_label.setWordWrap(True)
        help_label.setObjectName("PageSubtitle")
        root.addWidget(help_label)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(8)

        self.start_button = QPushButton("Jalankan Preflight")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_requested.emit)
        action_row.addWidget(self.start_button)

        self.cancel_button = QPushButton("Batalkan Preflight")
        self.cancel_button.setProperty("secondary", True)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        self.cancel_button.hide()
        action_row.addWidget(self.cancel_button)
        action_row.addStretch(1)
        root.addLayout(action_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        root.addWidget(self.progress_bar)

        self.status_label = QLabel(
            "Validasi nama file harus lolos sebelum preflight dijalankan."
        )
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("PageSubtitle")
        root.addWidget(self.status_label)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Error dan warning per file akan tampil di sini.")
        self.details.setMaximumHeight(140)
        root.addWidget(self.details)

    @property
    def is_running(self) -> bool:
        return self._running

    def set_filename_validation(
        self,
        validation: SourceFilenameValidation | None,
    ) -> None:
        self._filename_validation = validation
        if self._running:
            return

        self.progress_bar.setValue(0)
        self.summary_label.clear()
        self.details.clear()
        ready = bool(validation is not None and validation.is_valid)
        self.start_button.setEnabled(ready)
        if validation is None:
            self.status_label.setText(
                "Validasi nama file harus lolos sebelum preflight dijalankan."
            )
        elif validation.errors:
            self.status_label.setText(
                "Perbaiki masalah filename sebelum menjalankan preflight."
            )
        else:
            self.status_label.setText(
                f"{validation.file_count} filename siap. Jalankan preflight workbook."
            )

    def set_running(self, running: bool) -> None:
        self._running = bool(running)
        self.start_button.setEnabled(
            not self._running
            and self._filename_validation is not None
            and self._filename_validation.is_valid
        )
        self.cancel_button.setVisible(self._running)
        self.cancel_button.setEnabled(self._running)
        if self._running:
            self.progress_bar.setValue(0)
            self.summary_label.clear()
            self.details.clear()
            self.status_label.setText("Preflight sedang berjalan…")

    def set_cancelling(self) -> None:
        if not self._running:
            return
        self.cancel_button.setEnabled(False)
        self.status_label.setText(
            "Membatalkan preflight setelah operasi workbook saat ini selesai…"
        )

    @Slot(object)
    def update_progress(self, progress: SourcePreflightProgress) -> None:
        total = max(int(progress.total), 1)
        current = max(0, min(int(progress.current), total))
        self.progress_bar.setValue(round(current / total * 100))
        message = progress.message
        if progress.file_name:
            message = f"{message} — {progress.file_name}"
        self.status_label.setText(message)

    def set_report(self, report: SourcePreflightReport) -> None:
        self.set_running(False)

        if report.cancelled:
            self.progress_bar.setValue(0)
            self.status_label.setText("Preflight dibatalkan. Jalankan ulang untuk melanjutkan.")
        elif report.is_valid:
            self.progress_bar.setValue(100)
            self.status_label.setText("✓ Preflight source selesai.")
        else:
            self.status_label.setText(
                f"✕ Preflight menemukan {len(report.problems)} masalah blocking."
            )

        ready_episodes = len(
            {item.episode_number for item in report.files if item.parsed}
        )
        workbook_ok = report.inspected_files == len(report.files) and bool(report.files)
        structure_ok = report.parsed_files == len(report.files) and bool(report.files)
        summary_lines = [
            "✓ Nama file terbaca",
            "✓ Nomor episode terbaca",
            (
                f"✓ Workbook dapat dibuka ({report.inspected_files}/{len(report.files)})"
                if workbook_ok
                else f"✕ Workbook dapat dibuka ({report.inspected_files}/{len(report.files)})"
            ),
            "✓ Struktur naskah dikenali" if structure_ok else "✕ Struktur naskah belum siap",
            (
                f"✓ {ready_episodes} episode siap diimpor · "
                f"{report.parsed_dialogues} dialog"
                if report.is_valid
                else f"✕ {ready_episodes} episode lolos parsing"
            ),
        ]
        self.summary_label.setText("\n".join(summary_lines))

        detail_lines = [f"✕ {message}" for message in report.problems]
        detail_lines.extend(f"⚠ {message}" for message in report.warnings)
        self.details.setPlainText("\n".join(detail_lines))
