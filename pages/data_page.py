from PySide6.QtWidgets import QLabel, QTableWidget, QVBoxLayout, QWidget
from widgets.context_panel import ContextPanel
from widgets.page_shell import PageShell

class DataPage(PageShell):
    def __init__(self, parent=None):
        context = ContextPanel("DATA")
        info = QLabel(
            "Validation, unresolved character, talent mapping, "
            "dan diagnostic hasil refresh akan berada di sini."
        )
        info.setWordWrap(True)
        context.add_widget(info)
        context.add_stretch()

        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel("Data & Validation")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["TYPE", "SOURCE", "VALUE", "STATUS"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        super().__init__(context, workspace, parent)
