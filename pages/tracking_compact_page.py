from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from pages.tracking_page import STATUS_ORDER, TrackingPage


class CompactTrackingPage(TrackingPage):
    """Tracking page with a compact two-column status legend."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._compact_status_legend()

    def _compact_status_legend(self) -> None:
        shell_layout = self.layout()
        if shell_layout is None or shell_layout.count() < 1:
            return
        context = shell_layout.itemAt(0).widget()
        root = getattr(context, "layout_root", None)
        if root is None:
            return

        status_index = -1
        episode_index = -1
        old_status_labels: list[QLabel] = []

        for index in range(root.count()):
            item = root.itemAt(index)
            widget = item.widget()
            if isinstance(widget, QLabel) and widget.objectName() == "SectionTitle":
                if widget.text() == "STATUS":
                    status_index = index
                elif widget.text() == "EPISODE" and status_index >= 0:
                    episode_index = index
                    break

        if status_index < 0:
            return

        stop = episode_index if episode_index >= 0 else root.count()
        for index in range(status_index + 1, stop):
            widget = root.itemAt(index).widget()
            if isinstance(widget, QLabel) and widget.objectName() != "SectionTitle":
                old_status_labels.append(widget)

        for label in old_status_labels:
            label.hide()

        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        for index, status in enumerate(STATUS_ORDER):
            label = self._status_legend_label(status)
            label.setMinimumWidth(0)
            grid.addWidget(label, index // 2, index % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        root.insertWidget(status_index + 1, holder)
