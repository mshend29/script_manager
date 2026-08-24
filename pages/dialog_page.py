from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QLabel, QListWidget, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget
)
from widgets.context_panel import ContextPanel
from widgets.page_shell import PageShell

class DialogPage(PageShell):
    def __init__(self, parent=None):
        context = ContextPanel("DIALOG")

        context.add_widget(QLabel("Tokoh"))
        self.character_combo = QComboBox()
        self.character_combo.setPlaceholderText("Pilih tokoh")
        context.add_widget(self.character_combo)

        context.add_widget(QLabel("Episode"))
        self.episode_combo = QComboBox()
        self.episode_combo.setPlaceholderText("Pilih episode")
        context.add_widget(self.episode_combo)

        self.open_source_button = QPushButton("Open Source File")
        self.open_source_button.setProperty("secondary", True)
        context.add_widget(self.open_source_button)

        context.add_section_title("CAST EPISODE")
        self.cast_list = QListWidget()
        self.cast_list.setMinimumHeight(190)
        context.add_widget(self.cast_list)
        context.add_stretch()

        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(18, 18, 18, 18)

        title = QLabel("Dialog")
        title.setObjectName("PageTitle")
        self.selection_info = QLabel("Pilih tokoh dan episode untuk menampilkan dialog.")
        self.selection_info.setObjectName("PageSubtitle")
        layout.addWidget(title)
        layout.addWidget(self.selection_info)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["✓", "IN", "OUT", "DIALOG"])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 42)
        self.table.setColumnWidth(1, 115)
        self.table.setColumnWidth(2, 115)
        layout.addWidget(self.table, 1)

        super().__init__(context, workspace, parent)

    def add_dialog_row(self, time_in, time_out, dialog, recorded=False):
        row = self.table.rowCount()
        self.table.insertRow(row)
        checkbox_item = QTableWidgetItem()
        checkbox_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
        checkbox_item.setCheckState(Qt.Checked if recorded else Qt.Unchecked)
        self.table.setItem(row, 0, checkbox_item)
        self.table.setItem(row, 1, QTableWidgetItem(time_in))
        self.table.setItem(row, 2, QTableWidgetItem(time_out))
        self.table.setItem(row, 3, QTableWidgetItem(dialog))

    def set_all_checked(self, checked):
        state = Qt.Checked if checked else Qt.Unchecked
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None:
                item.setCheckState(state)
