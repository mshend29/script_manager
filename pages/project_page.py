from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.project_dashboard_service import ProjectDashboardSnapshot
from widgets.context_panel import ContextPanel
from widgets.page_shell import PageShell


class DashboardCard(QFrame):
    def __init__(self, value: str, label: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("DashboardCard")
        self.setMinimumHeight(92)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(2)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("CardValue")

        label_widget = QLabel(label)
        label_widget.setObjectName("CardLabel")
        label_widget.setWordWrap(True)

        layout.addWidget(self.value_label)
        layout.addWidget(label_widget)
        layout.addStretch(1)

    def set_value(self, value: int | str) -> None:
        self.value_label.setText(str(value))


class ProjectPage(PageShell):
    action_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        context = ContextPanel("PROJECT")

        self.project_name = QLabel("No project open")
        self.project_name.setStyleSheet(
            "font-weight: 600; font-size: 12pt;"
        )
        context.add_widget(self.project_name)

        self.project_location = QLabel("Location: -")
        self.project_location.setWordWrap(True)
        context.add_widget(self.project_location)

        self.source_path = QLabel("Source: -")
        self.source_path.setWordWrap(True)
        context.add_widget(self.source_path)

        self.start_date = QLabel("Start date: -")
        context.add_widget(self.start_date)

        self.last_refresh = QLabel("Last refresh: -")
        context.add_widget(self.last_refresh)

        context.add_section_title("QUICK ACTIONS")

        self.new_button = QPushButton("New Project")
        self.new_button.setProperty("primary", True)
        context.add_widget(self.new_button)

        self.open_button = QPushButton("Open Project")
        self.open_button.setProperty("secondary", True)
        context.add_widget(self.open_button)

        self.open_recent_button = QPushButton("Open Recent")
        self.open_recent_button.setProperty("secondary", True)
        self.open_recent_button.clicked.connect(
            lambda: self.action_requested.emit("project.open_recent")
        )
        context.add_widget(self.open_recent_button)

        self.recover_button = QPushButton("Recover Project")
        self.recover_button.setProperty("secondary", True)
        self.recover_button.clicked.connect(
            lambda: self.action_requested.emit("project.recover")
        )
        context.add_widget(self.recover_button)

        context.add_stretch()

        workspace = QWidget()
        root = QVBoxLayout(workspace)
        root.setContentsMargins(28, 22, 28, 24)
        root.setSpacing(13)

        title = QLabel("Project Dashboard")
        title.setObjectName("PageTitle")

        subtitle = QLabel(
            "Ringkasan project dan pekerjaan berikutnya yang membutuhkan perhatian."
        )
        subtitle.setObjectName("PageSubtitle")

        root.addWidget(title)
        root.addWidget(subtitle)

        cards = QGridLayout()
        cards.setHorizontalSpacing(10)
        cards.setVerticalSpacing(10)

        self.episodes_card = DashboardCard("0", "Episodes")
        self.characters_card = DashboardCard("0", "Characters")
        self.talents_card = DashboardCard("0", "Talents")
        self.dialogues_card = DashboardCard("0", "Dialogues")

        cards.addWidget(self.episodes_card, 0, 0)
        cards.addWidget(self.characters_card, 0, 1)
        cards.addWidget(self.talents_card, 0, 2)
        cards.addWidget(self.dialogues_card, 0, 3)
        root.addLayout(cards)

        workflow_title = QLabel("WORKFLOW")
        workflow_title.setObjectName("SectionTitle")
        root.addWidget(workflow_title)

        workflow = QGridLayout()
        workflow.setHorizontalSpacing(10)
        workflow.setVerticalSpacing(10)

        self.review_card = DashboardCard("0", "Needs Review")
        self.recording_card = DashboardCard("0", "Recording Episodes")
        self.stem_card = DashboardCard("0", "Recorded → Stem")
        self.delivery_card = DashboardCard("0", "Stemmed → Delivery")
        self.revision_card = DashboardCard("0", "Revision")
        self.warning_card = DashboardCard("0", "Output Warnings")

        for index, card in enumerate(
            (
                self.review_card,
                self.recording_card,
                self.stem_card,
                self.delivery_card,
                self.revision_card,
                self.warning_card,
            )
        ):
            workflow.addWidget(card, index // 3, index % 3)
        root.addLayout(workflow)

        action_title = QLabel("WHAT NEEDS ATTENTION")
        action_title.setObjectName("SectionTitle")
        root.addWidget(action_title)

        self.action_holder = QWidget()
        self.action_layout = QGridLayout(self.action_holder)
        self.action_layout.setContentsMargins(0, 0, 0, 0)
        self.action_layout.setHorizontalSpacing(8)
        self.action_layout.setVerticalSpacing(8)
        root.addWidget(self.action_holder)

        activity_title = QLabel("RECENT ACTIVITY")
        activity_title.setObjectName("SectionTitle")
        root.addWidget(activity_title)

        self.activity_frame = QFrame()
        self.activity_frame.setObjectName("DashboardCard")
        self.activity_layout = QVBoxLayout(self.activity_frame)
        self.activity_layout.setContentsMargins(14, 10, 14, 10)
        self.activity_layout.setSpacing(4)
        self.activity_empty = QLabel("Belum ada audit activity.")
        self.activity_empty.setObjectName("MutedLabel")
        self.activity_layout.addWidget(self.activity_empty)
        root.addWidget(self.activity_frame)

        self.info = QFrame()
        self.info.setObjectName("DashboardCard")
        info_layout = QVBoxLayout(self.info)
        info_layout.setContentsMargins(16, 12, 16, 12)
        info_layout.setSpacing(3)

        self.info_title = QLabel("No project open")
        self.info_title.setStyleSheet(
            "font-size: 11pt; font-weight: 600;"
        )

        self.info_text = QLabel(
            "Buat project baru atau buka project yang sudah ada."
        )
        self.info_text.setWordWrap(True)

        info_layout.addWidget(self.info_title)
        info_layout.addWidget(self.info_text)

        root.addWidget(self.info)
        root.addStretch(1)

        super().__init__(context, workspace, parent)

    def set_counts(self, counts: dict[str, int]) -> None:
        self.episodes_card.set_value(counts.get("episodes", 0))
        self.characters_card.set_value(counts.get("characters", 0))
        self.talents_card.set_value(counts.get("talents", 0))
        self.dialogues_card.set_value(counts.get("dialogues", 0))

    def set_dashboard(self, snapshot: ProjectDashboardSnapshot) -> None:
        self.review_card.set_value(snapshot.needs_review)
        self.recording_card.set_value(snapshot.recording_episodes)
        self.stem_card.set_value(snapshot.recorded_waiting_stem)
        self.delivery_card.set_value(snapshot.stemmed_waiting_delivery)
        self.revision_card.set_value(snapshot.revisions)
        self.warning_card.set_value(snapshot.file_warnings)

        self._clear_layout(self.action_layout)
        if snapshot.actions:
            for index, action in enumerate(snapshot.actions):
                button = QPushButton(
                    f"{action.count}  {action.label}\n{action.detail}"
                )
                button.setProperty("secondary", True)
                button.setMinimumHeight(52)
                button.setStyleSheet("text-align: left; padding: 7px 10px;")
                button.clicked.connect(
                    lambda checked=False, key=action.key:
                    self.action_requested.emit(key)
                )
                self.action_layout.addWidget(
                    button,
                    index // 2,
                    index % 2,
                )
        else:
            clean = QLabel("✓ Tidak ada action penting yang tertunda.")
            clean.setStyleSheet("font-weight: 700; color: #176b2c;")
            self.action_layout.addWidget(clean, 0, 0, 1, 2)

        self._clear_layout(self.activity_layout)
        if snapshot.recent_activity:
            for entry in snapshot.recent_activity:
                label = QLabel(
                    f"{entry.created_at}   •   {entry.summary}"
                )
                label.setWordWrap(True)
                label.setObjectName("MutedLabel")
                label.setToolTip(
                    f"{entry.event_type} / {entry.action}"
                )
                self.activity_layout.addWidget(label)
        else:
            label = QLabel("Belum ada audit activity.")
            label.setObjectName("MutedLabel")
            self.activity_layout.addWidget(label)

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                ProjectPage._clear_layout(child_layout)

    def reset_view(self) -> None:
        self.project_name.setText("No project open")
        self.project_location.setText("Location: -")
        self.source_path.setText("Source: -")
        self.start_date.setText("Start date: -")
        self.last_refresh.setText("Last refresh: -")

        self.set_counts({})
        self.set_dashboard(ProjectDashboardSnapshot())

        self.info_title.setText("No project open")
        self.info_text.setText(
            "Buat project baru atau buka project yang sudah ada."
        )
