from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.windows_prerequisite_service import (
    GOOGLE_DRIVE_HELP_URL,
    GoogleDriveReadinessReport,
    GoogleDriveReadinessService,
    GoogleDriveReadinessState,
)


class GoogleDriveReadinessDialog(QDialog):
    """Explain Google Drive installation/readiness without handling credentials."""

    def __init__(
        self,
        service: GoogleDriveReadinessService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service or GoogleDriveReadinessService()
        self.report: GoogleDriveReadinessReport | None = None

        self.setWindowTitle("Status Google Drive")
        self.setModal(True)
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(12)

        title = QLabel("Google Drive for desktop")
        title.setObjectName("GoogleDriveReadinessTitle")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        root.addWidget(title)

        self.status_label = QLabel()
        self.status_label.setObjectName("GoogleDriveReadinessStatus")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        root.addWidget(self.status_label)

        self.detail_label = QLabel()
        self.detail_label.setObjectName("GoogleDriveReadinessDetail")
        self.detail_label.setWordWrap(True)
        self.detail_label.setTextInteractionFlags(
            self.detail_label.textInteractionFlags()
        )
        root.addWidget(self.detail_label)

        note = QLabel(
            "Script Manager hanya memeriksa aplikasi dan akses filesystem. "
            "Login dan credential Google tetap dikelola oleh Google Drive."
        )
        note.setObjectName("GoogleDriveReadinessPrivacyNote")
        note.setWordWrap(True)
        note.setStyleSheet("color: #717784;")
        root.addWidget(note)

        root.addSpacing(4)
        actions = QHBoxLayout()
        actions.setSpacing(8)

        self.help_button = QPushButton("Panduan Google Drive")
        self.help_button.setObjectName("GoogleDriveHelpButton")
        self.help_button.clicked.connect(self._open_help)
        actions.addWidget(self.help_button)

        actions.addStretch(1)

        self.open_button = QPushButton("Buka Google Drive")
        self.open_button.setObjectName("GoogleDriveOpenButton")
        self.open_button.clicked.connect(self._open_google_drive)
        actions.addWidget(self.open_button)

        self.retry_button = QPushButton("Periksa Lagi")
        self.retry_button.setObjectName("GoogleDriveRetryButton")
        self.retry_button.clicked.connect(self.refresh_status)
        actions.addWidget(self.retry_button)

        self.close_button = QPushButton("Tutup")
        self.close_button.setObjectName("GoogleDriveCloseButton")
        self.close_button.clicked.connect(self.accept)
        actions.addWidget(self.close_button)

        root.addLayout(actions)
        self.refresh_status()

    def refresh_status(self) -> None:
        self.report = self.service.check()
        self._apply_report(self.report)

    def _apply_report(self, report: GoogleDriveReadinessReport) -> None:
        state = report.state
        self.retry_button.setVisible(
            state != GoogleDriveReadinessState.UNSUPPORTED_SYSTEM
        )
        self.open_button.setVisible(
            report.installed
            and state
            in {
                GoogleDriveReadinessState.INSTALLED_NOT_RUNNING,
                GoogleDriveReadinessState.RUNNING_NOT_READY,
                GoogleDriveReadinessState.CHECK_ERROR,
            }
        )

        if state == GoogleDriveReadinessState.UNSUPPORTED_SYSTEM:
            self.status_label.setText("Tidak berlaku pada sistem ini")
            self.detail_label.setText(
                "Pemeriksaan Google Drive for desktop pada Phase 12 ditujukan "
                "untuk paket Windows."
            )
            return

        if state == GoogleDriveReadinessState.NOT_INSTALLED:
            self.status_label.setText("Belum terpasang")
            self.detail_label.setText(
                "Google Drive for desktop belum terdeteksi. Instal Google Drive, "
                "login melalui aplikasi Google, lalu klik Periksa Lagi."
            )
            return

        if state == GoogleDriveReadinessState.INSTALLED_NOT_RUNNING:
            self.status_label.setText("Terpasang, belum berjalan")
            self.detail_label.setText(
                "Google Drive sudah terpasang tetapi belum berjalan. Klik Buka "
                "Google Drive, selesaikan login bila diminta, lalu klik Periksa Lagi."
            )
            return

        if state == GoogleDriveReadinessState.RUNNING_NOT_READY:
            self.status_label.setText("Terpasang, belum siap digunakan")
            details = (
                "Google Drive sedang berjalan, tetapi filesystem Google Drive belum "
                "terdeteksi. Selesaikan login/sinkronisasi di Google Drive lalu klik "
                "Periksa Lagi. Jika komputer dikelola kantor atau memakai konfigurasi "
                "mirror khusus, pastikan folder Drive sudah terlihat di File Explorer."
            )
            if report.drivefs_data_dir:
                details += f"\n\nDriveFS terinisialisasi di: {report.drivefs_data_dir}"
            self.detail_label.setText(details)
            return

        if state == GoogleDriveReadinessState.READY:
            self.status_label.setText("Siap digunakan")
            roots = ", ".join(report.drive_roots) or "Google Drive"
            self.detail_label.setText(
                "Filesystem Google Drive sudah tersedia untuk dipilih sebagai folder "
                f"project. Lokasi terdeteksi: {roots}"
            )
            return

        self.status_label.setText("Status belum dapat dipastikan")
        detail = (
            "Script Manager tidak dapat memastikan kesiapan Google Drive saat ini. "
            "Anda dapat membuka Google Drive atau mencoba Periksa Lagi."
        )
        if report.error:
            detail += f"\n\nDetail: {report.error}"
        self.detail_label.setText(detail)

    def _open_google_drive(self) -> None:
        if self.service.launch():
            self.status_label.setText("Google Drive dibuka")
            self.detail_label.setText(
                "Selesaikan login atau tunggu sampai folder Google Drive muncul di "
                "File Explorer, lalu klik Periksa Lagi."
            )
            return

        QMessageBox.warning(
            self,
            "Google Drive",
            "Google Drive tidak dapat dibuka otomatis. Buka Google Drive dari Start "
            "Menu, lalu kembali dan klik Periksa Lagi.",
        )

    def _open_help(self) -> None:
        if QDesktopServices.openUrl(QUrl(GOOGLE_DRIVE_HELP_URL)):
            return
        QMessageBox.information(
            self,
            "Panduan Google Drive",
            f"Buka panduan Google Drive secara manual:\n{GOOGLE_DRIVE_HELP_URL}",
        )


def show_google_drive_readiness(
    parent: QWidget | None = None,
    *,
    service: GoogleDriveReadinessService | None = None,
) -> GoogleDriveReadinessDialog:
    dialog = GoogleDriveReadinessDialog(service=service, parent=parent)
    dialog.exec()
    return dialog
