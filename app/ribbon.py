from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from services.tracking_service import (
    DELIVERED,
    NOT_READY,
    READY_TO_STEM,
    RECORDED,
    REVISION,
    STATUS_LABELS,
    STEMMED,
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


class TrackingDetailGroup(QFrame):
    status_change_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RibbonGroup")
        self._loading = False
        self._chip = None

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 5, 10, 4)
        root.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.identity_label = QLabel("Klik nomor episode untuk melihat detail")
        self.identity_label.setStyleSheet("font-weight: 600;")
        self.progress_label = QLabel("")
        top.addWidget(self.identity_label)
        top.addWidget(self.progress_label)
        top.addStretch(1)
        root.addLayout(top)

        controls = QHBoxLayout()
        controls.setSpacing(7)
        self.current_status_label = QLabel("Status: -")
        controls.addWidget(self.current_status_label)
        controls.addWidget(QLabel("Ubah status:"))

        self.status_combo = QComboBox()
        self.status_combo.setMinimumWidth(170)
        self.status_combo.addItem("Auto (Recording Status)", NOT_READY)
        self.status_combo.addItem("Ready to Stem", READY_TO_STEM)
        self.status_combo.addItem("Stemmed", STEMMED)
        self.status_combo.addItem("Delivered", DELIVERED)
        self.status_combo.addItem("Revision", REVISION)
        self.status_combo.setEnabled(False)
        controls.addWidget(self.status_combo)
        controls.addStretch(1)
        root.addLayout(controls)

        title_label = QLabel("Episode Detail")
        title_label.setObjectName("RibbonGroupTitle")
        title_label.setAlignment(Qt.AlignCenter)
        root.addWidget(title_label)

        self.status_combo.currentIndexChanged.connect(
            self._status_changed
        )

    def set_chip(self, chip) -> None:
        self._loading = True
        try:
            self._chip = chip
            if chip is None:
                self.identity_label.setText(
                    "Klik nomor episode untuk melihat detail"
                )
                self.progress_label.clear()
                self.current_status_label.setText("Status: -")
                self.status_combo.setCurrentIndex(0)
                self.status_combo.setEnabled(False)
                self._set_downstream_options_enabled(False)
                return

            self.identity_label.setText(
                f"Episode {chip.episode_number} • "
                f"{chip.character_name} • {chip.talent_name}"
            )
            self.progress_label.setText(
                f"Dialog {chip.recorded_dialogues}/{chip.total_dialogues}"
            )
            self.current_status_label.setText(
                f"Status: {STATUS_LABELS.get(chip.display_status, chip.display_status)}"
            )

            recording_complete = chip.recording_status == RECORDED
            self._set_downstream_options_enabled(recording_complete)
            self.status_combo.setEnabled(True)

            downstream = chip.downstream_status
            if downstream not in {
                READY_TO_STEM,
                STEMMED,
                DELIVERED,
                REVISION,
            }:
                downstream = NOT_READY

            index = self.status_combo.findData(downstream)
            self.status_combo.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self._loading = False

    def _set_downstream_options_enabled(self, recording_complete: bool) -> None:
        model = self.status_combo.model()
        for status in (READY_TO_STEM, STEMMED, DELIVERED):
            index = self.status_combo.findData(status)
            if index < 0:
                continue
            item = model.item(index)
            if item is not None:
                item.setEnabled(recording_complete)

        revision_index = self.status_combo.findData(REVISION)
        if revision_index >= 0:
            item = model.item(revision_index)
            if item is not None:
                item.setEnabled(True)

        auto_index = self.status_combo.findData(NOT_READY)
        if auto_index >= 0:
            item = model.item(auto_index)
            if item is not None:
                item.setEnabled(True)

    def _status_changed(self) -> None:
        if self._loading or self._chip is None:
            return
        status = self.status_combo.currentData()
        if status:
            self.status_change_requested.emit(str(status))


class Ribbon(QWidget):
    tab_changed = Signal(str)
    action_triggered = Signal(str)
    tracking_status_change_requested = Signal(str)

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
            ("View", [
                ("script.refresh", "Refresh View"),
                ("script.search", "Search"),
            ]),
        ],
        "DIALOG": [
            ("View", [("dialog.refresh", "Refresh View")]),
            ("Recording", [
                ("dialog.check_all", "Check All"),
                ("dialog.uncheck_all", "Uncheck All"),
            ]),
            ("Source", [("dialog.open_source", "Open Source File")]),
        ],
        "TRACKING": [
            ("View", [("tracking.refresh", "Refresh View")]),
            ("Delivery", [("tracking.open_drive", "Open Client Drive")]),
        ],
        "DATA": [
            ("Source", [
                ("data.refresh", "Refresh Data"),
                ("data.rebuild", "Rebuild Index"),
            ]),
            ("Mapping", [
                ("data.characters", "Characters"),
                ("data.talents", "Talents"),
                ("data.cast", "Cast Mapping"),
            ]),
            ("Database", [
                ("data.validate", "Validate"),
                ("data.backup", "Backup"),
            ]),
        ],
        # TOOLS remains as a page for future utilities, but unsupported
        # actions are intentionally not advertised as clickable commands.
        "TOOLS": [],
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
        self.tracking_detail_group: TrackingDetailGroup | None = None

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

        if tab_name == "TRACKING":
            self.tracking_detail_group = TrackingDetailGroup()
            self.tracking_detail_group.status_change_requested.connect(
                self.tracking_status_change_requested
            )
            row.addWidget(self.tracking_detail_group, 1)

        row.addStretch(1)
        return page

    def set_tracking_detail(self, chip) -> None:
        if self.tracking_detail_group is not None:
            self.tracking_detail_group.set_chip(chip)

    def clear_tracking_detail(self) -> None:
        self.set_tracking_detail(None)

    def select_tab(self, tab_name):
        if tab_name not in self.content_pages:
            return
        index = self.TAB_ORDER.index(tab_name)
        self.content_stack.setCurrentIndex(index)
        self.tab_buttons[tab_name].setChecked(True)
        self.tab_changed.emit(tab_name)
