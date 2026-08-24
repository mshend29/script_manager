from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

class ContextPanel(QFrame):
    def __init__(self, title=None, parent=None):
        super().__init__(parent)
        self.setObjectName("ContextPanel")
        self.setMinimumWidth(260)
        self.setMaximumWidth(310)
        self.layout_root = QVBoxLayout(self)
        self.layout_root.setContentsMargins(16, 18, 16, 18)
        self.layout_root.setSpacing(10)
        if title:
            label = QLabel(title)
            label.setObjectName("SectionTitle")
            self.layout_root.addWidget(label)

    def add_section_title(self, text):
        label = QLabel(text)
        label.setObjectName("SectionTitle")
        self.layout_root.addSpacing(6)
        self.layout_root.addWidget(label)
        return label

    def add_widget(self, widget):
        self.layout_root.addWidget(widget)

    def add_stretch(self):
        self.layout_root.addStretch(1)
