from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.theme import COLORS
from core.database import Database
from services.dialogue_service import DialogueService, ScriptRow
from widgets.context_panel import ContextPanel
from widgets.page_shell import PageShell


class ScriptTableModel(QAbstractTableModel):
    HEADERS = ("EPISODE", "IN", "OUT", "DIALOG", "TOKOH", "TALENT")

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
                return self._single_line_dialogue(row.dialogue)
            if column == 4:
                return (
                    " / ".join(row.characters)
                    if row.characters
                    else "⚠ Belum dipetakan"
                )
            if column == 5:
                if not row.characters:
                    return "⚠ Belum dipetakan"
                return " / ".join(
                    talent if talent else "⚠ Belum dipetakan"
                    for talent in row.talents
                )

        if role == Qt.ItemDataRole.ToolTipRole:
            if column == 3:
                tooltip = row.dialogue
                if row.source_file_name:
                    tooltip += f"\n\nSumber: {row.source_file_name}"
                return tooltip
            if column in {4, 5} and row.has_unresolved_cast:
                return "Pemetaan tokoh/talent belum sepenuhnya selesai."

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

    @staticmethod
    def _single_line_dialogue(value: str) -> str:
        """Match Dialog workspace: one visible line even if source contains line breaks."""
        return " ".join(str(value or "").splitlines()).strip()


