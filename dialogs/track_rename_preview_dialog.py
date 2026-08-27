from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
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
    assign_manual_expected,
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
        self.resize(1040, 640)
        self.setMinimumSize(800, 500)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(9)

        title = QLabel(f"Rename Preview — {scope}")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "Semua WAV yang dapat dikaitkan dengan scope episode/talent ditampilkan. "
            "File Unmatched atau Ambiguous dapat dipasangkan manual melalui kolom "
            "Expected. Tidak ada file yang akan ditimpa."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        self.summary = QLabel()
        self.summary.setStyleSheet("font-weight: 700;")
        root.addWidget(self.summary)

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

        root.addWidget(self.table, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.rename_button = buttons.button(
            QDialogButtonBox.StandardButton.Ok
        )
        self.rename_button.setProperty("primary", True)

        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel.setText("Cancel")

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._populate()
        self._refresh_summary()

    def _populate(self) -> None:
        self.table.setRowCount(len(self.plan.items))

        for row_index, item in enumerate(self.plan.items):
            episode = QTableWidgetItem(
                str(item.episode_number)
                if item.episode_number is not None
                else "—"
            )
            character = QTableWidgetItem(item.character_name or "—")
            current = QTableWidgetItem(
                Path(item.source_path).name if item.source_path else "—"
            )
            status = QTableWidgetItem()

            for cell in (episode, character, current, status):
                cell.setToolTip(item.detail or cell.text())

            self.table.setItem(row_index, 0, episode)
            self.table.setItem(row_index, 1, character)
            self.table.setItem(row_index, 2, current)
            self.table.setItem(row_index, 4, status)

            if item.status in {RENAME_UNMATCHED, RENAME_AMBIGUOUS} and item.choices:
                combo = QComboBox()
                combo.addItem("Choose expected…", None)
                for choice in item.choices:
                    combo.addItem(
                        (
                            f"EP{choice.episode_number} — "
                            f"{choice.character_name} — "
                            f"{choice.expected_filename}"
                        ),
                        choice.expected_filename,
                    )
                combo.currentIndexChanged.connect(
                    lambda index, plan_row=row_index:
                    self._manual_choice_changed(plan_row, index)
                )
                self.table.setCellWidget(row_index, 3, combo)
            else:
                expected = QTableWidgetItem(
                    Path(item.target_path).name if item.target_path else "—"
                )
                expected.setToolTip(item.detail or expected.text())
                self.table.setItem(row_index, 3, expected)

            self._refresh_row(row_index)

    def _manual_choice_changed(
        self,
        row_index: int,
        combo_index: int,
    ) -> None:
        combo = self.table.cellWidget(row_index, 3)
        if not isinstance(combo, QComboBox):
            return

        expected_filename = combo.itemData(combo_index)
        if not expected_filename:
            return

        item = self.plan.items[row_index]
        assign_manual_expected(item, str(expected_filename))

        # A manual choice must not silently target a filename already chosen by
        # another source in the same plan.
        target_key = str(Path(item.target_path)).casefold()
        duplicate = any(
            other is not item
            and other.status == RENAME_MATCHED
            and other.target_path
            and str(Path(other.target_path)).casefold() == target_key
            for other in self.plan.items
        )
        if duplicate:
            item.status = RENAME_AMBIGUOUS
            item.detail = (
                "Expected filename ini juga dipakai file lain pada preview. "
                "Pilih target lain."
            )

        self._refresh_row(row_index)
        self._refresh_summary()

    def _refresh_row(self, row_index: int) -> None:
        item = self.plan.items[row_index]

        self.table.item(row_index, 0).setText(
            str(item.episode_number)
            if item.episode_number is not None
            else "—"
        )
        self.table.item(row_index, 1).setText(
            item.character_name or "—"
        )

        status = self.table.item(row_index, 4)
        text = _STATUS_LABELS.get(item.status, item.status)
        if item.status in {
            RENAME_AMBIGUOUS,
            RENAME_COLLISION,
            RENAME_UNMATCHED,
        }:
            text = "⚠ " + text
        elif item.status == RENAME_MATCHED:
            text = "✓ Ready to Rename"
        elif item.status == RENAME_ALREADY_EXPECTED:
            text = "✓ Already Expected"

        status.setText(text)
        status.setToolTip(item.detail)

        expected_item = self.table.item(row_index, 3)
        if expected_item is not None:
            expected_item.setText(
                Path(item.target_path).name if item.target_path else "—"
            )
            expected_item.setToolTip(item.detail)

    def _refresh_summary(self) -> None:
        self.summary.setText(
            f"Ready: {self.plan.matched}   •   "
            f"Already OK: {self.plan.already_expected}   •   "
            f"Ambiguous: {self.plan.ambiguous}   •   "
            f"Collision: {self.plan.collisions}   •   "
            f"Unmatched: {self.plan.unmatched}"
        )
        count = self.plan.matched
        self.rename_button.setText(
            f"Rename {count} File" + ("s" if count != 1 else "")
        )
        self.rename_button.setEnabled(count > 0)
