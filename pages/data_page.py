from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
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
from services.data_service import DataService, UnresolvedCastRow
from services.review_service import ReviewService, ReviewedDialogueRow
from services.validation_service import (
    ACTION_REVIEW,
    ACTION_SOURCES,
    ACTION_TRACKING,
    ERROR,
    REVIEW,
    SYSTEM,
    WARNING,
    WORKFLOW,
    ValidationIssue,
    ValidationService,
)
from widgets.context_panel import ContextPanel
from widgets.page_shell import PageShell


class DataPage(PageShell):
    tracking_navigation_requested = Signal(int, int, int)
    data_changed = Signal()

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
    REVIEWED_COLOR = QColor("#EEF3F0")
    SYSTEM_ERROR_COLOR = QColor("#FDE7E9")
    REVIEW_COLOR = QColor("#FFF4CE")
    WORKFLOW_COLOR = QColor("#FCE8D5")

    def __init__(self, parent=None):
        self._database: Database | None = None
        self._service: DataService | None = None
        self._review_service: ReviewService | None = None
        self._validation_service: ValidationService | None = None
        self._loading = False
        self._unresolved_rows: list[UnresolvedCastRow] = []
        self._reviewed_rows: list[ReviewedDialogueRow] = []
        self._validation_issues: list[ValidationIssue] = []
        self._source_rows = []

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
            "Master data, manual review, source health, dan validation project."
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
        self.characters_table.cellDoubleClicked.connect(
            self._character_row_activated
        )
        self.unresolved_table.cellClicked.connect(
            self._unresolved_cell_clicked
        )
        self.sources_table.cellDoubleClicked.connect(self._source_row_open)
        self.validation_table.cellClicked.connect(self._validation_cell_clicked)
        self.tabs.currentChanged.connect(self._data_tab_changed)
        self.lock_mapping_button.clicked.connect(self._lock_selected_mapping)
        self.unlock_mapping_button.clicked.connect(self._unlock_selected_mapping)
        self.unresolved_view_combo.currentIndexChanged.connect(
            self._populate_unresolved_table
        )
        self.validation_severity_combo.currentIndexChanged.connect(
            self._apply_validation_filters
        )
        self.validation_category_combo.currentIndexChanged.connect(
            self._apply_validation_filters
        )
        self.validation_episode_combo.currentIndexChanged.connect(
            self._apply_validation_filters
        )
        self.validation_search.textChanged.connect(self._apply_validation_filters)

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
            ("active_dialogues", "Script Rows"),
            ("active_characters", "Characters"),
            ("active_talents", "Talents"),
            ("locked_mappings", "Locked Mappings"),
            ("non_dialogue", "Narration / Non-Dialogue"),
            ("needs_review", "Needs Review"),
            ("system_errors", "System Errors"),
            ("workflow_warnings", "Workflow Warnings"),
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
        layout.setSpacing(8)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("View"))
        self.unresolved_view_combo = QComboBox()
        self.unresolved_view_combo.addItem("Needs Review", "review")
        self.unresolved_view_combo.addItem("Narration / Non-Dialogue", "narration")
        self.unresolved_view_combo.addItem("All", "all")
        controls.addWidget(self.unresolved_view_combo)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.unresolved_table = self._new_table(
            ["EPS", "ISSUE", "CHARACTER", "TALENT", "DIALOG", "SOURCE"]
        )
        self.unresolved_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        self.unresolved_table.setToolTip(
            "Needs Review: klik CHARACTER untuk Add Character, TALENT untuk Add Talent, "
            "ISSUE untuk Mark as Narration, atau SOURCE untuk membuka source."
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
        self.sources_table.setToolTip("Double-click source untuk membuka workbook.")
        layout.addWidget(self.sources_table)
        self.tabs.addTab(tab, "Sources")

    def _build_validation_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        summary_row = QHBoxLayout()
        self.validation_system_label = QLabel("System 0")
        self.validation_review_label = QLabel("Review 0")
        self.validation_workflow_label = QLabel("Workflow 0")
        for label in (
            self.validation_system_label,
            self.validation_review_label,
            self.validation_workflow_label,
        ):
            label.setStyleSheet(
                "padding: 7px 10px; border: 1px solid #dadce0; "
                "border-radius: 5px; font-weight: 700; background: #ffffff;"
            )
            summary_row.addWidget(label)
        summary_row.addStretch(1)
        layout.addLayout(summary_row)

        self.validation_summary = QLabel("Validation belum dijalankan.")
        self.validation_summary.setObjectName("PageSubtitle")
        layout.addWidget(self.validation_summary)

        filters = QHBoxLayout()
        self.validation_severity_combo = QComboBox()
        self.validation_severity_combo.addItem("All Severity", None)
        self.validation_severity_combo.addItem("Error", ERROR)
        self.validation_severity_combo.addItem("Warning", WARNING)
        self.validation_category_combo = QComboBox()
        self.validation_category_combo.addItem("All Categories", None)
        self.validation_category_combo.addItem("System", SYSTEM)
        self.validation_category_combo.addItem("Needs Review", REVIEW)
        self.validation_category_combo.addItem("Workflow", WORKFLOW)
        self.validation_episode_combo = QComboBox()
        self.validation_episode_combo.addItem("All Episodes", None)
        self.validation_search = QLineEdit()
        self.validation_search.setPlaceholderText("Search validation…")
        filters.addWidget(self.validation_severity_combo)
        filters.addWidget(self.validation_category_combo)
        filters.addWidget(self.validation_episode_combo)
        filters.addWidget(self.validation_search, 1)
        layout.addLayout(filters)

        self.validation_table = self._new_table(
            ["SEVERITY", "CATEGORY", "EPS", "ENTITY", "CODE", "MESSAGE", "ACTION"]
        )
        self.validation_table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.Stretch
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
        self._review_service = ReviewService(database) if database is not None else None
        self._validation_service = (
            ValidationService(database) if database is not None else None
        )

        if self._service is None:
            self.clear_data()
            return

        self.reload()

    def refresh_from_database(self, database: Database | None) -> None:
        if database is not self._database or self._service is None:
            self.set_database(database)
            return

        if database is None:
            self.clear_data()
            return

        self.reload()

    def clear_data(self) -> None:
        self._database = None
        self._service = None
        self._review_service = None
        self._validation_service = None
        self._unresolved_rows = []
        self._reviewed_rows = []
        self._validation_issues = []
        self._source_rows = []
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
            self.validation_system_label.setText("System 0")
            self.validation_review_label.setText("Review 0")
            self.validation_workflow_label.setText("Workflow 0")
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
            self._load_review_data()
            self._load_characters()
            self._load_talents()
            self._load_sources()
            self._load_talent_combo()
            self._refresh_validation()
            self._load_overview()
            self._restore_character_selection(selected_character_id)
        finally:
            self._loading = False

        self._character_selection_changed()
        self._update_cast_mapping_visibility()

    def _load_review_data(self) -> None:
        if self._service is None or self._review_service is None:
            self._unresolved_rows = []
            self._reviewed_rows = []
            self._populate_unresolved_table()
            return

        reviewed_ids = self._review_service.get_active_non_dialogue_ids()
        self._unresolved_rows = [
            row
            for row in self._service.get_unresolved_cast()
            if row.dialogue_id not in reviewed_ids
        ]
        self._reviewed_rows = self._review_service.get_non_dialogues()
        self._populate_unresolved_table()

    def _load_overview(self) -> None:
        if self._service is None or self._validation_service is None:
            return

        overview = self._service.get_overview()
        summary = self._validation_service.summarize(self._validation_issues)
        needs_review = len({row.dialogue_id for row in self._unresolved_rows})
        values = {
            "active_sources": overview.active_sources,
            "active_dialogues": overview.active_dialogues,
            "active_characters": overview.active_characters,
            "active_talents": overview.active_talents,
            "locked_mappings": overview.locked_mappings,
            "non_dialogue": len(self._reviewed_rows),
            "needs_review": needs_review,
            "system_errors": summary.system_errors,
            "workflow_warnings": summary.workflow_warnings,
        }
        for key, value in values.items():
            self.overview_values[key].setText(self._format_count(value))

        if summary.system_errors:
            self.health_label.setText(
                f"✕ {summary.system_errors} system error. Buka Validation."
            )
        elif needs_review or summary.workflow_warnings:
            self.health_label.setText(
                f"⚠ {needs_review} item needs review • "
                f"{summary.workflow_warnings} workflow warning."
            )
        else:
            self.health_label.setText("✓ Project data healthy.")

    def _load_characters(self) -> None:
        if self._service is None:
            return
        reviewed_count = (
            self._review_service.get_active_non_dialogue_count()
            if self._review_service is not None
            else 0
        )
        rows = self._service.get_characters()
        display_rows: list[tuple[object, int, int]] = []
        for row in rows:
            active_dialogues = row.active_dialogues
            unresolved_dialogues = row.unresolved_dialogues
            if row.missing_character:
                active_dialogues = max(0, active_dialogues - reviewed_count)
                unresolved_dialogues = max(0, unresolved_dialogues - reviewed_count)
                if unresolved_dialogues == 0:
                    continue
            display_rows.append((row, active_dialogues, unresolved_dialogues))

        self.characters_table.setRowCount(len(display_rows))
        for row_index, (row, active_dialogues, unresolved_dialogues) in enumerate(
            display_rows
        ):
            character_item = QTableWidgetItem(row.name)
            character_item.setData(Qt.ItemDataRole.UserRole, row.id)

            if row.locked_talent_name:
                locked_text = row.locked_talent_name
            elif unresolved_dialogues:
                locked_text = "⚠ Talent Unknown"
            else:
                locked_text = "—"

            locked_item = QTableWidgetItem(locked_text)
            locked_item.setData(Qt.ItemDataRole.UserRole, row.locked_talent_id)
            source_item = QTableWidgetItem(row.mapping_source or "—")
            dialogue_item = QTableWidgetItem(str(active_dialogues))
            unresolved_item = QTableWidgetItem(str(unresolved_dialogues))

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
                    "Double-click untuk membuka Needs Review / Missing Character."
                )
            elif unresolved_dialogues:
                self._set_table_row_color(
                    self.characters_table,
                    row_index,
                    self.UNRESOLVED_TALENT_COLOR,
                )
                unresolved_item.setToolTip(
                    "Double-click untuk membuka unresolved character ini."
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

    def _load_sources(self) -> None:
        if self._service is None:
            return
        rows = self._service.get_sources()
        self._source_rows = rows
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
    def _set_table_row_color(table: QTableWidget, row: int, color: QColor) -> None:
        for column in range(table.columnCount()):
            item = table.item(row, column)
            if item is not None:
                item.setBackground(color)

    # ------------------------------------------------------------------
    # UNRESOLVED / MANUAL REVIEW
    # ------------------------------------------------------------------

    def _populate_unresolved_table(self, *args) -> None:
        mode = self.unresolved_view_combo.currentData() or "review"
        rows: list[tuple[str, object]] = []
        if mode in {"review", "all"}:
            rows.extend(("review", row) for row in self._unresolved_rows)
        if mode in {"narration", "all"}:
            rows.extend(("narration", row) for row in self._reviewed_rows)

        self.unresolved_table.setRowCount(len(rows))
        for row_index, (kind, row) in enumerate(rows):
            if kind == "review":
                assert isinstance(row, UnresolvedCastRow)
                issue_text = (
                    "Missing Character"
                    if row.character_id is None
                    else "Missing Talent"
                )
                values = (
                    str(row.episode_number),
                    issue_text,
                    row.character_name,
                    row.talent_name,
                    row.dialogue,
                    row.source_file_name,
                )
                color = (
                    self.UNRESOLVED_CHARACTER_COLOR
                    if row.character_id is None
                    else self.UNRESOLVED_TALENT_COLOR
                )
                dialogue_id = row.dialogue_id
            else:
                assert isinstance(row, ReviewedDialogueRow)
                values = (
                    str(row.episode_number),
                    "Narration / Non-Dialogue",
                    "—",
                    "—",
                    row.dialogue,
                    row.source_file_name,
                )
                color = self.REVIEWED_COLOR
                dialogue_id = row.dialogue_id

            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, (kind, dialogue_id))
                self.unresolved_table.setItem(row_index, column, item)
            self._set_table_row_color(self.unresolved_table, row_index, color)

            source_path = (
                row.source_file_path
                if isinstance(row, (UnresolvedCastRow, ReviewedDialogueRow))
                else ""
            )
            source_item = self.unresolved_table.item(row_index, 5)
            if source_item is not None:
                source_item.setToolTip(source_path or values[5])

    def _current_review_row(self, row_index: int):
        item = self.unresolved_table.item(row_index, 0)
        if item is None:
            return None, None
        marker = item.data(Qt.ItemDataRole.UserRole)
        if not marker:
            return None, None
        kind, dialogue_id = marker
        source = self._unresolved_rows if kind == "review" else self._reviewed_rows
        for row in source:
            if row.dialogue_id == dialogue_id:
                return kind, row
        return None, None

    def _unresolved_cell_clicked(self, row_index: int, column: int) -> None:
        if self._service is None:
            return
        kind, row = self._current_review_row(row_index)
        if row is None:
            return
        item = self.unresolved_table.item(row_index, column)
        if item is None:
            return

        menu = QMenu(self)
        if kind == "review":
            assert isinstance(row, UnresolvedCastRow)
            if column == 1 and row.character_id is None:
                mark_narration = menu.addAction("Mark as Narration / Non-Dialogue")
                chosen = self._exec_cell_menu(menu, item)
                if chosen is mark_narration:
                    self._mark_non_dialogue(row)
            elif column == 2:
                add_character = menu.addAction("Add Character…")
                add_character.setEnabled(row.character_id is None)
                chosen = self._exec_cell_menu(menu, item)
                if chosen is add_character:
                    self._add_character_to_unresolved(row)
            elif column == 3:
                add_talent = menu.addAction("Add Talent…")
                add_talent.setEnabled(row.character_id is not None)
                if row.character_id is None:
                    hint = menu.addAction("Add Character terlebih dahulu")
                    hint.setEnabled(False)
                chosen = self._exec_cell_menu(menu, item)
                if chosen is add_talent:
                    self._add_talent_to_unresolved(row)
            elif column == 5:
                open_source = menu.addAction("Open Source")
                open_source.setEnabled(bool(row.source_file_path))
                chosen = self._exec_cell_menu(menu, item)
                if chosen is open_source:
                    self._open_path(row.source_file_path)
        else:
            assert isinstance(row, ReviewedDialogueRow)
            if column in {1, 4}:
                restore = menu.addAction("Restore to Needs Review")
                chosen = self._exec_cell_menu(menu, item)
                if chosen is restore:
                    self._restore_to_review(row)
            elif column == 5:
                open_source = menu.addAction("Open Source")
                open_source.setEnabled(bool(row.source_file_path))
                chosen = self._exec_cell_menu(menu, item)
                if chosen is open_source:
                    self._open_path(row.source_file_path)

    def _exec_cell_menu(self, menu: QMenu, item: QTableWidgetItem):
        rect = self.unresolved_table.visualItemRect(item)
        position = self.unresolved_table.viewport().mapToGlobal(rect.bottomLeft())
        return menu.exec(position)

    def _mark_non_dialogue(self, row: UnresolvedCastRow) -> None:
        if self._review_service is None or row.character_id is not None:
            return
        answer = QMessageBox.question(
            self,
            "Mark as Narration / Non-Dialogue",
            (
                f"Episode {row.episode_number}\n\n{row.dialogue}\n\n"
                "Tandai row ini sebagai narasi/non-dialogue? Row tetap ada di SCRIPT, "
                "tetapi tidak lagi dianggap unresolved."
            ),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._review_service.mark_non_dialogue(row.dialogue_id)
        except Exception as exc:
            QMessageBox.critical(self, "Manual Review", str(exc))
            return
        self.reload()
        self.tabs.setCurrentIndex(self.TAB_INDEX["unresolved"])
        self.data_changed.emit()

    def _restore_to_review(self, row: ReviewedDialogueRow) -> None:
        if self._review_service is None:
            return
        try:
            self._review_service.restore_to_review(row.dialogue_id)
        except Exception as exc:
            QMessageBox.critical(self, "Manual Review", str(exc))
            return
        self.unresolved_view_combo.setCurrentIndex(0)
        self.reload()
        self.tabs.setCurrentIndex(self.TAB_INDEX["unresolved"])
        self._select_unresolved_dialogue(row.dialogue_id)
        self.data_changed.emit()

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
        self._select_unresolved_dialogue(row.dialogue_id)
        self.data_changed.emit()

    def _add_talent_to_unresolved(self, row: UnresolvedCastRow) -> None:
        if self._service is None or row.character_id is None:
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
        self.data_changed.emit()

    def _select_unresolved_dialogue(self, dialogue_id: int) -> None:
        self.unresolved_view_combo.setCurrentIndex(0)
        self._populate_unresolved_table()
        for row_index in range(self.unresolved_table.rowCount()):
            item = self.unresolved_table.item(row_index, 0)
            marker = item.data(Qt.ItemDataRole.UserRole) if item else None
            if marker and marker[1] == dialogue_id:
                self.unresolved_table.selectRow(row_index)
                self.unresolved_table.scrollToItem(item)
                return

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

    def _character_row_activated(self, row_index: int, column: int) -> None:
        unresolved_item = self.characters_table.item(row_index, 4)
        character_item = self.characters_table.item(row_index, 0)
        if unresolved_item is None or character_item is None:
            return
        try:
            unresolved_count = int(unresolved_item.text())
        except ValueError:
            unresolved_count = 0
        if unresolved_count <= 0:
            return
        character_id = character_item.data(Qt.ItemDataRole.UserRole)
        self.tabs.setCurrentIndex(self.TAB_INDEX["unresolved"])
        self.unresolved_view_combo.setCurrentIndex(0)
        self._populate_unresolved_table()
        for table_row in range(self.unresolved_table.rowCount()):
            kind, review_row = self._current_review_row(table_row)
            if kind != "review" or review_row is None:
                continue
            if character_id is None and review_row.character_id is None:
                self.unresolved_table.selectRow(table_row)
                self.unresolved_table.scrollToItem(
                    self.unresolved_table.item(table_row, 0)
                )
                return
            if character_id == review_row.character_id:
                self.unresolved_table.selectRow(table_row)
                self.unresolved_table.scrollToItem(
                    self.unresolved_table.item(table_row, 0)
                )
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
        self.mapping_character_label.setText(f"Character: {character_item.text()}")
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
        self.data_changed.emit()

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
        self.data_changed.emit()

    # ------------------------------------------------------------------
    # SOURCES
    # ------------------------------------------------------------------

    def _source_row_open(self, row_index: int, column: int) -> None:
        if row_index < 0 or row_index >= len(self._source_rows):
            return
        self._open_path(self._source_rows[row_index].file_path)

    def _select_source_episode(self, episode_number: int | None) -> None:
        self.tabs.setCurrentIndex(self.TAB_INDEX["sources"])
        if episode_number is None:
            return
        for row_index, row in enumerate(self._source_rows):
            if row.episode_number == episode_number:
                self.sources_table.selectRow(row_index)
                item = self.sources_table.item(row_index, 0)
                if item is not None:
                    self.sources_table.scrollToItem(item)
                return

    def _open_path(self, raw_path: str) -> None:
        path = Path(raw_path)
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
    # VALIDATION
    # ------------------------------------------------------------------

    def _refresh_validation(self) -> None:
        if self._validation_service is None:
            self._validation_issues = []
            return
        self._validation_issues = self._validation_service.validate()
        summary = self._validation_service.summarize(self._validation_issues)
        self.validation_system_label.setText(f"System {summary.system_errors}")
        self.validation_review_label.setText(f"Review {summary.needs_review}")
        self.validation_workflow_label.setText(
            f"Workflow {summary.workflow_warnings}"
        )
        if summary.system_errors:
            self.validation_summary.setText(
                f"✕ {summary.system_errors} system error • "
                f"{summary.needs_review} needs review • "
                f"{summary.workflow_warnings} workflow warning"
            )
        elif summary.needs_review or summary.workflow_warnings:
            self.validation_summary.setText(
                f"✓ System healthy • {summary.needs_review} needs review • "
                f"{summary.workflow_warnings} workflow warning"
            )
        else:
            self.validation_summary.setText(
                "✓ Validation passed — system, review queue, dan workflow bersih."
            )

        current_episode = self.validation_episode_combo.currentData()
        episodes = sorted(
            {
                issue.episode_number
                for issue in self._validation_issues
                if issue.episode_number is not None
            }
        )
        self.validation_episode_combo.blockSignals(True)
        try:
            self.validation_episode_combo.clear()
            self.validation_episode_combo.addItem("All Episodes", None)
            for episode in episodes:
                self.validation_episode_combo.addItem(f"Episode {episode}", episode)
            index = self.validation_episode_combo.findData(current_episode)
            self.validation_episode_combo.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self.validation_episode_combo.blockSignals(False)
        self._apply_validation_filters()

    def _filtered_validation_issues(self) -> list[ValidationIssue]:
        severity = self.validation_severity_combo.currentData()
        category = self.validation_category_combo.currentData()
        episode = self.validation_episode_combo.currentData()
        search = self.validation_search.text().strip().casefold()
        result = []
        for issue in self._validation_issues:
            if severity and issue.severity != severity:
                continue
            if category and issue.category != category:
                continue
            if episode is not None and issue.episode_number != episode:
                continue
            haystack = " ".join(
                (
                    issue.severity,
                    issue.category,
                    issue.code,
                    issue.entity,
                    issue.message,
                    str(issue.episode_number or ""),
                )
            ).casefold()
            if search and search not in haystack:
                continue
            result.append(issue)
        return result

    def _apply_validation_filters(self, *args) -> None:
        issues = self._filtered_validation_issues()
        self.validation_table.setRowCount(len(issues))
        action_labels = {
            ACTION_REVIEW: "Review",
            ACTION_SOURCES: "Sources",
            ACTION_TRACKING: "Tracking",
        }
        for row_index, issue in enumerate(issues):
            values = (
                issue.severity,
                issue.category,
                str(issue.episode_number) if issue.episode_number is not None else "—",
                issue.entity or "—",
                issue.code,
                issue.message,
                action_labels.get(issue.action, "—"),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, issue)
                self.validation_table.setItem(row_index, column, item)
            if issue.category == SYSTEM and issue.severity == ERROR:
                color = self.SYSTEM_ERROR_COLOR
            elif issue.category == REVIEW:
                color = self.REVIEW_COLOR
            elif issue.category == WORKFLOW:
                color = self.WORKFLOW_COLOR
            else:
                color = QColor("#FFFFFF")
            self._set_table_row_color(self.validation_table, row_index, color)

    def _validation_cell_clicked(self, row_index: int, column: int) -> None:
        if column != 6:
            return
        item = self.validation_table.item(row_index, column)
        issue = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not isinstance(issue, ValidationIssue):
            return
        if issue.action == ACTION_REVIEW and issue.dialogue_id is not None:
            self.tabs.setCurrentIndex(self.TAB_INDEX["unresolved"])
            self._select_unresolved_dialogue(issue.dialogue_id)
        elif issue.action == ACTION_SOURCES:
            self._select_source_episode(issue.episode_number)
        elif (
            issue.action == ACTION_TRACKING
            and issue.talent_id is not None
            and issue.character_id is not None
            and issue.episode_number is not None
        ):
            self.tracking_navigation_requested.emit(
                int(issue.talent_id),
                int(issue.character_id),
                int(issue.episode_number),
            )

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
        if self._validation_service is None:
            return []
        self._refresh_validation()
        self._load_overview()
        self.tabs.setCurrentIndex(self.TAB_INDEX["validation"])
        return list(self._validation_issues)

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
