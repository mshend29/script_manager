from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.source_change_service import SourceChangePreview


class SourceRefreshPreviewDialog(QDialog):
    def __init__(
        self,
        preview: SourceChangePreview,
        *,
        warnings: list[str] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.preview = preview
        self.setWindowTitle("Source Refresh Preview")
        self.resize(1120, 720)
        self.setMinimumSize(860, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel("Source Refresh Preview")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "Preview ini read-only. Database belum diubah. "
            "Apply Refresh akan membuat safety backup terlebih dahulu."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(10)
        metrics.setVerticalSpacing(6)
        values = [
            ("Episodes Changed", preview.changed_episodes),
            ("Source Changed", preview.source_changed),
            ("Dialog Added", preview.dialogues_added),
            ("Dialog Removed", preview.dialogues_removed),
            ("Text Changed", preview.text_changed),
            ("Cast Changed", preview.cast_changed),
            ("Recording Affected", preview.recording_affected),
            ("Tracking Affected", preview.tracking_affected),
        ]
        for index, (label, value) in enumerate(values):
            box = QWidget()
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(8, 6, 8, 6)
            box_layout.setSpacing(1)
            value_label = QLabel(str(value))
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value_label.setStyleSheet("font-size: 15pt; font-weight: 700;")
            caption = QLabel(label)
            caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
            caption.setObjectName("MutedLabel")
            box_layout.addWidget(value_label)
            box_layout.addWidget(caption)
            metrics.addWidget(box, index // 4, index % 4)
        root.addLayout(metrics)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["TYPE", "EPS", "ROW", "ENTITY", "BEFORE", "AFTER", "IMPACT"]
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)

        self._populate_table()
        root.addWidget(self.table, 1)

        if warnings:
            warning_label = QLabel(
                "Parser/Resolver warnings:\n"
                + "\n".join(f"• {item}" for item in warnings[:8])
                + (
                    f"\n… {len(warnings) - 8} warning lainnya"
                    if len(warnings) > 8
                    else ""
                )
            )
            warning_label.setWordWrap(True)
            warning_label.setStyleSheet(
                "background: #FFF4CE; border: 1px solid #E0B400; "
                "border-radius: 5px; padding: 7px;"
            )
            root.addWidget(warning_label)

        if not preview.has_changes:
            no_change = QLabel("✓ Tidak ada perubahan source yang perlu diterapkan.")
            no_change.setStyleSheet("font-weight: 700; color: #176b2c;")
            root.addWidget(no_change)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        apply_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        apply_button.setText("Apply Refresh" if preview.has_changes else "Close")
        apply_button.setProperty("primary", True)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancel")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _populate_table(self) -> None:
        self.table.setRowCount(len(self.preview.items))
        for row_index, change in enumerate(self.preview.items):
            impact_parts = []
            if change.recording_affected:
                impact_parts.append("Recording")
            if change.tracking_affected:
                impact_parts.append("Tracking")
            impact = ", ".join(impact_parts) or "—"

            values = [
                change.change_type.replace("_", " ").title(),
                str(change.episode_number or "-"),
                str(change.source_row) if change.source_row is not None else "-",
                change.entity,
                change.before,
                change.after,
                impact,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.table.setItem(row_index, column, item)

            if change.recording_affected or change.tracking_affected:
                for column in range(self.table.columnCount()):
                    self.table.item(row_index, column).setBackground(
                        QColor("#FFF4CE")
                    )
