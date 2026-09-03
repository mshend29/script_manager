from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from app.theme import SIDEBAR_WIDTH
from core.version import APP_VERSION


class SidebarNavigation(QFrame):
    page_requested = Signal(str)

    PRIMARY_PAGES = (
        ("PROJECT", "Project"),
        ("SCRIPT", "Script"),
        ("DIALOG", "Dialog"),
        ("TRACKING", "Tracking"),
        ("DATA", "Data"),
    )
    SECONDARY_PAGES = (
        ("TOOLS", "Tools"),
        ("HELP", "Help"),
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("AppSidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 14, 10, 10)
        root.setSpacing(6)

        root.addWidget(self._build_brand())
        root.addSpacing(10)

        self._buttons: dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        for page_name, label in self.PRIMARY_PAGES:
            root.addWidget(self._make_button(page_name, label))

        divider = QFrame()
        divider.setObjectName("SidebarDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        root.addSpacing(8)
        root.addWidget(divider)
        root.addSpacing(4)

        for page_name, label in self.SECONDARY_PAGES:
            root.addWidget(self._make_button(page_name, label))

        root.addStretch(1)

        footer = QLabel(f"Script Manager  ·  v{APP_VERSION}")
        footer.setObjectName("SidebarFooter")
        footer.setWordWrap(True)
        root.addWidget(footer)

    def _build_brand(self) -> QFrame:
        brand = QFrame()
        brand.setObjectName("SidebarBrand")
        layout = QHBoxLayout(brand)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(10)

        mark = QLabel("SM")
        mark.setObjectName("SidebarBrandMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(38, 38)
        layout.addWidget(mark)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(0)

        title = QLabel("Script Manager")
        title.setObjectName("SidebarBrandTitle")
        title.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        text.addWidget(title)

        version = QLabel("Production workspace")
        version.setObjectName("SidebarBrandVersion")
        text.addWidget(version)

        layout.addLayout(text, 1)
        return brand

    def _make_button(self, page_name: str, label: str) -> QPushButton:
        button = QPushButton(label)
        button.setCheckable(True)
        button.setProperty("sidebarNav", True)
        button.clicked.connect(
            lambda checked=False, name=page_name:
                self.page_requested.emit(name)
        )
        self._group.addButton(button)
        self._buttons[page_name] = button
        return button

    def select_page(self, page_name: str, *, emit: bool = False) -> None:
        button = self._buttons.get(page_name)
        if button is None:
            return

        button.setChecked(True)
        if emit:
            self.page_requested.emit(page_name)

    # Compatibility name used by existing MainWindow navigation helpers during
    # the Phase 10 transition away from Ribbon.
    def select_tab(self, page_name: str) -> None:
        self.select_page(page_name, emit=True)
