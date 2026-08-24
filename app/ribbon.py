from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget
)

class RibbonGroup(QFrame):
    action_triggered = Signal(str)

    def __init__(self, title, actions, parent=None):
        super().__init__(parent)
        self.setObjectName("RibbonGroup")
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 7, 10, 5)
        root.setSpacing(3)

        row = QHBoxLayout()
        row.setSpacing(4)
        for action_id, label in actions:
            button = QPushButton(label)
            button.setProperty("ribbonAction", True)
            button.clicked.connect(
                lambda checked=False, value=action_id:
                    self.action_triggered.emit(value)
            )
            row.addWidget(button)
        row.addStretch(1)
        root.addLayout(row)

        title_label = QLabel(title)
        title_label.setObjectName("RibbonGroupTitle")
        title_label.setAlignment(Qt.AlignCenter)
        root.addWidget(title_label)

from PySide6.QtCore import Qt

class Ribbon(QWidget):
    tab_changed = Signal(str)
    action_triggered = Signal(str)

    TAB_ORDER = ["PROJECT", "SCRIPT", "DIALOG", "TRACKING", "DATA", "TOOLS"]

    TAB_GROUPS = {
        "PROJECT": [
            ("Project", [
                ("project.new", "New Project"),
                ("project.open", "Open Project"),
                ("project.save", "Save"),
                ("project.settings", "Project Settings"),
                ("project.close", "Close"),
            ]),
            ("Source", [
                ("source.import", "Import Source"),
                ("source.refresh", "Refresh Data"),
            ]),
            ("Client", [("client.drive", "Open Client Drive")]),
        ],
        "SCRIPT": [
            ("View", [("script.refresh", "Refresh View"), ("script.search", "Search")]),
            ("Data", [("script.export", "Export")]),
        ],
        "DIALOG": [
            ("View", [("dialog.refresh", "Refresh View"), ("dialog.search", "Search")]),
            ("Recording", [
                ("dialog.check_all", "Check All"),
                ("dialog.uncheck_all", "Uncheck All"),
            ]),
            ("Source", [("dialog.open_source", "Open Source File")]),
        ],
        "TRACKING": [
            ("View", [("tracking.refresh", "Refresh View")]),
            ("Delivery", [
                ("tracking.open_drive", "Open Client Drive"),
                ("tracking.mark_stemmed", "Mark Stemmed"),
            ]),
        ],
        "DATA": [
            ("Source", [("data.refresh", "Refresh Data"), ("data.rebuild", "Rebuild Index")]),
            ("Mapping", [
                ("data.characters", "Characters"),
                ("data.talents", "Talents"),
                ("data.cast", "Cast Mapping"),
            ]),
            ("Database", [("data.validate", "Validate"), ("data.backup", "Backup")]),
        ],
        "TOOLS": [
            ("Utilities", [("tools.settings", "Settings"), ("tools.logs", "Logs")])
        ],
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RibbonRoot")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.tab_bar = QFrame()
        self.tab_bar.setObjectName("RibbonTabBar")
        tabs_layout = QHBoxLayout(self.tab_bar)
        tabs_layout.setContentsMargins(8, 0, 8, 0)
        tabs_layout.setSpacing(0)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.tab_buttons = {}

        for tab_name in self.TAB_ORDER:
            button = QPushButton(tab_name)
            button.setCheckable(True)
            button.setProperty("ribbonTab", True)
            button.clicked.connect(
                lambda checked=False, name=tab_name: self.select_tab(name)
            )
            self.button_group.addButton(button)
            self.tab_buttons[tab_name] = button
            tabs_layout.addWidget(button)

        tabs_layout.addStretch(1)
        root.addWidget(self.tab_bar)

        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("RibbonContent")
        self.content_pages = {}

        for tab_name in self.TAB_ORDER:
            page = self._create_ribbon_page(tab_name)
            self.content_pages[tab_name] = page
            self.content_stack.addWidget(page)

        root.addWidget(self.content_stack)
        self.select_tab("PROJECT")

    def _create_ribbon_page(self, tab_name):
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(0)
        for group_title, actions in self.TAB_GROUPS[tab_name]:
            group = RibbonGroup(group_title, actions)
            group.action_triggered.connect(self.action_triggered)
            row.addWidget(group)
        row.addStretch(1)
        return page

    def select_tab(self, tab_name):
        if tab_name not in self.content_pages:
            return
        index = self.TAB_ORDER.index(tab_name)
        self.content_stack.setCurrentIndex(index)
        self.tab_buttons[tab_name].setChecked(True)
        self.tab_changed.emit(tab_name)
