from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMenu, QPushButton

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

        self.setText(str(chip.episode_number))
        self.setToolTip(
            f"{chip.character_name} • Episode {chip.episode_number}\n"
            f"Status: {chip.status_label}\n"
            "Klik untuk menampilkan detail dan menu aksi."
        )
        self.setFixedSize(46, 34)

        self._action_menu = QMenu(self)
        go_to_dialog = self._action_menu.addAction("Go to Dialog")
        go_to_dialog.triggered.connect(self._go_to_dialog)

        self.clicked.connect(self._request_detail)
        self._apply_status_style()

    def _request_detail(self) -> None:
        self.detail_requested.emit(self.chip)
        self._action_menu.popup(
            self.mapToGlobal(self.rect().bottomLeft())
        )

    def _go_to_dialog(self) -> None:
        window = self.window()
        ribbon = getattr(window, "ribbon", None)
        pages = getattr(window, "pages", None)
        if ribbon is None or not isinstance(pages, dict):
            return

        dialog_page = pages.get("DIALOG")
        if dialog_page is None or not hasattr(dialog_page, "reload"):
            return

        # Selecting the ribbon tab first lets MainWindow bind the active
        # project database to DIALOG. Then reuse the existing chained filter
        # loader so Talent -> Tokoh -> Episode opens exactly this Tracking chip.
        ribbon.select_tab("DIALOG")
        dialog_page.reload(
            preferred_talent_id=self.chip.talent_id,
            preferred_character_id=self.chip.character_id,
            preferred_episode=self.chip.episode_number,
        )

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
            "padding: 3px 6px;"
            "font-weight: 700;"
            "text-align: center;"
            "}"
            "QPushButton:hover {"
            f"border: 2px solid {border};"
            "}"
        )
