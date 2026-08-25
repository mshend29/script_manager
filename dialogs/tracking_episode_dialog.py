from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from services.tracking_service import (
    DELIVERED,
    NOT_READY,
    READY_TO_STEM,
    RECORDED,
    REVISION,
    STEMMED,
    TrackingChip,
)


class TrackingEpisodeDialog(QDialog):
    def __init__(self, chip: TrackingChip, parent=None):
        super().__init__(parent)
        self.chip = chip
        self.setWindowTitle(f"Tracking Episode {chip.episode_number}")
        self.setMinimumWidth(380)

        root = QVBoxLayout(self)
        form = QFormLayout()

        form.addRow("Episode", QLabel(str(chip.episode_number)))
        form.addRow("Tokoh", QLabel(chip.character_name))
        form.addRow("Talent", QLabel(chip.talent_name))
        form.addRow("Status saat ini", QLabel(chip.status_label))
        form.addRow(
            "Dialog recorded",
            QLabel(f"{chip.recorded_dialogues} / {chip.total_dialogues}"),
        )

        self.status_combo = QComboBox()
        self.status_combo.addItem("Ikuti Recording Status", NOT_READY)
        self.status_combo.addItem("Ready to Stem", READY_TO_STEM)
        self.status_combo.addItem("Stemmed", STEMMED)
        self.status_combo.addItem("Delivered", DELIVERED)
        self.status_combo.addItem("Revision", REVISION)

        current_status = chip.downstream_status
        index = self.status_combo.findData(current_status)
        if index < 0:
            index = 0
        self.status_combo.setCurrentIndex(index)

        recording_complete = chip.recording_status == RECORDED
        for row in range(self.status_combo.count()):
            status = self.status_combo.itemData(row)
            if status in {READY_TO_STEM, STEMMED, DELIVERED}:
                item = self.status_combo.model().item(row)
                if item is not None:
                    item.setEnabled(recording_complete)

        form.addRow("Ubah status", self.status_combo)
        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @property
    def selected_status(self) -> str:
        return str(self.status_combo.currentData() or NOT_READY)
