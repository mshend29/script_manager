from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QTableWidget, QVBoxLayout, QWidget
from widgets.context_panel import ContextPanel
from widgets.page_shell import PageShell

class ScriptPage(PageShell):
    def __init__(self, parent=None):
        context = ContextPanel("FILTER")
        context.add_widget(QLabel("Episode"))
        self.episode_combo = QComboBox()
        self.episode_combo.addItem("All")
        context.add_widget(self.episode_combo)

        context.add_widget(QLabel("Character"))
        self.character_combo = QComboBox()
        self.character_combo.addItem("All")
        context.add_widget(self.character_combo)

        context.add_widget(QLabel("Talent"))
        self.talent_combo = QComboBox()
        self.talent_combo.addItem("All")
        context.add_widget(self.talent_combo)

        context.add_widget(QLabel("Search"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search dialog...")
        context.add_widget(self.search_edit)
        context.add_stretch()

        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel("Script")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["EPS", "IN", "OUT", "DIALOG", "CHARACTER", "TALENT"])
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        super().__init__(context, workspace, parent)
