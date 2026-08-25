from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from services.tracking_service import (
    DELIVERED,
    IN_PROGRESS,
    NOT_READY,
    NOT_STARTED,
    READY_TO_STEM,
    RECORDED,
    REVISION,
    STATUS_LABELS,
    STEMMED,
)
from widgets.episode_chip import status_palette


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

    STATUS_BUTTON_ORDER = (
        NOT_STARTED,
        IN_PROGRESS,
        RECORDED,
        READY_TO_STEM,
        STEMMED,
        DELIVERED,
        REVISION,
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TrackingDetailGroup")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._loading = False
        self._chip = None
        self._status_buttons: dict[str, QPushButton] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 3)
        root.setSpacing(3)

        body = QHBoxLayout()
        body.setSpacing(10)

        episode_card, self.episode_caption, self.character_value = self._make_card(
            "Episode -",
            "Pilih episode",
        )
        dialogue_card, self.dialogue_caption, self.dialogue_value = self._make_card(
            "Dialog",
            "0/0",
        )
        status_card, self.status_caption, self.status_value = self._make_card(
            "Status",
            "-",
        )
        self.status_card = status_card

        body.addWidget(episode_card, 2)
        body.addWidget(dialogue_card, 2)
        body.addWidget(status_card, 2)

        picker = QFrame()
        picker.setObjectName("TrackingStatusPicker")
        picker.setStyleSheet(
            "QFrame#TrackingStatusPicker {"
            "background: #ffffff; border: 1px solid #c8cdd1; "
            "border-radius: 9px;"
            "}"
        )
        picker_layout = QHBoxLayout(picker)
        picker_layout.setContentsMargins(10, 6, 10, 6)
        picker_layout.setSpacing(10)

        picker_title = QLabel("Ubah\nStatus")
        picker_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        picker_title.setStyleSheet("font-weight: 700; font-size: 11pt;")
        picker_layout.addWidget(picker_title)

        button_grid = QGridLayout()
        button_grid.setContentsMargins(0, 0, 0, 0)
        button_grid.setHorizontalSpacing(8)
        button_grid.setVerticalSpacing(6)

        self.status_button_group = QButtonGroup(self)
        self.status_button_group.setExclusive(True)

        for index, status in enumerate(self.STATUS_BUTTON_ORDER):
            button = QPushButton(STATUS_LABELS[status])
            button.setCheckable(True)
            button.setMinimumWidth(105)
            button.setMinimumHeight(30)
            button.setToolTip(self._status_tooltip(status))
            self._apply_status_button_style(button, status)
            button.clicked.connect(
                lambda checked=False, value=status:
                    self._status_button_clicked(value)
            )
            self.status_button_group.addButton(button)
            self._status_buttons[status] = button
            button_grid.addWidget(button, index // 4, index % 4)

        picker_layout.addLayout(button_grid, 1)
        body.addWidget(picker, 6)
        root.addLayout(body)

        title_label = QLabel("Episode Detail")
        title_label.setObjectName("RibbonGroupTitle")
        title_label.setAlignment(Qt.AlignCenter)
        root.addWidget(title_label)

        self.set_chip(None)

    @staticmethod
    def _make_card(caption: str, value: str):
        frame = QFrame()
        frame.setObjectName("TrackingDetailCard")
        frame.setStyleSheet(
            "QFrame#TrackingDetailCard {"
            "background: #ffffff; border: 1px solid #c8cdd1; "
            "border-radius: 9px;"
            "}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(1)

        caption_label = QLabel(caption)
        caption_label.setAlignment(Qt.AlignCenter)
        caption_label.setStyleSheet("font-weight: 650;")

        value_label = QLabel(value)
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setStyleSheet("font-size: 14pt; font-weight: 700;")

        layout.addWidget(caption_label)
        layout.addWidget(value_label, 1)
        return frame, caption_label, value_label

    @staticmethod
    def _status_tooltip(status: str) -> str:
        if status in {NOT_STARTED, IN_PROGRESS, RECORDED}:
            return (
                "Status recording bersifat otomatis dari checkbox DIALOG. "
                "Status recording yang sedang aktual dapat dipilih untuk kembali ke mode Auto."
            )
        return "Pilih untuk menyimpan status tracking secara otomatis."

    @staticmethod
    def _apply_status_button_style(button: QPushButton, status: str) -> None:
        background, foreground, border = status_palette(status)
        button.setStyleSheet(
            "QPushButton {"
            f"background: {background}; color: {foreground}; "
            f"border: 1px solid {border}; border-radius: 5px; "
            "padding: 4px 9px; font-weight: 650;"
            "}"
            "QPushButton:hover {"
            f"border: 2px solid {border};"
            "}"
            "QPushButton:checked {"
            "border: 3px solid #202124; font-weight: 800;"
            "}"
            "QPushButton:disabled {"
            f"background: {background}; color: {foreground}; "
            "border: 1px dashed #b7bcc1;"
            "}"
        )

    def _set_status_card(self, status: str | None) -> None:
        if not status:
            self.status_card.setStyleSheet(
                "QFrame#TrackingDetailCard {"
                "background: #ffffff; border: 1px solid #c8cdd1; "
                "border-radius: 9px;"
                "}"
            )
            self.status_caption.setStyleSheet("font-weight: 650;")
            self.status_value.setStyleSheet(
                "font-size: 14pt; font-weight: 700;"
            )
            return

        background, foreground, border = status_palette(status)
        self.status_card.setStyleSheet(
            "QFrame#TrackingDetailCard {"
            f"background: {background}; border: 1px solid {border}; "
            "border-radius: 9px;"
            "}"
        )
        self.status_caption.setStyleSheet(
            f"font-weight: 650; color: {foreground};"
        )
        self.status_value.setStyleSheet(
            f"font-size: 14pt; font-weight: 800; color: {foreground};"
        )

    def set_chip(self, chip) -> None:
        self._loading = True
        try:
            self._chip = chip
            if chip is None:
                self.episode_caption.setText("Episode -")
                self.character_value.setText("Pilih episode")
                self.dialogue_value.setText("0/0")
                self.status_value.setText("-")
                self._set_status_card(None)
                self._clear_checked_status()
                for button in self._status_buttons.values():
                    button.setEnabled(False)
                return

            self.episode_caption.setText(f"Episode {chip.episode_number}")
            self.character_value.setText(chip.character_name)
            self.dialogue_value.setText(
                f"{chip.recorded_dialogues}/{chip.total_dialogues}"
            )
            self.status_value.setText(
                STATUS_LABELS.get(chip.display_status, chip.display_status)
            )
            self._set_status_card(chip.display_status)

            recording_complete = chip.recording_status == RECORDED
            for status, button in self._status_buttons.items():
                if status in {NOT_STARTED, IN_PROGRESS, RECORDED}:
                    button.setEnabled(status == chip.recording_status)
                elif status in {READY_TO_STEM, STEMMED, DELIVERED}:
                    button.setEnabled(recording_complete)
                else:
                    button.setEnabled(True)

            self._clear_checked_status()
            current_button = self._status_buttons.get(chip.display_status)
            if current_button is not None:
                current_button.setChecked(True)
        finally:
            self._loading = False

    def _clear_checked_status(self) -> None:
        exclusive = self.status_button_group.exclusive()
        self.status_button_group.setExclusive(False)
        try:
            for button in self._status_buttons.values():
                button.setChecked(False)
        finally:
            self.status_button_group.setExclusive(exclusive)

    def _status_button_clicked(self, status: str) -> None:
        if self._loading or self._chip is None:
            return

        if status in {NOT_STARTED, IN_PROGRESS, RECORDED}:
            if status != self._chip.recording_status:
                return
            requested = NOT_READY
        else:
            requested = status

        self.status_change_requested.emit(str(requested))


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

        if tab_name == "TRACKING":
            root = QVBoxLayout(page)
            root.setContentsMargins(4, 2, 4, 2)
            root.setSpacing(3)

            action_row = QHBoxLayout()
            action_row.setSpacing(0)
            for group_title, actions in self.TAB_GROUPS[tab_name]:
                group = RibbonGroup(group_title, actions)
                group.action_triggered.connect(self.action_triggered)
                action_row.addWidget(group)
            action_row.addStretch(1)
            root.addLayout(action_row)

            self.tracking_detail_group = TrackingDetailGroup()
            self.tracking_detail_group.status_change_requested.connect(
                self.tracking_status_change_requested
            )
            root.addWidget(self.tracking_detail_group)
            return page

        row = QHBoxLayout(page)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(0)
        for group_title, actions in self.TAB_GROUPS[tab_name]:
            group = RibbonGroup(group_title, actions)
            group.action_triggered.connect(self.action_triggered)
            row.addWidget(group)
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
