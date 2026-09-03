from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
)

from pages.tracking_compact_page import (
    CompactTrackingPage,
    WORKSPACE_OUTPUT_HEALTH,
    WORKSPACE_TRACK_FILES,
    WORKSPACE_TRACKING,
)


class DeliveryPage(CompactTrackingPage):
    """Dedicated output workspace for Track Files and Output Health."""

    def _build_tracking_workspaces(self) -> None:
        shell_layout = self.layout()
        context = (
            shell_layout.itemAt(0).widget()
            if shell_layout and shell_layout.count() > 1
            else None
        )
        workspace = (
            shell_layout.itemAt(1).widget()
            if shell_layout and shell_layout.count() > 1
            else None
        )
        root = workspace.layout() if workspace is not None else None
        if root is None:
            return

        if context is not None:
            context.hide()

        self.drive_button.hide()
        self.title_label.hide()
        root.removeWidget(self.scroll)

        filter_bar = QFrame()
        filter_bar.setObjectName("TrackingFilterBar")
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(12, 9, 12, 9)
        filter_layout.setSpacing(8)

        talent_label = QLabel("Talent")
        talent_label.setObjectName("TrackingFilterLabel")
        filter_layout.addWidget(talent_label)
        self.talent_combo.setMinimumWidth(180)
        filter_layout.addWidget(self.talent_combo)

        episode_label = QLabel("Episode")
        episode_label.setObjectName("TrackingFilterLabel")
        filter_layout.addWidget(episode_label)
        self.episode_combo.setMinimumWidth(132)
        filter_layout.addWidget(self.episode_combo)

        self.prev_episode_button.setProperty("trackingNav", True)
        self.next_episode_button.setProperty("trackingNav", True)
        filter_layout.addWidget(self.prev_episode_button)
        filter_layout.addWidget(self.next_episode_button)

        filter_layout.addSpacing(8)
        filter_layout.addWidget(self.summary_label, 1)

        navigation = QFrame()
        navigation.setObjectName("TrackingWorkspaceTabs")
        navigation_layout = QHBoxLayout(navigation)
        navigation_layout.setContentsMargins(4, 3, 4, 3)
        navigation_layout.setSpacing(4)

        self.workspace_buttons: dict[str, QPushButton] = {}
        for key, label in (
            (WORKSPACE_TRACK_FILES, "Track Files"),
            (WORKSPACE_OUTPUT_HEALTH, "Output Health"),
        ):
            button = QPushButton(label)
            button.setProperty("secondary", True)
            button.setProperty("trackingWorkspaceTab", True)
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, workspace_key=key:
                    self.show_workspace(workspace_key)
            )
            navigation_layout.addWidget(button)
            self.workspace_buttons[key] = button
        navigation_layout.addStretch(1)

        self.delivery_workspace_stack = QStackedWidget()
        self.delivery_workspace_stack.setObjectName(
            "DeliveryWorkspaceStack"
        )
        self.delivery_workspace_stack.addWidget(
            self._build_track_files_workspace()
        )
        self.delivery_workspace_stack.addWidget(
            self._build_output_health_workspace()
        )

        root.insertWidget(0, filter_bar)
        root.insertWidget(1, navigation)
        root.insertWidget(2, self.delivery_workspace_stack, 1)

    def show_workspace(self, key: str) -> None:
        normalized = str(key or "").strip().casefold()
        if normalized == WORKSPACE_TRACKING:
            normalized = WORKSPACE_TRACK_FILES

        mapping = {
            WORKSPACE_TRACK_FILES: 0,
            WORKSPACE_OUTPUT_HEALTH: 1,
        }
        if (
            normalized not in mapping
            or not hasattr(self, "delivery_workspace_stack")
        ):
            return

        self._workspace_key = normalized
        self.delivery_workspace_stack.setCurrentIndex(mapping[normalized])

        for button_key, button in self.workspace_buttons.items():
            button.setChecked(button_key == normalized)

        if normalized == WORKSPACE_TRACK_FILES:
            self._refresh_track_name_suggestions()
            self._refresh_track_files_table()
        else:
            self._refresh_output_health_workspace()
