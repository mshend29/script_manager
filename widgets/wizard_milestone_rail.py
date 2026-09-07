from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class WizardMilestoneState(str, Enum):
    PENDING = "pending"
    VALID = "valid"
    WARNING = "warning"
    ERROR = "error"


class WizardMilestoneItem(QFrame):
    _SYMBOLS = {
        WizardMilestoneState.PENDING: "○",
        WizardMilestoneState.VALID: "✓",
        WizardMilestoneState.WARNING: "⚠",
        WizardMilestoneState.ERROR: "✕",
    }

    def __init__(
        self,
        number: int,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("WizardMilestoneItem")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(58)

        self._state = WizardMilestoneState.PENDING
        self._active = False

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 9, 10, 9)
        row.setSpacing(10)

        self.symbol = QLabel("○")
        self.symbol.setObjectName("WizardMilestoneSymbol")
        self.symbol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.symbol.setFixedWidth(24)
        row.addWidget(self.symbol)

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(1)

        self.step_label = QLabel(f"LANGKAH {number}")
        self.step_label.setObjectName("WizardMilestoneStep")
        self.title_label = QLabel(title)
        self.title_label.setObjectName("WizardMilestoneTitle")
        self.title_label.setWordWrap(True)
        text_box.addWidget(self.step_label)
        text_box.addWidget(self.title_label)
        row.addLayout(text_box, 1)

        self.setStyleSheet(
            """
            QFrame#WizardMilestoneItem {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 8px;
            }
            QFrame#WizardMilestoneItem[active="true"] {
                background: #EEF5FF;
                border-color: #9EC5FF;
            }
            QFrame#WizardMilestoneItem[state="valid"] {
                background: #F2FAF5;
            }
            QFrame#WizardMilestoneItem[state="warning"] {
                background: #FFF9E8;
            }
            QFrame#WizardMilestoneItem[state="error"] {
                background: #FFF1F1;
            }
            QLabel#WizardMilestoneStep {
                color: #64748B;
                font-size: 10px;
                font-weight: 600;
            }
            QLabel#WizardMilestoneTitle {
                color: #1F2937;
                font-weight: 600;
            }
            QLabel#WizardMilestoneSymbol {
                color: #334155;
                font-size: 17px;
                font-weight: 700;
            }
            """
        )
        self._refresh()

    @property
    def state(self) -> WizardMilestoneState:
        return self._state

    def set_state(self, state: WizardMilestoneState | str) -> None:
        self._state = WizardMilestoneState(state)
        self._refresh()

    def set_active(self, active: bool) -> None:
        self._active = bool(active)
        self._refresh()

    def _refresh(self) -> None:
        symbol = self._SYMBOLS[self._state]
        if self._active and self._state == WizardMilestoneState.PENDING:
            symbol = "●"
        self.symbol.setText(symbol)
        self.setProperty("active", "true" if self._active else "false")
        self.setProperty("state", self._state.value)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()


class WizardMilestoneRail(QFrame):
    def __init__(
        self,
        titles: tuple[str, ...] | list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("WizardMilestoneRail")
        self.setMinimumWidth(205)
        self.setMaximumWidth(255)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(4)

        self.items: list[WizardMilestoneItem] = []
        for index, title in enumerate(titles):
            item = WizardMilestoneItem(index + 1, title)
            self.items.append(item)
            layout.addWidget(item)
            if index < len(titles) - 1:
                connector = QLabel("│")
                connector.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                connector.setFixedHeight(12)
                connector.setStyleSheet("color: #CBD5E1;")
                layout.addWidget(connector)
        layout.addStretch(1)

        self.setStyleSheet(
            """
            QFrame#WizardMilestoneRail {
                background: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
            }
            """
        )

    def set_active(self, index: int) -> None:
        for item_index, item in enumerate(self.items):
            item.set_active(item_index == index)

    def set_state(
        self,
        index: int,
        state: WizardMilestoneState | str,
    ) -> None:
        if 0 <= index < len(self.items):
            self.items[index].set_state(state)
