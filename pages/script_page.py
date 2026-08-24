from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.database import Database
from services.dialogue_service import DialogueService, ScriptRow
from widgets.context_panel import ContextPanel
from widgets.page_shell import PageShell


class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other: QTableWidgetItem) -> bool:
        left = self.data(Qt.ItemDataRole.UserRole)
        right = other.data(Qt.ItemDataRole.UserRole)

        if left is not None and right is not None:
            try:
                return int(left) < int(right)
            except (TypeError, ValueError):
                pass

        return super().__lt__(other)


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

        context.add_widget(QLabel("Character"))
        self.character_combo = QComboBox()
        self.character_combo.addItem("All", None)
        context.add_widget(self.character_combo)

        context.add_widget(QLabel("Talent"))
        self.talent_combo = QComboBox()
        self.talent_combo.addItem("All", None)
        context.add_widget(self.talent_combo)

        context.add_widget(QLabel("Search"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search dialog, character, talent...")
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

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["EPS", "IN", "OUT", "DIALOG", "CHARACTER", "TALENT"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setWordWrap(True)
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
        self.character_combo.currentIndexChanged.connect(self._filter_changed)
        self.talent_combo.currentIndexChanged.connect(self._filter_changed)
        self.search_edit.textChanged.connect(self._search_changed)

    # ------------------------------------------------------------------
    # PROJECT / DATABASE BINDING
    # ------------------------------------------------------------------

    def set_database(self, database: Database | None) -> None:
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
            self._reset_combo(self.character_combo)
            self._reset_combo(self.talent_combo)
        finally:
            self._loading_filters = False

        self.search_edit.clear()
        self.table.setRowCount(0)
        self.result_label.setText("No project open")

    def reload(self) -> None:
        if self._service is None:
            self.clear_data()
            return

        selected_episode = self.episode_combo.currentData()
        selected_character = self.character_combo.currentData()
        selected_talent = self.talent_combo.currentData()

        try:
            options = self._service.get_script_filter_options()
        except Exception as exc:
            self.table.setRowCount(0)
            self.result_label.setText(f"Failed to load Script filters: {exc}")
            return

        self._loading_filters = True
        try:
            self._reset_combo(self.episode_combo)
            for episode in options.episodes:
                self.episode_combo.addItem(f"Episode {episode}", episode)
            self._restore_combo(self.episode_combo, selected_episode)

            self._reset_combo(self.character_combo)
            for option in options.characters:
                self.character_combo.addItem(option.label, option.id)
            self._restore_combo(self.character_combo, selected_character)

            self._reset_combo(self.talent_combo)
            for option in options.talents:
                self.talent_combo.addItem(option.label, option.id)
            self._restore_combo(self.talent_combo, selected_talent)
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
            self.table.setRowCount(0)
            self.result_label.setText("No project open")
            return

        try:
            rows = self._service.get_script_rows(
                episode_number=self.episode_combo.currentData(),
                character_id=self.character_combo.currentData(),
                talent_id=self.talent_combo.currentData(),
                search=self.search_edit.text(),
            )
        except Exception as exc:
            self.table.setRowCount(0)
            self.result_label.setText(f"Failed to load Script data: {exc}")
            return

        self._populate_table(rows)

        unresolved = sum(1 for row in rows if row.has_unresolved_cast)
        result_text = f"{self._format_count(len(rows))} dialogues"
        if unresolved:
            result_text += f" • {self._format_count(unresolved)} unresolved"
        self.result_label.setText(result_text)

    def _populate_table(self, rows: list[ScriptRow]) -> None:
        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)

        try:
            self.table.clearContents()
            self.table.setRowCount(len(rows))

            for row_index, row in enumerate(rows):
                episode_item = NumericTableWidgetItem(str(row.episode_number))
                episode_item.setData(Qt.ItemDataRole.UserRole, row.episode_number)

                in_item = QTableWidgetItem(row.time_in)
                out_item = QTableWidgetItem(row.time_out)
                dialogue_item = QTableWidgetItem(row.dialogue)

                if row.source_file_name:
                    dialogue_item.setToolTip(f"Source: {row.source_file_name}")

                character_text = " / ".join(row.characters) if row.characters else "⚠ Unresolved"
                character_item = QTableWidgetItem(character_text)

                if row.characters:
                    talent_values = [
                        talent if talent else "⚠ Unresolved"
                        for talent in row.talents
                    ]
                    talent_text = " / ".join(talent_values)
                else:
                    talent_text = "⚠ Unresolved"

                talent_item = QTableWidgetItem(talent_text)

                if row.has_unresolved_cast:
                    warning = "Character/talent mapping belum sepenuhnya resolved."
                    character_item.setToolTip(warning)
                    talent_item.setToolTip(warning)

                items = (
                    episode_item,
                    in_item,
                    out_item,
                    dialogue_item,
                    character_item,
                    talent_item,
                )

                for column, item in enumerate(items):
                    item.setData(Qt.ItemDataRole.UserRole + 1, row.dialogue_id)
                    self.table.setItem(row_index, column, item)
        finally:
            self.table.setSortingEnabled(True)
            self.table.setUpdatesEnabled(True)

    @staticmethod
    def _format_count(value: int) -> str:
        return f"{value:,}".replace(",", ".")
