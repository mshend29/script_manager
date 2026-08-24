from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from widgets.context_panel import ContextPanel
from widgets.page_shell import PageShell

class ToolsPage(PageShell):
    def __init__(self, parent=None):
        context = ContextPanel("TOOLS")
        context.add_widget(QLabel("Settings"))
        context.add_widget(QLabel("Logs"))
        context.add_stretch()

        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel("Tools")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Utility, log import, maintenance, dan pengaturan aplikasi.")
        subtitle.setObjectName("PageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch(1)

        super().__init__(context, workspace, parent)
