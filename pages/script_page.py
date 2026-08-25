from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from core.database import Database
from services.dialogue_service import DialogueService, ScriptRow
from widgets.context_panel import ContextPanel
from widgets.page_shell import PageShell


class ScriptTableModel(QAbstractTableModel):
    HEADERS = ("EPS", "IN", "OUT", "DIALOG", "CHARACTER", "TALENT")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[ScriptRow] = []

    def set_rows(self, rows: list[ScriptRow]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None

        row = self._rows[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                return str(row.episode_number)
            if column == 1:
                return row.time_in
            if column == 2:
                return row.time_out
            if column == 3:
                return row.dialogue
            if column == 4:
                return " / ".join(row.characters) if row.characters else "⚠ Unresolved"
            if column == 5:
                if not row.characters:
                    return "⚠ Unresolved"
                return " / ".join(
                    talent if talent else "⚠ Unresolved"
                    for talent in row.talents
                )

        if role == Qt.ItemDataRole.ToolTipRole:
            if column == 3 and row.source_file_name:
                return f"Source: {row.source_file_name}"
            if column in {4, 5} and row.has_unresolved_cast:
                return "Character/talent mapping belum sepenuhnya resolved."

        if role == Qt.ItemDataRole.TextAlignmentRole and column in {0, 1, 2}:
            return int(
                Qt.AlignmentFlag.AlignHCenter
                | Qt.AlignmentFlag.AlignVCenter
            )

        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(self.HEADERS)
        ):
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)


class ScriptTableView(QTableView):
    """QTableView with a small compatibility helper for QA/UI callers."""

    def rowCount(self) -> int:
        model = self.model()
        return model.rowCount() if model is not None else 0


class ScriptPage(PageShell):
    def __init__(self, parent=None):
        self._database: Database | None = None
        self._service: DialogueService | None = None
        self._loading_filters = False

        context = ContextPanel("FILTER")

        context.add_widget(QLabel("Episode"))
        self.episode_combo = QComboBox()
        self.episode_combo.addItem("All", None)
        context.add_widget(self.episode_combo)

        context.add_widget(QLabel("Search"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search script...")
        self.search_edit.setClearButtonEnabled(True)
        context.add_widget(self.search_edit)
        context.add_stretch()

        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel("Script")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self.result_label = QLabel("No project open")
        self.result_label.setObjectName("MutedLabel")
        layout.addWidget(self.result_label)

        self.table = ScriptTableView()
        self.table_model = ScriptTableModel(self.table)
        self.table.setModel(self.table_model)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.setSortingEnabled(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(4, 190)
        self.table.setColumnWidth(5, 190)

        layout.addWidget(self.table, 1)

        super().__init__(context, workspace, parent)

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(250)
        self.search_timer.timeout.connect(self.refresh_rows)

        self.episode_combo.currentIndexChanged.connect(self._filter_changed)
        self.search_edit.textChanged.connect(self._search_changed)

    # ------------------------------------------------------------------
    # PROJECT / DATABASE BINDING
    # ------------------------------------------------------------------

    def set_database(self, database: Database | None) -> None:
        if database is self._database and self._service is not None:
            self.refresh_rows()
            return

        self._database = database
        self._service = DialogueService(database) if database is not None else None

        if self._service is None:
            self.clear_data()
            return

        self.reload()

    def clear_data(self) -> None:
        self._service = None
        self._database = None
        self.search_timer.stop()

        self._loading_filters = True
        try:
            self._reset_combo(self.episode_combo)
            self.search_edit.blockSignals(True)
            self.search_edit.clear()
            self.search_edit.blockSignals(False)
        finally:
            self._loading_filters = False

        self.table_model.set_rows([])
        self.result_label.setText("No project open")

    def reload(self) -> None:
        if self._service is None:
            self.clear_data()
            return

        selected_episode = self.episode_combo.currentData()

        try:
            options = self._service.get_script_filter_options()
        except Exception as exc:
            self.table_model.set_rows([])
            self.result_label.setText(f"Failed to load Script filters: {exc}")
            return

        self._loading_filters = True
        try:
            self._reset_combo(self.episode_combo)
            for episode in options.episodes:
                self.episode_combo.addItem(f"Episode {episode}", episode)
            self._restore_combo(self.episode_combo, selected_episode)
        finally:
            self._loading_filters = False

        self.refresh_rows()

    @staticmethod
    def _reset_combo(combo: QComboBox) -> None:
        combo.blockSignals(True)
        try:
            combo.clear()
            combo.addItem("All", None)
        finally:
            combo.blockSignals(False)

    @staticmethod
    def _restore_combo(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    # ------------------------------------------------------------------
    # FILTERS
    # ------------------------------------------------------------------

    def _filter_changed(self) -> None:
        if self._loading_filters:
            return
        self.refresh_rows()

    def _search_changed(self) -> None:
        if self._loading_filters:
            return
        self.search_timer.start()

    # ------------------------------------------------------------------
    # TABLE
    # ------------------------------------------------------------------

    def refresh_rows(self) -> None:
        if self._service is None:
            self.table_model.set_rows([])
            self.result_label.setText("No project open")
            return

        try:
            rows = self._service.get_script_rows(
                episode_number=self.episode_combo.currentData(),
                search=self.search_edit.text(),
            )
        except Exception as exc:
            self.table_model.set_rows([])
            self.result_label.setText(f"Failed to load Script data: {exc}")
            return

        # DialogueService returns episode/time/source order.  The view does not
        # enable interactive sorting, so EP1 stays before EP2 ... EP110.
        self.table_model.set_rows(rows)

        unresolved = sum(1 for row in rows if row.has_unresolved_cast)
        result_text = f"{self._format_count(len(rows))} dialogues"
        if unresolved:
            result_text += f" • {self._format_count(unresolved)} unresolved"
        self.result_label.setText(result_text)

    @staticmethod
    def _format_count(value: int) -> str:
        return f"{value:,}".replace(",", ".")
