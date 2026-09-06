from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from services.audio_setup_validation import AudioSetupValidation


class AudioSetupPanel(QGroupBox):
    create_stem_requested = Signal()
    create_delivery_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("Validasi Folder Audio", parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self.summary = QLabel(
            "Folder Stem dan Setoran harus tersedia dan dapat ditulis."
        )
        self.summary.setObjectName("PageSubtitle")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        grid = QGridLayout()
        grid.setColumnStretch(0, 1)

        self.stem_status = QLabel("Folder Stem belum divalidasi.")
        self.stem_status.setWordWrap(True)
        grid.addWidget(self.stem_status, 0, 0)

        self.create_stem_button = QPushButton("Buat Folder Stem")
        self.create_stem_button.setProperty("secondary", True)
        self.create_stem_button.clicked.connect(self.create_stem_requested)
        self.create_stem_button.hide()
        grid.addWidget(self.create_stem_button, 0, 1)

        self.delivery_status = QLabel("Folder Setoran belum divalidasi.")
        self.delivery_status.setWordWrap(True)
        grid.addWidget(self.delivery_status, 1, 0)

        self.create_delivery_button = QPushButton("Buat Folder Setoran")
        self.create_delivery_button.setProperty("secondary", True)
        self.create_delivery_button.clicked.connect(
            self.create_delivery_requested
        )
        self.create_delivery_button.hide()
        grid.addWidget(self.create_delivery_button, 1, 1)

        root.addLayout(grid)

    def set_validation(self, result: AudioSetupValidation) -> None:
        stem_issue = next(
            (
                issue
                for issue in result.issues
                if issue.field == "stem_output_folder"
            ),
            None,
        )
        delivery_issue = next(
            (
                issue
                for issue in result.issues
                if issue.field == "delivery_folder"
            ),
            None,
        )

        if stem_issue is None:
            self.stem_status.setText("✓ Folder Stem siap digunakan.")
        else:
            self.stem_status.setText(f"✕ {stem_issue.message}")

        if delivery_issue is None:
            self.delivery_status.setText("✓ Folder Setoran siap digunakan.")
        else:
            self.delivery_status.setText(f"✕ {delivery_issue.message}")

        self.create_stem_button.setVisible(
            result.stem_folder.can_create
        )
        self.create_delivery_button.setVisible(
            result.delivery_folder.can_create
        )

        non_folder_issues = [
            issue
            for issue in result.issues
            if issue.field
            not in {"stem_output_folder", "delivery_folder"}
        ]
        if result.is_valid:
            self.summary.setText(
                "✓ Folder audio dan konfigurasi WAV siap digunakan."
            )
        elif non_folder_issues:
            self.summary.setText(f"✕ {non_folder_issues[0].message}")
        else:
            self.summary.setText(
                "Lengkapi atau perbaiki folder audio sebelum melanjutkan."
            )
