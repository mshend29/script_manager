from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton

from services.tracking_service import (
    DELIVERED,
    IN_PROGRESS,
    NOT_STARTED,
    READY_TO_STEM,
    RECORDED,
    REVISION,
    STEMMED,
    TrackingChip,
)


STATUS_PALETTE = {
    NOT_STARTED: ("#F2F2F2", "#5C5C5C", "#D0D0D0"),
    IN_PROGRESS: ("#FFF3CD", "#6B5700", "#E5C95B"),
    RECORDED: ("#E2F0D9", "#215E21", "#70AD47"),
    READY_TO_STEM: ("#DDEBF7", "#1F4E78", "#5B9BD5"),
    STEMMED: ("#E4DFEC", "#4C3A6D", "#8064A2"),
    DELIVERED: ("#D9EAD3", "#274E13", "#6AA84F"),
    REVISION: ("#FCE4D6", "#9C0006", "#E26B0A"),
}


def status_palette(status: str) -> tuple[str, str, str]:
    return STATUS_PALETTE.get(status, STATUS_PALETTE[NOT_STARTED])


class EpisodeChipButton(QPushButton):
    detail_requested = Signal(object)

    def __init__(self, chip: TrackingChip, parent=None):
        super().__init__(parent)
        self.chip = chip

        self.setText(f"EP {chip.episode_number}")
        self.setToolTip(
            f"{chip.character_name} • Episode {chip.episode_number}\n"
            "Klik untuk melihat detail tracking."
        )
        self.setFixedSize(72, 38)
        self.clicked.connect(self._request_detail)
        self._apply_status_style()

    def _request_detail(self) -> None:
        self.detail_requested.emit(self.chip)

    def _apply_status_style(self) -> None:
        background, foreground, border = status_palette(
            self.chip.display_status
        )

        self.setStyleSheet(
            "QPushButton {"
            f"background: {background};"
            f"color: {foreground};"
            f"border: 1px solid {border};"
            "border-radius: 9px;"
            "padding: 4px 8px;"
            "font-weight: 700;"
            "text-align: center;"
            "}"
            "QPushButton:hover {"
            f"border: 2px solid {border};"
            "}"
        )
