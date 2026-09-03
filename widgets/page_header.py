from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
)


@dataclass(frozen=True)
class HeaderAction:
    action_id: str
    label: str
    primary: bool = False


@dataclass(frozen=True)
class PageHeaderSpec:
    title: str
    subtitle: str
    actions: tuple[HeaderAction, ...] = ()
    overflow: tuple[HeaderAction, ...] = ()


PAGE_HEADER_SPECS = {
    "PROJECT": PageHeaderSpec(
        title="Project",
        subtitle="Project overview, source sync, and production status",
        actions=(
            HeaderAction("source.sync", "Sync Source", primary=True),
            HeaderAction("project.open", "Open Project"),
            HeaderAction("project.settings", "Project Settings"),
        ),
        overflow=(
            HeaderAction("project.new", "New Project"),
            HeaderAction("project.open_recent", "Open Recent"),
            HeaderAction("project.save", "Save"),
            HeaderAction("project.save_as", "Save As"),
            HeaderAction("project.duplicate", "Duplicate"),
            HeaderAction("project.recover", "Recover"),
            HeaderAction("client.drive", "Open Client Drive"),
            HeaderAction("project.close", "Close Project"),
        ),
    ),
    "SCRIPT": PageHeaderSpec(
        title="Script",
        subtitle="Imported dialogue source and episode overview",
        actions=(
            HeaderAction("script.search", "Search"),
        ),
    ),
    "DIALOG": PageHeaderSpec(
        title="Dialog",
        subtitle="Recording workspace for dialogue review and completion",
        actions=(
            HeaderAction("dialog.open_source", "Open Source File", primary=True),
            HeaderAction("dialog.check_all", "Check All"),
        ),
        overflow=(
            HeaderAction("dialog.uncheck_all", "Uncheck All"),
        ),
    ),
    "TRACKING": PageHeaderSpec(
        title="Tracking",
        subtitle="Compact episode status matrix for production progress",
        actions=(
            HeaderAction("tracking.open_drive", "Open Client Drive"),
        ),
    ),
    "DATA": PageHeaderSpec(
        title="Data",
        subtitle="Characters, talents, cast mapping, and project validation",
        actions=(
            HeaderAction("data.validate", "Validate", primary=True),
            HeaderAction("data.backup", "Backup"),
        ),
        overflow=(
            HeaderAction("data.characters", "Characters"),
            HeaderAction("data.talents", "Talents"),
            HeaderAction("data.cast", "Cast Mapping"),
            HeaderAction("data.rebuild", "Rebuild Index"),
        ),
    ),
    "TOOLS": PageHeaderSpec(
        title="Tools",
        subtitle="Diagnostics, backups, project folders, and maintenance",
        actions=(
            HeaderAction("tools.diagnostics", "Run Diagnostics", primary=True),
            HeaderAction("tools.backup", "Create Backup"),
        ),
        overflow=(
            HeaderAction("tools.audit", "Audit History"),
            HeaderAction("tools.restore_backup", "Restore Backup"),
            HeaderAction("tools.open_project_folder", "Open Project Folder"),
            HeaderAction("tools.open_source_folder", "Open Source Folder"),
            HeaderAction("tools.open_output_folder", "Open Stem / Export"),
            HeaderAction("tools.open_delivery_folder", "Open Setoran"),
            HeaderAction("tools.open_backups", "Open Backups"),
            HeaderAction("tools.open_logs", "Open Logs"),
            HeaderAction("tools.open_main_drive", "Open Main Drive"),
            HeaderAction("tools.open_material_drive", "Open Material Drive"),
            HeaderAction("tools.open_delivery_drive", "Open Delivery Drive"),
        ),
    ),
    "HELP": PageHeaderSpec(
        title="Help",
        subtitle="Guides, shortcuts, updates, and support",
        actions=(
            HeaderAction("help.user_guide", "User Guide", primary=True),
            HeaderAction("help.check_updates", "Check for Updates"),
        ),
        overflow=(
            HeaderAction("help.getting_started", "Getting Started"),
            HeaderAction("help.keyboard_shortcuts", "Keyboard Shortcuts"),
            HeaderAction("help.report_problem", "Report a Problem"),
            HeaderAction("help.about", "About Script Manager"),
        ),
    ),
}


class PageHeader(QFrame):
    action_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PageHeader")
        self.setFixedHeight(78)

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 10, 16, 10)
        root.setSpacing(10)

        title_area = QVBoxLayout()
        title_area.setContentsMargins(0, 0, 0, 0)
        title_area.setSpacing(1)

        self.title_label = QLabel("Project")
        self.title_label.setObjectName("HeaderTitle")
        title_area.addWidget(self.title_label)

        self.subtitle_label = QLabel("")
        self.subtitle_label.setObjectName("HeaderSubtitle")
        title_area.addWidget(self.subtitle_label)

        root.addLayout(title_area, 1)

        self.actions_layout = QHBoxLayout()
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(8)
        root.addLayout(self.actions_layout)

        self.overflow_button = QToolButton()
        self.overflow_button.setText("•••")
        self.overflow_button.setProperty("headerOverflow", True)
        self.overflow_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.overflow_button.setFixedWidth(42)
        self.actions_layout.addWidget(self.overflow_button)

    def set_page(self, page_name: str) -> None:
        spec = PAGE_HEADER_SPECS.get(page_name)
        if spec is None:
            return

        self.title_label.setText(spec.title)
        self.subtitle_label.setText(spec.subtitle)

        while self.actions_layout.count() > 1:
            item = self.actions_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for action in spec.actions:
            button = QPushButton(action.label)
            if action.primary:
                button.setProperty("headerPrimary", True)
            else:
                button.setProperty("headerSecondary", True)
            button.clicked.connect(
                lambda checked=False, action_id=action.action_id:
                    self.action_requested.emit(action_id)
            )
            self.actions_layout.insertWidget(
                self.actions_layout.count() - 1,
                button,
            )

        menu = QMenu(self.overflow_button)
        for action in spec.overflow:
            menu_action = menu.addAction(action.label)
            menu_action.triggered.connect(
                lambda checked=False, action_id=action.action_id:
                    self.action_requested.emit(action_id)
            )
        self.overflow_button.setMenu(menu)
        self.overflow_button.setVisible(bool(spec.overflow))
