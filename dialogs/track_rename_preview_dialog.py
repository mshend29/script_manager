from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.track_rename_service import (
    RENAME_ALREADY_EXPECTED,
    RENAME_AMBIGUOUS,
    RENAME_COLLISION,
    RENAME_MATCHED,
    RENAME_UNMATCHED,
    TrackRenamePlan,
)


_STATUS_LABELS = {
    RENAME_MATCHED: "Ready to Rename",
    RENAME_ALREADY_EXPECTED: "Already Expected",
    RENAME_AMBIGUOUS: "Ambiguous",
    RENAME_COLLISION: "Collision",
    RENAME_UNMATCHED: "Unmatched",
}


class TrackRenamePreviewDialog(QDialog):
    def __init__(
        self,
        plan: TrackRenamePlan,
        *,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.plan = plan

        scope = (
            f"Episode {plan.episode_number}"
            if plan.episode_number is not None
            else plan.talent_name or "Selected Talent"
        )
        self.setWindowTitle(f"Rename Preview — {scope}")
        self.resize(980, 620)
        self.setMinimumSize(760, 480)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(9)

        title = QLabel(f"Rename Preview — {scope}")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "Hanya file Stem / Export yang diubah. Tidak ada file yang akan "
            "ditimpa. Ambiguous, Collision, dan Unmatched tidak ikut direname."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        summary = QLabel(
            f"Ready: {plan.matched}   •   "
            f"Already OK: {plan.already_expected}   •   "
            f"Ambiguous: {plan.ambiguous}   •   "
            f"Collision: {plan.collisions}   •   "
            f"Unmatched: {plan.unmatched}"
        )
        summary.setStyleSheet("font-weight: 700;")
        root.addWidget(summary)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["EPS", "CHARACTER", "CURRENT", "EXPECTED", "STATUS"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )

        self._populate()
        root.addWidget(self.table, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        rename_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        rename_button.setText(
            f"Rename {plan.matched} File"
            + ("s" if plan.matched != 1 else "")
        )
        rename_button.setProperty("primary", True)
        rename_button.setEnabled(plan.matched > 0)

        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel.setText("Cancel")

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _populate(self) -> None:
        self.table.setRowCount(len(self.plan.items))

        for row_index, item in enumerate(self.plan.items):
            values = [
                (
                    str(item.episode_number)
                    if item.episode_number is not None
                    else "—"
                ),
                item.character_name or "—",
                Path(item.source_path).name if item.source_path else "—",
                Path(item.target_path).name if item.target_path else "—",
                _STATUS_LABELS.get(item.status, item.status),
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setToolTip(item.detail or value)
                self.table.setItem(row_index, column, cell)

            if item.status in {
                RENAME_AMBIGUOUS,
                RENAME_COLLISION,
                RENAME_UNMATCHED,
            }:
                self.table.item(row_index, 4).setText(
                    "⚠ " + self.table.item(row_index, 4).text()
                )
            elif item.status == RENAME_MATCHED:
                self.table.item(row_index, 4).setText("✓ Ready to Rename")
            elif item.status == RENAME_ALREADY_EXPECTED:
                self.table.item(row_index, 4).setText("✓ Already Expected")
