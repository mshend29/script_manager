from __future__ import annotations

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QVBoxLayout,
)

from import_engine.source_sync import SourceSyncProgress, SourceSyncReport


class InitialSourceSyncPanel(QGroupBox):
    """Progress and result surface for the final New Project milestone."""

    _STAGE_LABELS = {
        "creating_project": "Membuat project",
        "scanning": "Memindai sumber",
        "classifying": "Mengklasifikasikan sumber",
        "inspecting": "Membuka workbook",
        "parsing": "Membaca naskah",
        "diffing": "Menyiapkan perubahan",
        "preview_ready": "Rencana sinkronisasi siap",
        "backup": "Membuat safety backup",
        "synchronizing": "Menerapkan data sumber",
        "complete": "Sinkronisasi selesai",
        "verifying": "Memverifikasi database",
        "ready": "Project siap",
    }

    def __init__(self, parent=None) -> None:
        super().__init__("Pembuatan Project & Initial Source Sync", parent)
        self.hide()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self.status_label = QLabel(
            "Klik Buat Proyek untuk membuat .smproj dan mengisi database dari sumber."
        )
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("PageSubtitle")
        root.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(True)
        root.addWidget(self.progress_bar)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(120)
        self.details.hide()
        root.addWidget(self.details)

    def set_running(self) -> None:
        self.show()
        self.details.clear()
        self.details.hide()
        self.summary_label.clear()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat("")
        self.status_label.setText(
            "Membuat project dan menjalankan Initial Source Sync…"
        )

    @Slot(object)
    def update_progress(self, progress: SourceSyncProgress) -> None:
        self.show()
        if progress.is_determinate:
            total = max(int(progress.total), 1)
            current = max(0, min(int(progress.current), total))
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)
            self.progress_bar.setFormat("%v/%m")
        else:
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setFormat("")

        label = self._STAGE_LABELS.get(progress.stage, "Initial Source Sync")
        message = str(progress.message or "").strip()
        file_name = str(progress.file_name or "").strip()
        text = label
        if message:
            text = f"{label} — {message}"
        if file_name:
            text = f"{text} — {file_name}"
        self.status_label.setText(text)

    def set_success(self, report: SourceSyncReport) -> None:
        self.show()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("100%")
        self.status_label.setText("✓ Project dan Initial Source Sync selesai.")
        self.summary_label.setText(
            f"{report.scanned} episode sumber · "
            f"{report.parsed_dialogues} dialog · "
            f"{report.auto_locked} cast terkunci otomatis · "
            f"{report.unresolved_cast} belum terpetakan"
        )
        detail_lines = [f"⚠ {message}" for message in report.warnings]
        self.details.setPlainText("\n".join(detail_lines))
        self.details.setVisible(bool(detail_lines))

    def set_error(self, message: str) -> None:
        self.show()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Gagal")
        self.status_label.setText(
            "✕ Project belum berhasil dibuat. Artefak sementara sudah di-rollback."
        )
        self.summary_label.setText(
            "Perbaiki penyebab di bawah, lalu klik Buat Proyek untuk mencoba lagi."
        )
        self.details.setPlainText(str(message or "Unknown error"))
        self.details.show()