class ScriptCastTableModel(QAbstractTableModel):
    HEADERS = ("TALENT", "TOKOH")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[tuple[str, str]] = []

    def set_rows(self, rows: list[tuple[str, str]]) -> None:
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
        value = self._rows[index.row()][index.column()]
        if role in {
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.ToolTipRole,
        }:
            return value
        if role == Qt.ItemDataRole.BackgroundRole:
            color_key = "surface" if index.row() % 2 == 0 else "neutral_soft"
            return QColor(COLORS[color_key])
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

        context = ContextPanel("TOKOH & TALENT")
        self.cast_scope_label = QLabel("Belum ada proyek terbuka")
        self.cast_scope_label.setObjectName("MutedLabel")
        self.cast_scope_label.setWordWrap(True)
        context.add_widget(self.cast_scope_label)

        self.cast_table = ScriptTableView()
        self.cast_table.setObjectName("ScriptCastTable")
        self.cast_model = ScriptCastTableModel(self.cast_table)
        self.cast_table.setModel(self.cast_model)
        self.cast_table.setAlternatingRowColors(False)
        self.cast_table.setWordWrap(True)
        self.cast_table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.cast_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.cast_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.cast_table.verticalHeader().setVisible(False)
        self.cast_table.verticalHeader().setDefaultSectionSize(30)
        self.cast_table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.cast_table.setShowGrid(False)
        cast_header = self.cast_table.horizontalHeader()
        cast_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        cast_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        context.layout_root.addWidget(self.cast_table, 1)

        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel("Naskah")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        filter_bar = QFrame()
        filter_bar.setObjectName("ScriptFilterBar")
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(12, 9, 12, 9)
        filter_layout.setSpacing(8)

        self.result_label = QLabel("Belum ada proyek terbuka")
        self.result_label.setObjectName("ScriptSummary")
        self.result_label.setMinimumWidth(170)
        filter_layout.addWidget(self.result_label, 1)

        episode_label = QLabel("Episode")
        episode_label.setObjectName("ScriptFilterLabel")
        filter_layout.addWidget(episode_label)

        self.episode_combo = QComboBox()
        self.episode_combo.setObjectName("ScriptEpisodeFilter")
        self.episode_combo.addItem("Semua Episode", None)
        self.episode_combo.setMinimumWidth(138)
        self.episode_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.episode_combo.setMinimumContentsLength(12)
        filter_layout.addWidget(self.episode_combo)

        self.prev_episode_button = QPushButton("‹ Sebelumnya")
        self.prev_episode_button.setObjectName("ScriptPrevEpisode")
        self.prev_episode_button.setProperty("secondary", True)
        self.next_episode_button = QPushButton("Berikutnya ›")
        self.next_episode_button.setObjectName("ScriptNextEpisode")
        self.next_episode_button.setProperty("secondary", True)
        filter_layout.addWidget(self.prev_episode_button)
        filter_layout.addWidget(self.next_episode_button)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("ScriptSearch")
        self.search_edit.setPlaceholderText("Cari naskah…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMinimumWidth(210)
        filter_layout.addWidget(self.search_edit, 1)

        layout.addWidget(filter_bar)

        self.table = ScriptTableView()
        self.table.setObjectName("ScriptTable")
        self.table_model = ScriptTableModel(self.table)
        self.table.setModel(self.table_model)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.setSortingEnabled(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Fixed
        )

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

        self.episode_combo.currentIndexChanged.connect(self._episode_changed)
        self.prev_episode_button.clicked.connect(
            lambda: self._select_adjacent_episode(-1)
        )
        self.next_episode_button.clicked.connect(
            lambda: self._select_adjacent_episode(1)
        )
        self.search_edit.textChanged.connect(self._search_changed)
        self._update_episode_navigation()

    # ------------------------------------------------------------------
    # PROJECT / DATABASE BINDING
    # ------------------------------------------------------------------

    def set_database(self, database: Database | None) -> None:
        if database is self._database and self._service is not None:
            self.refresh_rows()
            self._refresh_cast_sidebar()
            return

        self._database = database
        self._service = DialogueService(database) if database is not None else None

        if self._service is None:
            self.clear_data()
            return

        self.reload()

    def refresh_from_database(self, database: Database | None) -> None:
        """Reload source-derived episode options and rows while preserving scope."""
        if database is not self._database or self._service is None:
            self.set_database(database)
            return

        if database is None:
            self.clear_data()
            return

        # Full refresh must reload filters so newly added episodes become
        # selectable immediately after source refresh.
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

        self._update_episode_navigation()
        self.table_model.set_rows([])
        self.cast_model.set_rows([])
        self.cast_scope_label.setText("Belum ada proyek terbuka")
        self.result_label.setText("Belum ada proyek terbuka")

    def reload(self) -> None:
        if self._service is None:
            self.clear_data()
            return

        selected_episode = self.episode_combo.currentData()

        try:
            options = self._service.get_script_filter_options()
        except Exception as exc:
            self.table_model.set_rows([])
            self.cast_model.set_rows([])
            self.result_label.setText(f"Gagal membaca filter naskah: {exc}")
            return

        self._loading_filters = True
        try:
            self._reset_combo(self.episode_combo)
            for episode in options.episodes:
                self.episode_combo.addItem(f"Episode {episode}", episode)
            self._restore_combo(self.episode_combo, selected_episode)
        finally:
            self._loading_filters = False

        self._update_episode_navigation()
        self._refresh_cast_sidebar()
        self.refresh_rows()

    @staticmethod
    def _reset_combo(combo: QComboBox) -> None:
        combo.blockSignals(True)
        try:
            combo.clear()
            combo.addItem("Semua Episode", None)
        finally:
            combo.blockSignals(False)

    @staticmethod
    def _restore_combo(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    # ------------------------------------------------------------------
    # FILTER / EPISODE NAVIGATION
    # ------------------------------------------------------------------

    def _episode_changed(self) -> None:
        if self._loading_filters:
            return
        self._update_episode_navigation()
        self._refresh_cast_sidebar()
        self.refresh_rows()

    def _select_adjacent_episode(self, offset: int) -> None:
        count = self.episode_combo.count()
        if count <= 1:
            return

        current = max(0, self.episode_combo.currentIndex())
        target = min(max(current + int(offset), 0), count - 1)
        if target != current:
            self.episode_combo.setCurrentIndex(target)

    def _update_episode_navigation(self) -> None:
        count = self.episode_combo.count()
        current = self.episode_combo.currentIndex()
        self.prev_episode_button.setEnabled(count > 1 and current > 0)
        self.next_episode_button.setEnabled(
            count > 1 and 0 <= current < count - 1
        )

    def _search_changed(self) -> None:
        if self._loading_filters:
            return
        self.search_timer.start()

    # ------------------------------------------------------------------
    # CAST SIDEBAR
    # ------------------------------------------------------------------

    def _refresh_cast_sidebar(self) -> None:
        self.cast_model.set_rows([])
        if self._service is None:
            self.cast_scope_label.setText("Belum ada proyek terbuka")
            return

        episode_number = self.episode_combo.currentData()
        try:
            rows = self._service.get_script_rows(
                episode_number=episode_number,
                search="",
            )
        except Exception as exc:
            self.cast_scope_label.setText(f"Gagal membaca tokoh/talent: {exc}")
            return

        talent_cast: dict[str, set[str]] = {}
        unique_characters: set[str] = set()

        for row in rows:
            if not row.characters:
                talent_cast.setdefault("⚠ Belum dipetakan", set()).add(
                    "⚠ Belum dipetakan"
                )
                continue

            for index, character_name in enumerate(row.characters):
                character_text = str(character_name)
                talent_name = (
                    row.talents[index]
                    if index < len(row.talents)
                    else None
                )
                talent_text = (
                    str(talent_name)
                    if talent_name
                    else "⚠ Belum dipetakan"
                )
                talent_cast.setdefault(talent_text, set()).add(character_text)
                unique_characters.add(character_text)

        grouped_rows = [
            (
                talent_name,
                "\n".join(
                    sorted(
                        characters,
                        key=str.casefold,
                    )
                ),
            )
            for talent_name, characters in talent_cast.items()
        ]
        grouped_rows.sort(key=lambda item: item[0].casefold())
        self.cast_model.set_rows(grouped_rows)
        self.cast_table.resizeRowsToContents()

        unique_talents = {
            talent_name
            for talent_name in talent_cast
            if not talent_name.startswith("⚠")
        }
        scope = (
            "Semua episode"
            if episode_number is None
            else f"Episode {episode_number}"
        )
        self.cast_scope_label.setText(
            f"{scope} • "
            f"{self._format_count(len(unique_talents))} talent • "
            f"{self._format_count(len(unique_characters))} tokoh"
        )

    # ------------------------------------------------------------------
    # TABLE
    # ------------------------------------------------------------------

    def refresh_rows(self) -> None:
        if self._service is None:
            self.table_model.set_rows([])
            self.result_label.setText("Belum ada proyek terbuka")
            return

        episode_number = self.episode_combo.currentData()
        try:
            rows = self._service.get_script_rows(
                episode_number=self.episode_combo.currentData(),
                search=self.search_edit.text(),
            )
        except Exception as exc:
            self.table_model.set_rows([])
            self.result_label.setText(f"Gagal membaca data naskah: {exc}")
            return

        # DialogueService returns episode/time/source order. The view does not
        # enable interactive sorting, so EP1 stays before EP2 ... EP110.
        self.table_model.set_rows(rows)

        unresolved = sum(1 for row in rows if row.has_unresolved_cast)
        scope = (
            "Semua episode"
            if episode_number is None
            else f"Episode {episode_number}"
        )
        result_text = f"{self._format_count(len(rows))} dialog • {scope}"
        if unresolved:
            result_text += (
                f" • {self._format_count(unresolved)} belum dipetakan"
            )
        self.result_label.setText(result_text)

    @staticmethod
    def _format_count(value: int) -> str:
        return f"{value:,}".replace(",", ".")