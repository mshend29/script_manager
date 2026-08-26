from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QInputDialog, QLabel, QMessageBox, QPushButton

from core.database import Database
from pages.data_page import DataPage
from services.alias_service import CharacterAliasRow, CharacterAliasService
from services.data_service import DataService
from services.review_service import ReviewService
from services.validation_service import ValidationIssue
from services.alias_validation_service import AliasValidationService


class AliasAwareDataPage(DataPage):
    """DATA page extension for manual canonical character aliases."""

    def __init__(self, parent=None):
        self._alias_service: CharacterAliasService | None = None
        self._selected_aliases: list[CharacterAliasRow] = []
        super().__init__(parent)
        self._install_alias_ui()

    def _install_alias_ui(self) -> None:
        # PageShell places ContextPanel as the first child in its root layout.
        context = self.layout().itemAt(0).widget()
        root = context.layout_root
        insert_at = max(0, root.count() - 1)  # before the existing stretch

        self.identity_title = QLabel("CHARACTER IDENTITY")
        self.identity_title.setObjectName("SectionTitle")
        root.insertSpacing(insert_at, 6)
        insert_at += 1
        root.insertWidget(insert_at, self.identity_title)
        insert_at += 1

        self.alias_summary_label = QLabel("Aliases: —")
        self.alias_summary_label.setWordWrap(True)
        root.insertWidget(insert_at, self.alias_summary_label)
        insert_at += 1

        self.alias_combo = QComboBox()
        self.alias_combo.addItem("No aliases", None)
        root.insertWidget(insert_at, self.alias_combo)
        insert_at += 1

        self.set_alias_button = QPushButton("Set as Alias of…")
        self.set_alias_button.setProperty("secondary", True)
        root.insertWidget(insert_at, self.set_alias_button)
        insert_at += 1

        self.restore_alias_button = QPushButton("Restore Selected Alias")
        self.restore_alias_button.setProperty("secondary", True)
        root.insertWidget(insert_at, self.restore_alias_button)
        insert_at += 1

        self.alias_note = QLabel(
            "Alias hanya mengubah identitas operasional di database. "
            "Nama character pada source client dan tampilan SCRIPT tidak diubah."
        )
        self.alias_note.setWordWrap(True)
        self.alias_note.setObjectName("MutedLabel")
        root.insertWidget(insert_at, self.alias_note)

        self._cast_mapping_widgets.extend(
            [
                self.identity_title,
                self.alias_summary_label,
                self.alias_combo,
                self.set_alias_button,
                self.restore_alias_button,
                self.alias_note,
            ]
        )

        self.set_alias_button.clicked.connect(self._set_selected_as_alias)
        self.restore_alias_button.clicked.connect(self._restore_selected_alias)
        self.alias_combo.currentIndexChanged.connect(self._update_alias_buttons)
        self._update_alias_ui(None)
        self._update_cast_mapping_visibility()

    # ------------------------------------------------------------------
    # DATABASE BINDING
    # ------------------------------------------------------------------

    def set_database(self, database: Database | None) -> None:
        # Mirror DataPage binding so Validation uses the alias-aware extension
        # from the first reload rather than requiring a second refresh.
        self._database = database
        self._service = DataService(database) if database is not None else None
        self._review_service = ReviewService(database) if database is not None else None
        self._validation_service = (
            AliasValidationService(database) if database is not None else None
        )
        self._alias_service = (
            CharacterAliasService(database) if database is not None else None
        )

        if self._service is None:
            self.clear_data()
            return
        self.reload()

    def clear_data(self) -> None:
        self._alias_service = None
        self._selected_aliases = []
        super().clear_data()
        if hasattr(self, "alias_combo"):
            self._update_alias_ui(None)

    # ------------------------------------------------------------------
    # CHARACTER TABLE
    # ------------------------------------------------------------------

    def _build_characters_tab(self) -> None:
        # Build the base tab, then add a stable ALIASES column. Keeping LOCKED
        # TALENT at index 1 lets the inherited cast-mapping editor stay intact.
        super()._build_characters_tab()
        self.characters_table.setColumnCount(6)
        self.characters_table.setHorizontalHeaderLabels(
            [
                "CHARACTER",
                "LOCKED TALENT",
                "ALIASES",
                "SOURCE",
                "DIALOGUES",
                "UNRESOLVED",
            ]
        )
        self.characters_table.horizontalHeader().setSectionResizeMode(
            0, self.characters_table.horizontalHeader().ResizeMode.Stretch
        )
        self.characters_table.horizontalHeader().setSectionResizeMode(
            1, self.characters_table.horizontalHeader().ResizeMode.Stretch
        )
        self.characters_table.horizontalHeader().setSectionResizeMode(
            2, self.characters_table.horizontalHeader().ResizeMode.Stretch
        )

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
            from PySide6.QtWidgets import QTableWidgetItem

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

            aliases_text = " / ".join(row.aliases) if row.aliases else "—"
            aliases_item = QTableWidgetItem(aliases_text)
            aliases_item.setToolTip(
                "Source character yang dianggap sebagai character canonical ini."
                if row.aliases
                else "Belum ada alias."
            )
            source_item = QTableWidgetItem(row.mapping_source or "—")
            dialogue_item = QTableWidgetItem(str(active_dialogues))
            unresolved_item = QTableWidgetItem(str(unresolved_dialogues))

            for column, item in enumerate(
                (
                    character_item,
                    locked_item,
                    aliases_item,
                    source_item,
                    dialogue_item,
                    unresolved_item,
                )
            ):
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
        # Same behavior as DataPage, adjusted for the inserted ALIASES column.
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
                self.unresolved_table.scrollToItem(self.unresolved_table.item(table_row, 0))
                return
            if character_id == review_row.character_id:
                self.unresolved_table.selectRow(table_row)
                self.unresolved_table.scrollToItem(self.unresolved_table.item(table_row, 0))
                return

    def _character_selection_changed(self, *args) -> None:
        super()._character_selection_changed(*args)
        self._update_alias_ui(self._selected_character_id())

    # ------------------------------------------------------------------
    # ALIAS ACTIONS
    # ------------------------------------------------------------------

    def _update_alias_ui(self, character_id: int | None) -> None:
        if not hasattr(self, "alias_combo"):
            return
        self.alias_combo.blockSignals(True)
        try:
            self.alias_combo.clear()
            self._selected_aliases = []
            if self._alias_service is not None and character_id is not None:
                self._selected_aliases = self._alias_service.get_aliases_for_character(
                    int(character_id)
                )
            if self._selected_aliases:
                for alias in self._selected_aliases:
                    self.alias_combo.addItem(alias.source_name, alias.id)
                self.alias_summary_label.setText(
                    "Aliases: " + " / ".join(a.source_name for a in self._selected_aliases)
                )
            else:
                self.alias_combo.addItem("No aliases", None)
                self.alias_summary_label.setText("Aliases: —")
        finally:
            self.alias_combo.blockSignals(False)
        self._update_alias_buttons()

    def _update_alias_buttons(self, *args) -> None:
        character_id = self._selected_character_id()
        visible = self.tabs.currentIndex() == self.TAB_INDEX["characters"]
        valid_character = (
            visible
            and self._alias_service is not None
            and character_id is not None
        )
        # A canonical that already owns aliases cannot itself be demoted; this
        # prevents alias chains and keeps Restore deterministic.
        self.set_alias_button.setEnabled(
            bool(valid_character and not self._selected_aliases)
        )
        self.restore_alias_button.setEnabled(
            bool(valid_character and self.alias_combo.currentData() is not None)
        )

    def _set_selected_as_alias(self) -> None:
        if self._alias_service is None:
            return
        source_id = self._selected_character_id()
        if source_id is None:
            return
        row = self.characters_table.currentRow()
        source_item = self.characters_table.item(row, 0)
        source_name = source_item.text() if source_item else str(source_id)

        options = self._alias_service.get_canonical_options(
            exclude_character_id=int(source_id)
        )
        if not options:
            QMessageBox.information(
                self,
                "Character Alias",
                "Tidak ada canonical character lain yang tersedia.",
            )
            return
        labels = [name for _id, name in options]
        selected, accepted = QInputDialog.getItem(
            self,
            "Set as Alias of",
            f"'{source_name}' adalah alias dari character:",
            labels,
            0,
            False,
        )
        if not accepted or not selected:
            return
        target_id = next(character_id for character_id, name in options if name == selected)

        answer = QMessageBox.question(
            self,
            "Confirm Character Alias",
            (
                f"Gunakan '{selected}' sebagai canonical character untuk '{source_name}'?\n\n"
                "Source Excel dan label di SCRIPT tidak diubah. DIALOG dan TRACKING "
                "akan menggabungkan keduanya. Status stem/delivery pada episode "
                "terdampak akan direset karena identitas tracking berubah."
            ),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self._alias_service.set_alias(
                source_character_id=int(source_id),
                canonical_character_id=int(target_id),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Character Alias", str(exc))
            return

        self.reload()
        self.tabs.setCurrentIndex(self.TAB_INDEX["characters"])
        self._restore_character_selection(int(target_id))
        self._character_selection_changed()

    def _restore_selected_alias(self) -> None:
        if self._alias_service is None:
            return
        alias_id = self.alias_combo.currentData()
        if alias_id is None:
            return
        alias = next(
            (item for item in self._selected_aliases if item.id == int(alias_id)),
            None,
        )
        if alias is None:
            return

        answer = QMessageBox.question(
            self,
            "Restore Character Alias",
            (
                f"Pisahkan '{alias.source_name}' dari '{alias.canonical_name}' dan "
                "jadikan character mandiri lagi?\n\n"
                "Source dan recording tetap tidak berubah. Status stem/delivery pada "
                "episode terdampak akan direset."
            ),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._alias_service.restore_alias(alias.id)
        except Exception as exc:
            QMessageBox.critical(self, "Character Alias", str(exc))
            return

        self.reload()
        self.tabs.setCurrentIndex(self.TAB_INDEX["characters"])
        self._restore_character_selection(alias.source_character_id)
        self._character_selection_changed()

    def run_validation(self) -> list[ValidationIssue]:
        return super().run_validation()
