from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.database import Database
from services.data_service import DataService, UnresolvedCastRow, ValidationIssue
from widgets.context_panel import ContextPanel
from widgets.page_shell import PageShell


class DataPage(PageShell):
    TAB_INDEX = {
        "overview": 0,
        "characters": 1,
        "talents": 2,
        "unresolved": 3,
        "sources": 4,
        "validation": 5,
    }

    UNRESOLVED_CHARACTER_COLOR = QColor("#FDE7E9")
    UNRESOLVED_TALENT_COLOR = QColor("#FFF4CE")

    def __init__(self, parent=None):
        self._database: Database | None = None
        self._service: DataService | None = None
        self._loading = False
        self._unresolved_rows: list[UnresolvedCastRow] = []

        context = ContextPanel("DATA")

        context.add_section_title("DATA HEALTH")
        self.health_label = QLabel("No project open")
        self.health_label.setWordWrap(True)
        context.add_widget(self.health_label)

        self.cast_mapping_title = context.add_section_title("CAST MAPPING")
        self.mapping_character_label = QLabel("Pilih character dari tabel.")
        self.mapping_character_label.setWordWrap(True)
        context.add_widget(self.mapping_character_label)

        self.mapping_talent_combo = QComboBox()
        self.mapping_talent_combo.setPlaceholderText("Pilih talent")
        context.add_widget(self.mapping_talent_combo)

        self.lock_mapping_button = QPushButton("Lock Mapping")
        self.lock_mapping_button.setProperty("primary", True)
        context.add_widget(self.lock_mapping_button)

        self.unlock_mapping_button = QPushButton("Unlock Mapping")
        self.unlock_mapping_button.setProperty("secondary", True)
        context.add_widget(self.unlock_mapping_button)

        self.mapping_note = QLabel(
            "Manual lock menjadi mapping authoritative untuk cast aktif. "
            "Unlock hanya melepas kunci; re-resolve berikutnya terjadi saat Refresh Data."
        )
        self.mapping_note.setWordWrap(True)
        self.mapping_note.setObjectName("MutedLabel")
        context.add_widget(self.mapping_note)

        self._cast_mapping_widgets = [
            self.cast_mapping_title,
            self.mapping_character_label,
            self.mapping_talent_combo,
            self.lock_mapping_button,
            self.unlock_mapping_button,
            self.mapping_note,
        ]
        context.add_stretch()

        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel("Data & Validation")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self.subtitle = QLabel(
            "Admin center untuk source, character/talent mapping, unresolved cast, backup, dan validation."
        )
        self.subtitle.setObjectName("PageSubtitle")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        self._build_overview_tab()
        self._build_characters_tab()
        self._build_talents_tab()
        self._build_unresolved_tab()
        self._build_sources_tab()
        self._build_validation_tab()

        super().__init__(context, workspace, parent)

        self.characters_table.currentCellChanged.connect(
            self._character_selection_changed
        )
        self.unresolved_table.cellClicked.connect(
            self._unresolved_cell_clicked
        )
        self.tabs.currentChanged.connect(self._data_tab_changed)
        self.lock_mapping_button.clicked.connect(self._lock_selected_mapping)
        self.unlock_mapping_button.clicked.connect(self._unlock_selected_mapping)

        self._set_mapping_enabled(False)
        self._update_cast_mapping_visibility()

    # ------------------------------------------------------------------
    # BUILD UI
    # ------------------------------------------------------------------

    def _build_overview_tab(self) -> None:
        tab = QWidget()
        root = QVBoxLayout(tab)
        root.setContentsMargins(14, 14, 14, 14)

        card = QFrame()
        card.setObjectName("DashboardCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(18, 18, 18, 18)
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(16)

        self.overview_values: dict[str, QLabel] = {}
        metrics = [
            ("active_sources", "Active Sources"),
            ("inactive_sources", "Inactive Sources"),
            ("active_dialogues", "Active Dialogues"),
            ("active_characters", "Characters"),
            ("active_talents", "Talents"),
            ("locked_mappings", "Locked Mappings"),
            ("unresolved_cast", "Unresolved Cast"),
        ]

        for index, (key, label_text) in enumerate(metrics):
            row = index // 3
            column = index % 3
            box = QFrame()
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(8, 8, 8, 8)
            value = QLabel("0")
            value.setStyleSheet("font-size: 20pt; font-weight: 700;")
            label = QLabel(label_text)
            label.setObjectName("MutedLabel")
            box_layout.addWidget(value)
            box_layout.addWidget(label)
            grid.addWidget(box, row, column)
            self.overview_values[key] = value

        root.addWidget(card)
        root.addStretch(1)
        self.tabs.addTab(tab, "Overview")

    def _build_characters_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)

        self.characters_table = self._new_table(
            ["CHARACTER", "LOCKED TALENT", "SOURCE", "DIALOGUES", "UNRESOLVED"]
        )
        self.characters_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.characters_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.characters_table)
        self.tabs.addTab(tab, "Character Mapping")

    def _build_talents_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)

        self.talents_table = self._new_table(
            ["TALENT", "CHARACTERS", "ACTIVE DIALOGUES"]
        )
        self.talents_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.talents_table)
        self.tabs.addTab(tab, "Talents")

    def _build_unresolved_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)

        self.unresolved_table = self._new_table(
            ["EPS", "CHARACTER", "TALENT", "DIALOG", "SOURCE"]
        )
        self.unresolved_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self.unresolved_table.setToolTip(
            "Klik CHARACTER untuk Add Character, TALENT untuk Add Talent, "
            "atau SOURCE untuk membuka file source."
        )
        layout.addWidget(self.unresolved_table)
        self.tabs.addTab(tab, "Unresolved")

    def _build_sources_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)

        self.sources_table = self._new_table(
            ["EPS", "FILE", "STATE", "IMPORTED", "LAST SEEN"]
        )
        self.sources_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.sources_table)
        self.tabs.addTab(tab, "Sources")

    def _build_validation_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)

        self.validation_summary = QLabel("Validation belum dijalankan.")
        self.validation_summary.setObjectName("PageSubtitle")
        layout.addWidget(self.validation_summary)

        self.validation_table = self._new_table(
            ["SEVERITY", "CODE", "MESSAGE"]
        )
        self.validation_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.validation_table)
        self.tabs.addTab(tab, "Validation")

    @staticmethod
    def _new_table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(False)
        for column in range(len(headers)):
            table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        return table

    # ------------------------------------------------------------------
    # DATABASE BINDING
    # ------------------------------------------------------------------

    def set_database(self, database: Database | None) -> None:
        self._database = database
        self._service = DataService(database) if database is not None else None

        if self._service is None:
            self.clear_data()
            return

        self.reload()

    def clear_data(self) -> None:
        self._database = None
        self._service = None
        self._unresolved_rows = []
        self._loading = True
        try:
            for table in (
                self.characters_table,
                self.talents_table,
                self.unresolved_table,
                self.sources_table,
                self.validation_table,
            ):
                table.setRowCount(0)
            self.mapping_talent_combo.clear()
            self.mapping_character_label.setText("Pilih character dari tabel.")
            self.health_label.setText("No project open")
            self.validation_summary.setText("Validation belum dijalankan.")
            for label in self.overview_values.values():
                label.setText("0")
        finally:
            self._loading = False
        self._set_mapping_enabled(False)
        self._update_cast_mapping_visibility()

    def reload(self) -> None:
        if self._service is None:
            self.clear_data()
            return

        selected_character_id = self._selected_character_id()
        self._loading = True
        try:
            self._load_overview()
            self._load_characters()
            self._load_talents()
            self._load_unresolved()
            self._load_sources()
            self._load_talent_combo()
            self._restore_character_selection(selected_character_id)
        finally:
            self._loading = False

        self._character_selection_changed()
        self._update_cast_mapping_visibility()

    def _load_overview(self) -> None:
        if self._service is None:
            return
        overview = self._service.get_overview()
        values = {
            "active_sources": overview.active_sources,
            "inactive_sources": overview.inactive_sources,
            "active_dialogues": overview.active_dialogues,
            "active_characters": overview.active_characters,
            "active_talents": overview.active_talents,
            "locked_mappings": overview.locked_mappings,
            "unresolved_cast": overview.unresolved_cast,
        }
        for key, value in values.items():
            self.overview_values[key].setText(self._format_count(value))

        if overview.unresolved_cast:
            self.health_label.setText(
                f"⚠ {self._format_count(overview.unresolved_cast)} unresolved cast. "
                "Buka Character Mapping atau Unresolved."
            )
        else:
            self.health_label.setText("✓ Tidak ada unresolved cast aktif.")

    def _load_characters(self) -> None:
        if self._service is None:
            return
        rows = self._service.get_characters()
        self.characters_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            character_item = QTableWidgetItem(row.name)
            character_item.setData(Qt.ItemDataRole.UserRole, row.id)

            if row.locked_talent_name:
                locked_text = row.locked_talent_name
            elif row.unresolved_dialogues:
                locked_text = "⚠ Talent Unknown"
            else:
                locked_text = "—"

            locked_item = QTableWidgetItem(locked_text)
            locked_item.setData(Qt.ItemDataRole.UserRole, row.locked_talent_id)
            source_item = QTableWidgetItem(row.mapping_source or "—")
            dialogue_item = QTableWidgetItem(str(row.active_dialogues))
            unresolved_item = QTableWidgetItem(str(row.unresolved_dialogues))

            items = (
                character_item,
                locked_item,
                source_item,
                dialogue_item,
                unresolved_item,
            )
            for column, item in enumerate(items):
                self.characters_table.setItem(row_index, column, item)

            if row.missing_character:
                self._set_table_row_color(
                    self.characters_table,
                    row_index,
                    self.UNRESOLVED_CHARACTER_COLOR,
                )
                character_item.setToolTip(
                    "Dialog aktif tanpa character. Putuskan manual dari tab Unresolved."
                )
                locked_item.setToolTip(
                    "Talent belum dapat ditentukan sebelum character ditetapkan."
                )
            elif row.unresolved_dialogues:
                self._set_table_row_color(
                    self.characters_table,
                    row_index,
                    self.UNRESOLVED_TALENT_COLOR,
                )
                unresolved_item.setToolTip(
                    "Ada dialog aktif dengan character ini tetapi talent belum ditentukan."
                )

    def _load_talents(self) -> None:
        if self._service is None:
            return
        rows = self._service.get_talents()
        self.talents_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            talent_item = QTableWidgetItem(row.name)
            talent_item.setData(Qt.ItemDataRole.UserRole, row.id)
            self.talents_table.setItem(row_index, 0, talent_item)
            self.talents_table.setItem(
                row_index, 1, QTableWidgetItem(str(row.character_count))
            )
            self.talents_table.setItem(
                row_index, 2, QTableWidgetItem(str(row.active_dialogues))
            )

    def _load_unresolved(self) -> None:
        if self._service is None:
            return
        rows = self._service.get_unresolved_cast()
        self._unresolved_rows = rows
        self.unresolved_table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            episode_item = QTableWidgetItem(str(row.episode_number))
            episode_item.setData(Qt.ItemDataRole.UserRole, row.dialogue_id)

            character_item = QTableWidgetItem(row.character_name)
            character_item.setData(Qt.ItemDataRole.UserRole, row.character_id)
            character_item.setToolTip(
                "Klik untuk menambahkan character secara manual."
                if row.character_id is None
                else "Character sudah tersedia; unresolved ini memerlukan talent."
            )

            talent_item = QTableWidgetItem(row.talent_name)
            talent_item.setData(Qt.ItemDataRole.UserRole, row.talent_id)
            talent_item.setToolTip(
                "Klik untuk menambahkan/memilih talent secara manual."
            )

            dialogue_item = QTableWidgetItem(row.dialogue)
            source_item = QTableWidgetItem(row.source_file_name)
            source_item.setToolTip(row.source_file_path or row.source_file_name)

            for column, item in enumerate(
                (episode_item, character_item, talent_item, dialogue_item, source_item)
            ):
                self.unresolved_table.setItem(row_index, column, item)

            color = (
                self.UNRESOLVED_CHARACTER_COLOR
                if row.character_id is None
                else self.UNRESOLVED_TALENT_COLOR
            )
            self._set_table_row_color(self.unresolved_table, row_index, color)

    def _load_sources(self) -> None:
        if self._service is None:
            return
        rows = self._service.get_sources()
        self.sources_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            episode_text = (
                str(row.episode_number) if row.episode_number is not None else "—"
            )
            episode_item = QTableWidgetItem(episode_text)
            file_item = QTableWidgetItem(row.file_name)
            file_item.setToolTip(row.file_path)
            state_item = QTableWidgetItem("Active" if row.is_active else "Inactive")
            imported_item = QTableWidgetItem(row.imported_at or "—")
            last_seen_item = QTableWidgetItem(row.last_seen_at or "—")
            for column, item in enumerate(
                (episode_item, file_item, state_item, imported_item, last_seen_item)
            ):
                self.sources_table.setItem(row_index, column, item)

    def _load_talent_combo(self) -> None:
        if self._service is None:
            return
        current = self.mapping_talent_combo.currentData()
        self.mapping_talent_combo.clear()
        self.mapping_talent_combo.addItem("Pilih talent", None)
        for talent_id, name in self._service.get_talent_options():
            self.mapping_talent_combo.addItem(name, talent_id)
        index = self.mapping_talent_combo.findData(current)
        self.mapping_talent_combo.setCurrentIndex(index if index >= 0 else 0)

    @staticmethod
    def _set_table_row_color(
        table: QTableWidget,
        row: int,
        color: QColor,
    ) -> None:
        for column in range(table.columnCount()):
            item = table.item(row, column)
            if item is not None:
                item.setBackground(color)

    # ------------------------------------------------------------------
    # UNRESOLVED MANUAL ACTIONS
    # ------------------------------------------------------------------

    def _unresolved_cell_clicked(self, row_index: int, column: int) -> None:
        if (
            self._service is None
            or row_index < 0
            or row_index >= len(self._unresolved_rows)
        ):
            return

        row = self._unresolved_rows[row_index]
        item = self.unresolved_table.item(row_index, column)
        if item is None:
            return

        menu = QMenu(self)
        chosen = None

        if column == 1:
            add_character = menu.addAction("Add Character…")
            add_character.setEnabled(row.character_id is None)
            if row.character_id is not None:
                existing = menu.addAction(f"Character: {row.character_name}")
                existing.setEnabled(False)
            chosen = self._exec_cell_menu(menu, item)
            if chosen is add_character:
                self._add_character_to_unresolved(row)

        elif column == 2:
            add_talent = menu.addAction("Add Talent…")
            add_talent.setEnabled(row.character_id is not None)
            if row.character_id is None:
                hint = menu.addAction("Add Character terlebih dahulu")
                hint.setEnabled(False)
            chosen = self._exec_cell_menu(menu, item)
            if chosen is add_talent:
                self._add_talent_to_unresolved(row)

        elif column == 4:
            open_source = menu.addAction("Open Source")
            open_source.setEnabled(bool(row.source_file_path))
            chosen = self._exec_cell_menu(menu, item)
            if chosen is open_source:
                self._open_unresolved_source(row)

    def _exec_cell_menu(self, menu: QMenu, item: QTableWidgetItem):
        rect = self.unresolved_table.visualItemRect(item)
        position = self.unresolved_table.viewport().mapToGlobal(rect.bottomLeft())
        return menu.exec(position)

    def _add_character_to_unresolved(self, row: UnresolvedCastRow) -> None:
        if self._service is None or row.character_id is not None:
            return

        name, accepted = QInputDialog.getText(
            self,
            "Add Character",
            f"Character untuk Episode {row.episode_number}:\n{row.dialogue}",
        )
        if not accepted or not name.strip():
            return

        try:
            character_id = self._service.ensure_character(name)
            self._service.assign_missing_character(row.dialogue_id, character_id)
        except Exception as exc:
            QMessageBox.critical(self, "Add Character", str(exc))
            return

        self.reload()
        self.tabs.setCurrentIndex(self.TAB_INDEX["unresolved"])

    def _add_talent_to_unresolved(self, row: UnresolvedCastRow) -> None:
        if self._service is None:
            return
        if row.character_id is None:
            QMessageBox.information(
                self,
                "Add Talent",
                "Tambahkan character terlebih dahulu sebelum menentukan talent.",
            )
            return

        name, accepted = QInputDialog.getText(
            self,
            "Add Talent",
            f"Talent untuk {row.character_name}:",
        )
        if not accepted or not name.strip():
            return

        try:
            talent_id = self._service.ensure_talent(name)
            self._service.set_locked_mapping(row.character_id, talent_id)
        except Exception as exc:
            QMessageBox.critical(self, "Add Talent", str(exc))
            return

        self.reload()
        self.tabs.setCurrentIndex(self.TAB_INDEX["unresolved"])

    def _open_unresolved_source(self, row: UnresolvedCastRow) -> None:
        path = Path(row.source_file_path)
        if not path.is_file():
            QMessageBox.warning(
                self,
                "Open Source",
                f"Source file tidak ditemukan.\n\n{path}",
            )
            return

        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.warning(
                self,
                "Open Source",
                f"Source file tidak dapat dibuka.\n\n{path}",
            )

    # ------------------------------------------------------------------
    # CHARACTER MAPPING EDITOR
    # ------------------------------------------------------------------

    def _selected_character_id(self) -> int | None:
        row = self.characters_table.currentRow()
        if row < 0:
            return None
        item = self.characters_table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return int(value) if value is not None else None

    def _restore_character_selection(self, character_id: int | None) -> None:
        if character_id is None:
            return
        for row in range(self.characters_table.rowCount()):
            item = self.characters_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == character_id:
                self.characters_table.selectRow(row)
                self.characters_table.setCurrentCell(row, 0)
                return

    def _character_selection_changed(self, *args) -> None:
        if self._loading:
            return
        if self.tabs.currentIndex() != self.TAB_INDEX["characters"]:
            self._set_mapping_enabled(False)
            return

        row = self.characters_table.currentRow()
        if row < 0:
            self.mapping_character_label.setText("Pilih character dari tabel.")
            self.mapping_talent_combo.setCurrentIndex(0)
            self._set_mapping_enabled(False)
            return

        character_item = self.characters_table.item(row, 0)
        talent_item = self.characters_table.item(row, 1)
        if character_item is None:
            return

        character_id = character_item.data(Qt.ItemDataRole.UserRole)
        if character_id is None:
            self.mapping_character_label.setText(
                "Character Unknown — selesaikan manual dari tab Unresolved."
            )
            self.mapping_talent_combo.setCurrentIndex(0)
            self._set_mapping_enabled(False)
            return

        self.mapping_character_label.setText(
            f"Character: {character_item.text()}"
        )
        locked_talent_id = (
            talent_item.data(Qt.ItemDataRole.UserRole)
            if talent_item is not None
            else None
        )
        index = self.mapping_talent_combo.findData(locked_talent_id)
        self.mapping_talent_combo.setCurrentIndex(index if index >= 0 else 0)
        self._set_mapping_enabled(True)

    def _set_mapping_enabled(self, enabled: bool) -> None:
        active = (
            enabled
            and self._service is not None
            and self.tabs.currentIndex() == self.TAB_INDEX["characters"]
        )
        self.mapping_talent_combo.setEnabled(active)
        self.lock_mapping_button.setEnabled(active)
        self.unlock_mapping_button.setEnabled(active)

    def _data_tab_changed(self, *args) -> None:
        self._update_cast_mapping_visibility()
        if self.tabs.currentIndex() == self.TAB_INDEX["characters"]:
            self._character_selection_changed()

    def _update_cast_mapping_visibility(self) -> None:
        visible = self.tabs.currentIndex() == self.TAB_INDEX["characters"]
        for widget in self._cast_mapping_widgets:
            widget.setVisible(visible)
        if not visible:
            self._set_mapping_enabled(False)

    def _lock_selected_mapping(self) -> None:
        if self._service is None:
            return
        character_id = self._selected_character_id()
        talent_id = self.mapping_talent_combo.currentData()
        if character_id is None or talent_id is None:
            QMessageBox.information(
                self,
                "Cast Mapping",
                "Pilih character dan talent terlebih dahulu.",
            )
            return

        row = self.characters_table.currentRow()
        character_name = self.characters_table.item(row, 0).text()
        talent_name = self.mapping_talent_combo.currentText()
        answer = QMessageBox.question(
            self,
            "Lock Cast Mapping",
            (
                f"Kunci {character_name} → {talent_name}?\n\n"
                "Cast aktif untuk character ini akan langsung memakai talent tersebut."
            ),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self._service.set_locked_mapping(character_id, int(talent_id))
        except Exception as exc:
            QMessageBox.critical(self, "Cast Mapping", str(exc))
            return

        self.reload()
        self.tabs.setCurrentIndex(self.TAB_INDEX["characters"])

    def _unlock_selected_mapping(self) -> None:
        if self._service is None:
            return
        character_id = self._selected_character_id()
        if character_id is None:
            return

        try:
            self._service.unlock_mapping(character_id)
        except Exception as exc:
            QMessageBox.critical(self, "Cast Mapping", str(exc))
            return

        self.reload()
        self.tabs.setCurrentIndex(self.TAB_INDEX["characters"])

    # ------------------------------------------------------------------
    # RIBBON-FACING ACTIONS
    # ------------------------------------------------------------------

    def show_section(self, section: str) -> None:
        if section == "cast":
            section = "characters"
        index = self.TAB_INDEX.get(section)
        if index is not None:
            self.tabs.setCurrentIndex(index)

    def run_validation(self) -> list[ValidationIssue]:
        if self._service is None:
            return []

        issues = self._service.validate()
        self.validation_table.setRowCount(len(issues))
        for row_index, issue in enumerate(issues):
            self.validation_table.setItem(
                row_index, 0, QTableWidgetItem(issue.severity)
            )
            self.validation_table.setItem(
                row_index, 1, QTableWidgetItem(issue.code)
            )
            self.validation_table.setItem(
                row_index, 2, QTableWidgetItem(issue.message)
            )

        errors = sum(1 for issue in issues if issue.severity == "ERROR")
        warnings = sum(1 for issue in issues if issue.severity == "WARNING")
        if not issues:
            self.validation_summary.setText("✓ Validation passed — tidak ada issue.")
        else:
            self.validation_summary.setText(
                f"{errors} error • {warnings} warning"
            )

        self.tabs.setCurrentIndex(self.TAB_INDEX["validation"])
        return issues

    def backup_database(self) -> Path:
        if self._service is None:
            raise RuntimeError("Belum ada project yang dibuka.")
        return self._service.backup_database()

    def rebuild_indexes(self) -> None:
        if self._service is None:
            raise RuntimeError("Belum ada project yang dibuka.")
        self._service.rebuild_indexes()
        self.reload()

    @staticmethod
    def _format_count(value: int) -> str:
        return f"{value:,}".replace(",", ".")
