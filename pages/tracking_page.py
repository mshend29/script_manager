from PySide6.QtWidgets import QComboBox, QFrame, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget
from widgets.context_panel import ContextPanel
from widgets.page_shell import PageShell

class TrackingPage(PageShell):
    def __init__(self, parent=None):
        context = ContextPanel("TRACKING")

        self.drive_button = QPushButton("Open Client Drive")
        self.drive_button.setProperty("primary", True)
        context.add_widget(self.drive_button)

        context.add_section_title("TALENT")
        self.talent_combo = QComboBox()
        self.talent_combo.setPlaceholderText("Pilih talent")
        context.add_widget(self.talent_combo)

        context.add_section_title("STATUS")
        for text in [
            "■ Not Recorded", "■ Recording", "■ Recorded",
            "■ Ready to Stem", "■ Stemmed", "■ Revision",
        ]:
            context.add_widget(QLabel(text))

        context.add_section_title("EPISODE")
        self.episode_combo = QComboBox()
        self.episode_combo.setPlaceholderText("Pilih episode")
        context.add_widget(self.episode_combo)

        context.add_section_title("CHARACTER TO STEM")
        self.character_list = QListWidget()
        self.character_list.setMinimumHeight(150)
        context.add_widget(self.character_list)
        context.add_stretch()

        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(18, 18, 18, 18)

        title = QLabel("Tracking")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Status episode dihitung dari checkbox Dialog, bukan diubah manual dari chip.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        empty = QFrame()
        empty.setObjectName("DashboardCard")
        empty_layout = QVBoxLayout(empty)
        empty_layout.setContentsMargins(18, 18, 18, 18)
        empty_title = QLabel("Belum ada talent dipilih")
        empty_title.setStyleSheet("font-size: 12pt; font-weight: 600;")
        empty_text = QLabel(
            "Nanti area ini menampilkan satu baris per tokoh dan chip episode "
            "seperti [3] [18] [19] [20] berdasarkan status recording."
        )
        empty_text.setWordWrap(True)
        empty_layout.addWidget(empty_title)
        empty_layout.addWidget(empty_text)
        layout.addWidget(empty)
        layout.addStretch(1)

        super().__init__(context, workspace, parent)
