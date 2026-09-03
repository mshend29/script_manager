from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.database import Database
from pages.data_page import DataPage
from pages.data_workspace_controller import DataWorkspaceController
from services.character_alias_service import (
    AliasAwareValidationService,
    CharacterAliasService,
)
from services.validation_service import ValidationService


class AliasDataPage(DataPage):
    """DATA page extended with manual canonical-character alias management."""

    def __init__(self, parent=None):
        self._alias_service: CharacterAliasService | None = None
        super().__init__(parent)
        self._controller = DataWorkspaceController(
            validation_factory=lambda database:
                AliasAwareValidationService(database, ValidationService)
        )
        self._install_alias_sidebar()
        self._update_cast_mapping_visibility()
        self._refresh_alias_controls()

    # ------------------------------------------------------------------
    # BUILD / DATABASE
    # ------------------------------------------------------------------

    def _build_characters_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)

        self.characters_table = self._new_table(
            [
                "CHARACTER",
                "LOCKED TALENT",
                "ALIASES",
                "SOURCE",
                "DIALOGUES",
                "UNRESOLVED",
            ]
        )
        for column in (0, 1, 2):
            self.characters_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.Stretch
            )
        layout.addWidget(self.characters_table)
        self.tabs.addTab(tab, "Character Mapping")

    def _install_alias_sidebar(self) -> None:
        context = self.layout().itemAt(0).widget()
        layout = getattr(context, "layout_root", None)
        if layout is None:
            return

        self.alias_title = QLabel("CHARACTER ALIAS")
        self.alias_title.setObjectName("SectionTitle")
        self.alias_selected_label = QLabel("Pilih character dari tabel.")
        self.alias_selected_label.setWordWrap(True)

        self.alias_target_combo = QComboBox()
        self.alias_target_combo.addItem("Alias of…", None)
        self.set_alias_button = QPushButton("Set as Alias")
        self.set_alias_button.setProperty("primary", True)

        self.alias_existing_combo = QComboBox()
        self.alias_existing_combo.addItem("Belum ada alias", None)
        self.add_alias_button = QPushButton("Add Alias Name…")
        self.add_alias_button.setProperty("secondary", True)
        self.remove_alias_button = QPushButton("Remove Alias / Restore")
        self.remove_alias_button.setProperty("secondary", True)

        self.alias_note = QLabel(
            "Alias menyatukan label source ke canonical character tanpa mengubah file client. "
            "Recording tetap; status tracking scope yang terdampak direset agar aman."
        )
        self.alias_note.setObjectName("MutedLabel")
        self.alias_note.setWordWrap(True)

        alias_widgets = [
            self.alias_title,
            self.alias_selected_label,
            self.alias_target_combo,
            self.set_alias_button,
            self.alias_existing_combo,
            self.add_alias_button,
            self.remove_alias_button,
            self.alias_note,
        ]
        insert_at = max(0, layout.count() - 1)
        for widget in alias_widgets:
            layout.insertWidget(insert_at, widget)
            insert_at += 1

        self._cast_mapping_widgets.extend(alias_widgets)

        self.set_alias_button.clicked.connect(self._set_selected_character_alias)
        self.add_alias_button.clicked.connect(self._add_alias_name)
        self.remove_alias_button.clicked.connect(self._remove_selected_alias)
        self.alias_target_combo.currentIndexChanged.connect(
            self._update_alias_button_states
        )
        self.alias_existing_combo.currentIndexChanged.connect(
            self._update_alias_button_states
        )

    def set_database(self, database: Database | None) -> None:
        self._alias_service = (
            CharacterAliasService(database) if database is not None else None
        )
        super().set_database(database)
        self._refresh_alias_controls()

    def clear_data(self) -> None:
        super().clear_data()
        self._alias_service = None
        if hasattr(self, "alias_target_combo"):
            self._refresh_alias_controls()

    # ------------------------------------------------------------------
    # CHARACTER TABLE + SIDEBAR
    # ------------------------------------------------------------------

    def _load_characters(self) -> None:
        if not self._controller.is_bound:
            return

        reviewed_count = self._controller.get_active_non_dialogue_count()
        aliases = (
            self._alias_service.aliases_by_canonical()
            if self._alias_service is not None
            else {}
        )
        rows = self._controller.get_characters()
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
            alias_items = aliases.get(int(row.id), []) if row.id is not None else []
            alias_text = ", ".join(alias.alias_name for alias in alias_items) or "—"
            alias_item = QTableWidgetItem(alias_text)
            if alias_items:
                alias_item.setToolTip("\n".join(alias.alias_name for alias in alias_items))

            source_item = QTableWidgetItem(row.mapping_source or "—")
            dialogue_item = QTableWidgetItem(str(active_dialogues))
            unresolved_item = QTableWidgetItem(str(unresolved_dialogues))

            items = (
                character_item,
                locked_item,
                alias_item,
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

    def _character_row_activated(self, row_index: int, column: int) -> None:
        unresolved_item = self.characters_table.item(row_index, 5)
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
        super()._character_selection_changed(*args)
        if hasattr(self, "alias_target_combo"):
            self._refresh_alias_controls()

    def _refresh_alias_controls(self) -> None:
        if not hasattr(self, "alias_target_combo"):
            return

        character_id = self._selected_character_id()
        self.alias_target_combo.blockSignals(True)
        self.alias_existing_combo.blockSignals(True)
        try:
            self.alias_target_combo.clear()
            self.alias_target_combo.addItem("Alias of…", None)
            self.alias_existing_combo.clear()
            self.alias_existing_combo.addItem("Belum ada alias", None)

            if self._alias_service is None or character_id is None:
                self.alias_selected_label.setText("Pilih character dari tabel.")
                return

            row = self.characters_table.currentRow()
            character_item = self.characters_table.item(row, 0)
            character_name = character_item.text() if character_item else "Character"
            self.alias_selected_label.setText(f"Selected: {character_name}")

            for candidate_id, candidate_name in self._alias_service.get_canonical_characters():
                if candidate_id != character_id:
                    self.alias_target_combo.addItem(candidate_name, candidate_id)

            aliases = self._alias_service.get_aliases(character_id)
            if aliases:
                self.alias_existing_combo.clear()
                self.alias_existing_combo.addItem("Pilih alias", None)
                for alias in aliases:
                    self.alias_existing_combo.addItem(alias.alias_name, alias.id)
        finally:
            self.alias_target_combo.blockSignals(False)
            self.alias_existing_combo.blockSignals(False)
            self._update_alias_button_states()

    def _update_alias_button_states(self, *args) -> None:
        active_tab = self.tabs.currentIndex() == self.TAB_INDEX["characters"]
        character_id = self._selected_character_id()
        available = self._alias_service is not None and character_id is not None and active_tab
        self.alias_target_combo.setEnabled(available)
        self.alias_existing_combo.setEnabled(available)
        self.add_alias_button.setEnabled(available)
        self.set_alias_button.setEnabled(
            available and self.alias_target_combo.currentData() is not None
        )
        self.remove_alias_button.setEnabled(
            available and self.alias_existing_combo.currentData() is not None
        )

    # ------------------------------------------------------------------
    # ALIAS ACTIONS
    # ------------------------------------------------------------------

    def _set_selected_character_alias(self) -> None:
        if self._alias_service is None:
            return
        source_id = self._selected_character_id()
        target_id = self.alias_target_combo.currentData()
        if source_id is None or target_id is None:
            return

        row = self.characters_table.currentRow()
        source_name = self.characters_table.item(row, 0).text()
        target_name = self.alias_target_combo.currentText()
        answer = QMessageBox.question(
            self,
            "Set Character Alias",
            (
                f"Jadikan '{source_name}' sebagai alias dari '{target_name}'?\n\n"
                "File source client tidak akan diubah. Dialog akan memakai canonical character, "
                "recording tetap tersimpan, dan status tracking scope terkait akan direset agar aman."
            ),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self._alias_service.set_character_alias(int(source_id), int(target_id))
        except Exception as exc:
            QMessageBox.critical(self, "Character Alias", str(exc))
            return

        self.reload()
        self.tabs.setCurrentIndex(self.TAB_INDEX["characters"])
        self._restore_character_selection(int(target_id))
        self._character_selection_changed()

    def _add_alias_name(self) -> None:
        if self._alias_service is None:
            return
        canonical_id = self._selected_character_id()
        if canonical_id is None:
            return
        row = self.characters_table.currentRow()
        canonical_name = self.characters_table.item(row, 0).text()
        alias_name, accepted = QInputDialog.getText(
            self,
            "Add Character Alias",
            f"Alias source untuk {canonical_name}:",
        )
        if not accepted or not alias_name.strip():
            return
        try:
            self._alias_service.add_alias_name(canonical_id, alias_name)
        except Exception as exc:
            QMessageBox.critical(self, "Character Alias", str(exc))
            return
        self.reload()
        self.tabs.setCurrentIndex(self.TAB_INDEX["characters"])
        self._restore_character_selection(canonical_id)
        self._character_selection_changed()

    def _remove_selected_alias(self) -> None:
        if self._alias_service is None:
            return
        canonical_id = self._selected_character_id()
        alias_id = self.alias_existing_combo.currentData()
        if canonical_id is None or alias_id is None:
            return
        alias_name = self.alias_existing_combo.currentText()
        answer = QMessageBox.question(
            self,
            "Remove Character Alias",
            (
                f"Hapus alias '{alias_name}'?\n\n"
                "Jika alias berasal dari character yang sudah pernah di-import, cast yang masih "
                "berasal dari alias akan dikembalikan menjadi character terpisah."
            ),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._alias_service.remove_alias(int(alias_id))
        except Exception as exc:
            QMessageBox.critical(self, "Character Alias", str(exc))
            return
        self.reload()
        self.tabs.setCurrentIndex(self.TAB_INDEX["characters"])
        self._restore_character_selection(canonical_id)
        self._character_selection_changed()
