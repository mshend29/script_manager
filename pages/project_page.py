from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from widgets.context_panel import ContextPanel
from widgets.page_shell import PageShell


class DashboardCard(QFrame):
    def __init__(self, value: str, label: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("DashboardCard")
        self.setMinimumHeight(105)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("CardValue")

        label_widget = QLabel(label)
        label_widget.setObjectName("CardLabel")

        layout.addWidget(self.value_label)
        layout.addWidget(label_widget)
        layout.addStretch(1)

    def set_value(self, value: int | str) -> None:
        self.value_label.setText(str(value))


class ProjectPage(PageShell):
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

        context.add_stretch()

        workspace = QWidget()
        root = QVBoxLayout(workspace)
        root.setContentsMargins(28, 26, 28, 26)
        root.setSpacing(18)

        title = QLabel("Project Dashboard")
        title.setObjectName("PageTitle")

        subtitle = QLabel(
            "Ringkasan project, source, database, dan status sinkronisasi."
        )
        subtitle.setObjectName("PageSubtitle")

        root.addWidget(title)
        root.addWidget(subtitle)

        cards = QGridLayout()
        cards.setHorizontalSpacing(14)

        self.episodes_card = DashboardCard("0", "Episodes")
        self.characters_card = DashboardCard("0", "Characters")
        self.talents_card = DashboardCard("0", "Talents")
        self.dialogues_card = DashboardCard("0", "Dialogues")

        cards.addWidget(self.episodes_card, 0, 0)
        cards.addWidget(self.characters_card, 0, 1)
        cards.addWidget(self.talents_card, 0, 2)
        cards.addWidget(self.dialogues_card, 0, 3)

        root.addLayout(cards)

        self.info = QFrame()
        self.info.setObjectName("DashboardCard")
        info_layout = QVBoxLayout(self.info)
        info_layout.setContentsMargins(18, 16, 18, 16)

        self.info_title = QLabel("No project open")
        self.info_title.setStyleSheet(
            "font-size: 12pt; font-weight: 600;"
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

    def reset_view(self) -> None:
        self.project_name.setText("No project open")
        self.project_location.setText("Location: -")
        self.source_path.setText("Source: -")
        self.start_date.setText("Start date: -")
        self.last_refresh.setText("Last refresh: -")

        self.set_counts({})

        self.info_title.setText("No project open")
        self.info_text.setText(
            "Buat project baru atau buka project yang sudah ada."
        )
