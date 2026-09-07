from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from core.project_settings import ProjectSettings
from services.folder_links_setup_validation import FolderLinksSetupValidation


class FolderLinksSummaryPanel(QGroupBox):
    def __init__(self, parent=None) -> None:
        super().__init__("Ringkasan Folder Operasional", parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        form = QFormLayout()
        self.source_folder = self._read_only_field()
        self.stem_folder = self._read_only_field()
        self.delivery_folder = self._read_only_field()
        form.addRow("Naskah", self.source_folder)
        form.addRow("Stem", self.stem_folder)
        form.addRow("Setoran", self.delivery_folder)
        root.addLayout(form)

        self.status = QLabel(
            "Folder di atas adalah filesystem path dan diringkas dari milestone sebelumnya."
        )
        self.status.setObjectName("PageSubtitle")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

    @staticmethod
    def _read_only_field() -> QLineEdit:
        field = QLineEdit()
        field.setReadOnly(True)
        field.setPlaceholderText("Belum dikonfigurasi")
        return field

    def set_settings(self, settings: ProjectSettings) -> None:
        self.source_folder.setText(settings.source_folder)
        self.stem_folder.setText(settings.stem_output_folder)
        self.delivery_folder.setText(settings.delivery_folder)

    def set_validation(self, result: FolderLinksSetupValidation) -> None:
        folder_issues = [
            issue
            for issue in result.errors
            if issue.field
            in {"source_folder", "stem_output_folder", "delivery_folder"}
        ]
        link_issues = [
            issue
            for issue in result.errors
            if issue.field
            in {"main_drive_url", "material_drive_url", "delivery_drive_url"}
        ]

        if folder_issues:
            self.status.setText(f"✕ {folder_issues[0].message}")
        elif link_issues:
            self.status.setText(
                "✓ Folder operasional siap. Perbaiki format tautan yang ditandai."
            )
        else:
            self.status.setText(
                "✓ Folder operasional siap. Tautan browser bersifat opsional."
            )
