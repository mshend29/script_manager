from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
)


class WorkspaceNavigation(QFrame):
    """DaVinci Resolve-style bottom workspace switcher."""

    page_requested = Signal(str)

    WORKSPACES = (
        ("PROJECT", "Project"),
        ("SCRIPT", "Script"),
        ("DIALOG", "Dialog"),
        ("TRACKING", "Tracking"),
        ("DATA", "Data"),
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("WorkspaceNavigation")
        self.setFixedHeight(58)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 5, 12, 5)
        root.setSpacing(3)
        root.addStretch(1)

        self._buttons: dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        for page_name, label in self.WORKSPACES:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("workspaceNav", True)
            button.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.Expanding,
            )
            button.setMinimumWidth(92)
            button.clicked.connect(
                lambda checked=False, name=page_name:
                    self.page_requested.emit(name)
            )
            self._group.addButton(button)
            self._buttons[page_name] = button
            root.addWidget(button)

        root.addStretch(1)

    def select_page(self, page_name: str, *, emit: bool = False) -> None:
        normalized = str(page_name or "").strip().upper()
        button = self._buttons.get(normalized)

        if button is None:
            self._group.setExclusive(False)
            try:
                for candidate in self._buttons.values():
                    candidate.setChecked(False)
            finally:
                self._group.setExclusive(True)
            if emit:
                self.page_requested.emit(normalized)
            return

        button.setChecked(True)
        if emit:
            self.page_requested.emit(normalized)

    def select_tab(self, page_name: str) -> None:
        """Compatibility helper for existing navigation call sites."""
        normalized = str(page_name or "").strip().upper()
        self.select_page(normalized, emit=False)
        self.page_requested.emit(normalized)
