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
    NOT_READY,
    REVISION,
    STATUS_LABELS,
)
from widgets.episode_chip import status_palette


class RibbonGroup(QFrame):
    action_triggered = Signal(str)

    def __init__(self, title, actions, parent=None):
        super().__init__(parent)
        self.setObjectName("RibbonGroup")
        root = QVBoxLayout(self)
        root.setContentsMargins(9, 4, 9, 2)
        root.setSpacing(2)

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
        self.setObjectName("TrackingDetailGroup")
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._chip = None

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 2, 6, 2)
        root.setSpacing(1)

        body = QHBoxLayout()
        body.setSpacing(6)

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

        revision_panel = QFrame()
        revision_panel.setObjectName("TrackingStatusPicker")
        revision_panel.setMinimumWidth(150)
        revision_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        revision_panel.setStyleSheet(
            "QFrame#TrackingStatusPicker {"
            "background: #ffffff; border: 1px solid #c8cdd1; "
            "border-radius: 9px;"
            "}"
        )
        revision_layout = QHBoxLayout(revision_panel)
        revision_layout.setContentsMargins(9, 4, 9, 4)
        revision_layout.setSpacing(8)

        revision_title = QLabel("Revision")
        revision_title.setStyleSheet("font-weight: 700;")
        revision_layout.addWidget(revision_title)

        self.revision_button = QPushButton("Mark Revision")
        self.revision_button.setMinimumHeight(28)
        self.revision_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        background, foreground, border = status_palette(REVISION)
        self.revision_button.setStyleSheet(
            "QPushButton {"
            f"background: {background}; color: {foreground}; "
            f"border: 1px solid {border}; border-radius: 5px; "
            "padding: 3px 10px; font-weight: 700;"
            "}"
            "QPushButton:hover {"
            f"border: 2px solid {border};"
            "}"
        )
        self.revision_button.clicked.connect(self._revision_clicked)
        revision_layout.addWidget(self.revision_button, 1)

        body.addWidget(revision_panel, 4)
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
        frame.setMinimumWidth(92)
        frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        frame.setStyleSheet(
            "QFrame#TrackingDetailCard {"
            "background: #ffffff; border: 1px solid #c8cdd1; "
            "border-radius: 9px;"
            "}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(0)

        caption_label = QLabel(caption)
        caption_label.setAlignment(Qt.AlignCenter)
        caption_label.setMinimumWidth(0)
        caption_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        caption_label.setStyleSheet("font-weight: 650;")

        value_label = QLabel(value)
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setMinimumWidth(0)
        value_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        value_label.setStyleSheet("font-size: 12pt; font-weight: 700;")

        layout.addWidget(caption_label)
        layout.addWidget(value_label, 1)
        return frame, caption_label, value_label

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
                "font-size: 12pt; font-weight: 700;"
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
            f"font-size: 12pt; font-weight: 800; color: {foreground};"
        )

    def set_chip(self, chip) -> None:
        self._chip = chip
        if chip is None:
            self.episode_caption.setText("Episode -")
            self.character_value.setText("Pilih episode")
            self.character_value.setToolTip("")
            self.dialogue_value.setText("0/0")
            self.status_value.setText("-")
            self._set_status_card(None)
            self.revision_button.setText("Mark Revision")
            self.revision_button.setEnabled(False)
            return

        self.episode_caption.setText(f"Episode {chip.episode_number}")
        self.character_value.setText(chip.character_name)
        self.character_value.setToolTip(chip.character_name)
        self.dialogue_value.setText(
            f"{chip.recorded_dialogues}/{chip.total_dialogues}"
        )
        self.status_value.setText(
            STATUS_LABELS.get(chip.display_status, chip.display_status)
        )
        self._set_status_card(chip.display_status)
        self.revision_button.setEnabled(True)
        self.revision_button.setText(
            "Clear Revision"
            if chip.display_status == REVISION
            else "Mark Revision"
        )

    def _revision_clicked(self) -> None:
        if self._chip is None:
            return
        requested = (
            NOT_READY
            if self._chip.display_status == REVISION
            else REVISION
        )
        self.status_change_requested.emit(requested)


class Ribbon(QWidget):
    tab_changed = Signal(str)
    action_triggered = Signal(str)
    tracking_status_change_requested = Signal(str)

    TAB_ORDER = ["PROJECT", "SCRIPT", "DIALOG", "TRACKING", "DATA", "TOOLS", "HELP"]

    TAB_GROUPS = {
        "PROJECT": [
            ("Project", [
                ("project.new", "New Project"),
                ("project.open", "Open Project"),
                ("project.open_recent", "Open Recent"),
                ("project.save", "Save"),
                ("project.save_as", "Save As"),
                ("project.duplicate", "Duplicate"),
                ("project.recover", "Recover"),
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
        "TOOLS": [
            ("Diagnostics", [
                ("tools.diagnostics", "Run Diagnostics"),
                ("tools.audit", "Audit History"),
            ]),
            ("Project", [
                ("tools.open_project_folder", "Open Project Folder"),
            ]),
            ("Database", [
                ("tools.backup", "Create Backup"),
                ("tools.restore_backup", "Restore Backup"),
                ("tools.open_backups", "Open Backups"),
            ]),
            ("Folders", [
                ("tools.open_source_folder", "Source"),
                ("tools.open_output_folder", "Stem / Export"),
                ("tools.open_delivery_folder", "Setoran"),
                ("tools.open_logs", "Logs"),
            ]),
            ("Drive", [
                ("tools.open_main_drive", "Main Drive"),
                ("tools.open_material_drive", "Material Drive"),
                ("tools.open_delivery_drive", "Delivery Drive"),
            ]),
        ],
        "HELP": [
            ("Guide", [
                ("help.getting_started", "Getting Started"),
                ("help.user_guide", "User Guide"),
                ("help.keyboard_shortcuts", "Keyboard Shortcuts"),
            ]),
            ("Application", [
                ("help.check_updates", "Check for Updates"),
                ("help.about", "About Script Manager"),
            ]),
            ("Support", [
                ("help.report_problem", "Report a Problem"),
            ]),
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
        else:
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
