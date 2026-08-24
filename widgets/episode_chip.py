from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMenu, QPushButton

from services.tracking_service import (
    DELIVERED,
    IN_PROGRESS,
    NOT_READY,
    NOT_STARTED,
    READY_TO_STEM,
    RECORDED,
    REVISION,
    STEMMED,
    TrackingChip,
)


class EpisodeChipButton(QPushButton):
    status_change_requested = Signal(int, int, int, str)

    def __init__(self, chip: TrackingChip, parent=None):
        super().__init__(parent)
        self.chip = chip

        self.setText(
            f"EP {chip.episode_number}\n"
            f"{chip.status_label}\n"
            f"{chip.progress_text}"
        )
        self.setToolTip(
            f"{chip.character_name} — {chip.talent_name}\n"
            f"Episode {chip.episode_number}\n"
            f"Recording: {chip.progress_text}\n"
            f"Status: {chip.status_label}\n\n"
            "Klik untuk mengubah status downstream."
        )
        self.setMinimumWidth(116)
        self.setMinimumHeight(68)
        self.clicked.connect(self._show_status_menu)
        self._apply_status_style()

    def _show_status_menu(self) -> None:
        menu = QMenu(self)

        reset_action = menu.addAction("Reset to Recording Status")
        menu.addSeparator()
        ready_action = menu.addAction("Ready to Stem")
        stemmed_action = menu.addAction("Stemmed")
        delivered_action = menu.addAction("Delivered")
        menu.addSeparator()
        revision_action = menu.addAction("Revision")

        recording_complete = self.chip.recording_status == RECORDED
        ready_action.setEnabled(recording_complete)
        stemmed_action.setEnabled(recording_complete)
        delivered_action.setEnabled(recording_complete)

        selected = menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

        status = None
        if selected is reset_action:
            status = NOT_READY
        elif selected is ready_action:
            status = READY_TO_STEM
        elif selected is stemmed_action:
            status = STEMMED
        elif selected is delivered_action:
            status = DELIVERED
        elif selected is revision_action:
            status = REVISION

        if status is not None:
            self.status_change_requested.emit(
                self.chip.episode_id,
                self.chip.talent_id,
                self.chip.character_id,
                status,
            )

    def _apply_status_style(self) -> None:
        palette = {
            NOT_STARTED: ("#F2F2F2", "#5C5C5C", "#D0D0D0"),
            IN_PROGRESS: ("#FFF3CD", "#6B5700", "#E5C95B"),
            RECORDED: ("#E2F0D9", "#215E21", "#70AD47"),
            READY_TO_STEM: ("#DDEBF7", "#1F4E78", "#5B9BD5"),
            STEMMED: ("#E4DFEC", "#4C3A6D", "#8064A2"),
            DELIVERED: ("#D9EAD3", "#274E13", "#6AA84F"),
            REVISION: ("#FCE4D6", "#9C0006", "#E26B0A"),
        }

        background, foreground, border = palette.get(
            self.chip.display_status,
            palette[NOT_STARTED],
        )

        self.setStyleSheet(
            "QPushButton {"
            f"background: {background};"
            f"color: {foreground};"
            f"border: 1px solid {border};"
            "border-radius: 6px;"
            "padding: 6px 10px;"
            "font-weight: 600;"
            "text-align: center;"
            "}"
            "QPushButton:hover {"
            f"border: 2px solid {border};"
            "}"
        )
