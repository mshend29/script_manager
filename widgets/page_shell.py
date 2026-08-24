from PySide6.QtWidgets import QHBoxLayout, QWidget

class PageShell(QWidget):
    def __init__(self, context_widget, workspace_widget, parent=None):
        super().__init__(parent)
        workspace_widget.setObjectName("Workspace")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(context_widget)
        layout.addWidget(workspace_widget, 1)
