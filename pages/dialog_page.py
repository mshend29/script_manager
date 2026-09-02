from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.database import Database
from services.recording_service import RecordingDialogueRow, RecordingService
from widgets.context_panel import ContextPanel
from widgets.page_shell import PageShell


class DialogPage(PageShell):
    def __init__(self, parent=None):
        self._database: Database | None = None
        self._service: RecordingService | None = None
        self._loading_controls = False
        self._updating_checks = False
        self._source_file_path = ""
        self._checkboxes: dict[int, QCheckBox] = {}
        self._dialogue_items: dict[int, QTableWidgetItem] = {}
        self._dialogue_rows: list[RecordingDialogueRow] = []

        context = ContextPanel("DIALOG")

        context.add_widget(QLabel("Talent"))
        self.talent_combo = QComboBox()
        self.talent_combo.addItem("Pilih talent", None)
        context.add_widget(self.talent_combo)

        context.add_widget(QLabel("Tokoh"))
        self.character_combo = QComboBox()
        self.character_combo.addItem("Pilih tokoh", None)
        self.character_combo.setEnabled(False)
        context.add_widget(self.character_combo)

        context.add_widget(QLabel("Episode"))
        self.episode_combo = QComboBox()
        self.episode_combo.addItem("Pilih episode", None)
        self.episode_combo.setEnabled(False)
        context.add_widget(self.episode_combo)

        episode_nav = QWidget()
        episode_nav_layout = QHBoxLayout(episode_nav)
        episode_nav_layout.setContentsMargins(0, 0, 0, 0)
        episode_nav_layout.setSpacing(6)
        self.prev_episode_button = QPushButton("‹ Prev")
        self.prev_episode_button.setProperty("secondary", True)
        self.next_episode_button = QPushButton("Next ›")
        self.next_episode_button.setProperty("secondary", True)
        episode_nav_layout.addWidget(self.prev_episode_button)
        episode_nav_layout.addWidget(self.next_episode_button)
        context.add_widget(episode_nav)

        self.open_source_button = QPushButton("Open Source File")
        self.open_source_button.setProperty("secondary", True)
        self.open_source_button.setEnabled(False)
        context.add_widget(self.open_source_button)

        context.add_section_title("CAST EPISODE")
        self.cast_table = QTableWidget(0, 2)
        self.cast_table.setHorizontalHeaderLabels(["TOKOH", "TALENT"])
        self.cast_table.setMinimumHeight(190)
        self.cast_table.setAlternatingRowColors(True)
        self.cast_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cast_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.cast_table.verticalHeader().setVisible(False)
        cast_header = self.cast_table.horizontalHeader()
        cast_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        cast_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        context.add_widget(self.cast_table)
        context.add_stretch()

        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel("Dialog")
        title.setObjectName("PageTitle")

        self.selection_info = QLabel(
            "Pilih talent, tokoh, dan episode untuk menampilkan dialog."
        )
        self.selection_info.setObjectName("PageSubtitle")

        self.copy_all_button = QPushButton("Copy All Dialog")
        self.copy_all_button.setProperty("secondary", True)
        self.copy_all_button.setEnabled(False)
        self.copy_all_button.setToolTip(
            "Salin seluruh dialog yang sedang tampil, satu dialog per baris."
        )

        layout.addWidget(title)
        info_row = QHBoxLayout()
        info_row.setSpacing(8)
        info_row.addWidget(self.selection_info, 1)
        info_row.addWidget(self.copy_all_button)
        layout.addLayout(info_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["✓", "IN", "OUT", "DIALOG"])
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.table.setColumnWidth(0, 48)
        self.table.setColumnWidth(1, 115)
        self.table.setColumnWidth(2, 115)
        layout.addWidget(self.table, 1)

        super().__init__(context, workspace, parent)

        self.talent_combo.currentIndexChanged.connect(self._talent_changed)
        self.character_combo.currentIndexChanged.connect(self._character_changed)
        self.episode_combo.currentIndexChanged.connect(self._episode_changed)
        self.prev_episode_button.clicked.connect(
            lambda: self._select_adjacent_episode(-1)
        )
        self.next_episode_button.clicked.connect(
            lambda: self._select_adjacent_episode(1)
        )
        self.open_source_button.clicked.connect(self._open_source_file)
        self.copy_all_button.clicked.connect(self._copy_all_dialogues_clicked)
        self._update_episode_navigation()

    # ------------------------------------------------------------------
    # PROJECT / DATABASE BINDING
    # ------------------------------------------------------------------

    def set_database(self, database: Database | None) -> None:
        selected_talent = self.talent_combo.currentData()
        selected_character = self.character_combo.currentData()
        selected_episode = self.episode_combo.currentData()

        self._database = database
        self._service = RecordingService(database) if database is not None else None

        if self._service is None:
            self.clear_data()
            return

        self.reload(
            preferred_talent_id=selected_talent,
            preferred_character_id=selected_character,
            preferred_episode=selected_episode,
        )

    def clear_data(self) -> None:
        self._service = None
        self._database = None
        self._source_file_path = ""
        self._checkboxes.clear()
        self._dialogue_items.clear()
        self._dialogue_rows = []

        self._loading_controls = True
        try:
            self.talent_combo.clear()
            self.talent_combo.addItem("Pilih talent", None)
            self.character_combo.clear()
            self.character_combo.addItem("Pilih tokoh", None)
            self.character_combo.setEnabled(False)
            self.episode_combo.clear()
            self.episode_combo.addItem("Pilih episode", None)
            self.episode_combo.setEnabled(False)
        finally:
            self._loading_controls = False

        self._update_episode_navigation()
        self.open_source_button.setEnabled(False)
        self.copy_all_button.setEnabled(False)
        self.cast_table.setRowCount(0)
        self.table.setRowCount(0)
        self.selection_info.setText("No project open")

    def reload(
        self,
        *,
        preferred_talent_id: int | None = None,
        preferred_character_id: int | None = None,
        preferred_episode: int | None = None,
    ) -> None:
        if self._service is None:
            self.clear_data()
            return

        try:
            talents = self._service.get_talents()
        except Exception as exc:
            self._show_load_error("Gagal membaca daftar talent", exc)
            return

        self._loading_controls = True
        try:
            self.talent_combo.clear()
            self.talent_combo.addItem("Pilih talent", None)
            for talent in talents:
                self.talent_combo.addItem(talent.name, talent.id)

            talent_index = self.talent_combo.findData(preferred_talent_id)
            self.talent_combo.setCurrentIndex(
                talent_index if talent_index >= 0 else 0
            )
        finally:
            self._loading_controls = False

        selected_talent = self.talent_combo.currentData()
        if selected_talent is None:
            self._reset_character_selection()
            self.selection_info.setText(
                "Pilih talent, tokoh, dan episode untuk menampilkan dialog."
            )
            return

        self._load_characters(
            int(selected_talent),
            preferred_character_id=preferred_character_id,
            preferred_episode=preferred_episode,
        )

    # ------------------------------------------------------------------
    # TALENT / CHARACTER / EPISODE SELECTION
    # ------------------------------------------------------------------

    def _talent_changed(self) -> None:
        if self._loading_controls:
            return

        talent_id = self.talent_combo.currentData()
        if talent_id is None:
            self._reset_character_selection()
            self.selection_info.setText(
                "Pilih talent, tokoh, dan episode untuk menampilkan dialog."
            )
            return

        self._load_characters(int(talent_id))

    def _load_characters(
        self,
        talent_id: int,
        *,
        preferred_character_id: int | None = None,
        preferred_episode: int | None = None,
    ) -> None:
        if self._service is None:
            return

        try:
            characters = self._service.get_characters_for_talent(talent_id)
        except Exception as exc:
            self._show_load_error("Gagal membaca daftar tokoh", exc)
            return

        self._loading_controls = True
        try:
            self.character_combo.clear()
            self.character_combo.addItem("Pilih tokoh", None)
            for character in characters:
                self.character_combo.addItem(character.name, character.id)
            self.character_combo.setEnabled(bool(characters))

            character_index = self.character_combo.findData(
                preferred_character_id
            )
            self.character_combo.setCurrentIndex(
                character_index if character_index >= 0 else 0
            )
        finally:
            self._loading_controls = False

        selected_character = self.character_combo.currentData()
        if selected_character is None:
            self._reset_episode_selection()
            self.selection_info.setText("Pilih tokoh untuk melanjutkan.")
            return

        self._load_episodes(
            talent_id,
            int(selected_character),
            preferred_episode=preferred_episode,
        )

    def _character_changed(self) -> None:
        if self._loading_controls:
            return

        talent_id = self.talent_combo.currentData()
        character_id = self.character_combo.currentData()

        if talent_id is None or character_id is None:
            self._reset_episode_selection()
            self.selection_info.setText("Pilih talent dan tokoh untuk melanjutkan.")
            return

        self._load_episodes(int(talent_id), int(character_id))

    def _load_episodes(
        self,
        talent_id: int,
        character_id: int,
        *,
        preferred_episode: int | None = None,
    ) -> None:
        if self._service is None:
            return

        try:
            episodes = self._service.get_episodes_for_cast(
                talent_id=talent_id,
                character_id=character_id,
            )
        except Exception as exc:
            self._show_load_error("Gagal membaca daftar episode", exc)
            return

        self._loading_controls = True
        try:
            self.episode_combo.clear()
            self.episode_combo.addItem("Pilih episode", None)
            for episode in episodes:
                number = episode.episode_number
                self.episode_combo.addItem(f"Episode {number}", number)
            self.episode_combo.setEnabled(bool(episodes))

            episode_index = self.episode_combo.findData(preferred_episode)
            self.episode_combo.setCurrentIndex(
                episode_index if episode_index >= 0 else 0
            )
        finally:
            self._loading_controls = False
            self._update_episode_navigation()

        self._clear_episode_content()

        if not episodes:
            self.selection_info.setText(
                "Kombinasi talent dan tokoh ini belum memiliki episode aktif."
            )
            return

        if self.episode_combo.currentData() is not None:
            self._load_selected_episode()
        else:
            self.selection_info.setText("Pilih episode untuk menampilkan dialog.")

    def _episode_changed(self) -> None:
        if self._loading_controls:
            return
        self._update_episode_navigation()
        self._load_selected_episode()

    def _select_adjacent_episode(self, offset: int) -> None:
        if self.episode_combo.count() <= 1:
            return

        current = self.episode_combo.currentIndex()
        if current <= 0:
            target = 1
        else:
            target = current + offset

        target = min(max(target, 1), self.episode_combo.count() - 1)
        if target != current:
            self.episode_combo.setCurrentIndex(target)

    def _update_episode_navigation(self) -> None:
        count = self.episode_combo.count()
        current = self.episode_combo.currentIndex()
        has_episodes = count > 1
        self.prev_episode_button.setEnabled(has_episodes and current > 1)
        self.next_episode_button.setEnabled(
            has_episodes and current < count - 1
        )

    def _load_selected_episode(self) -> None:
        talent_id = self.talent_combo.currentData()
        character_id = self.character_combo.currentData()
        episode_number = self.episode_combo.currentData()

        self._clear_episode_content()

        if (
            self._service is None
            or talent_id is None
            or character_id is None
            or episode_number is None
        ):
            self.selection_info.setText(
                "Pilih talent, tokoh, dan episode untuk menampilkan dialog."
            )
            return

        try:
            cast = self._service.get_episode_cast(int(episode_number))
            rows = self._service.get_dialogues(
                talent_id=int(talent_id),
                character_id=int(character_id),
                episode_number=int(episode_number),
            )
            self._source_file_path = self._service.get_source_file_path(
                int(episode_number)
            )
        except Exception as exc:
            self._show_load_error("Gagal membaca data dialog", exc)
            return

        self._populate_cast(cast)
        self._populate_dialogues(rows)

        self.open_source_button.setEnabled(bool(self._source_file_path))
        self._update_selection_info()

    def _reset_character_selection(self) -> None:
        self._loading_controls = True
        try:
            self.character_combo.clear()
            self.character_combo.addItem("Pilih tokoh", None)
            self.character_combo.setEnabled(False)
        finally:
            self._loading_controls = False
        self._reset_episode_selection()

    def _reset_episode_selection(self) -> None:
        self._loading_controls = True
        try:
            self.episode_combo.clear()
            self.episode_combo.addItem("Pilih episode", None)
            self.episode_combo.setEnabled(False)
        finally:
            self._loading_controls = False

        self._update_episode_navigation()
        self._clear_episode_content()

    def _clear_episode_content(self) -> None:
        self._source_file_path = ""
        self.open_source_button.setEnabled(False)
        self.copy_all_button.setEnabled(False)
        self.copy_all_button.setText("Copy All Dialog")
        self.cast_table.setRowCount(0)
        self._checkboxes.clear()
        self._dialogue_items.clear()
        self._dialogue_rows = []

        self._updating_checks = True
        try:
            self.table.setRowCount(0)
        finally:
            self._updating_checks = False

    # ------------------------------------------------------------------
    # CAST / TABLE / RECORDING STATUS
    # ------------------------------------------------------------------

    def _populate_cast(self, cast) -> None:
        self.cast_table.setUpdatesEnabled(False)
        try:
            self.cast_table.clearContents()
            self.cast_table.setRowCount(len(cast))
            for row_index, member in enumerate(cast):
                character_item = QTableWidgetItem(member.character_name)
                talent_text = (
                    member.talent_name
                    if member.is_resolved
                    else "⚠ Unresolved"
                )
                talent_item = QTableWidgetItem(talent_text)
                self.cast_table.setItem(row_index, 0, character_item)
                self.cast_table.setItem(row_index, 1, talent_item)
        finally:
            self.cast_table.setUpdatesEnabled(True)

    def _populate_dialogues(self, rows: list[RecordingDialogueRow]) -> None:
        self._updating_checks = True
        self.table.setUpdatesEnabled(False)
        self._checkboxes.clear()
        self._dialogue_items.clear()
        self._dialogue_rows = list(rows)
        self.copy_all_button.setEnabled(bool(rows))
        self.copy_all_button.setText("Copy All Dialog")

        try:
            self.table.clearContents()
            self.table.setRowCount(len(rows))

            for row_index, row in enumerate(rows):
                checkbox = QCheckBox()
                checkbox.setChecked(row.is_recorded)
                checkbox.setProperty("dialogue_id", row.dialogue_id)
                checkbox.setProperty("source_revised", row.source_revised)
                if row.source_revised:
                    checkbox.setToolTip(
                        "Source berubah sejak dialog ini terakhir direkam. "
                        "Rekam ulang lalu update checkbox untuk menerima source terbaru."
                    )
                checkbox.stateChanged.connect(
                    lambda state, dialogue_id=row.dialogue_id:
                        self._recording_checkbox_changed(dialogue_id, state)
                )

                holder = QWidget()
                holder_layout = QHBoxLayout(holder)
                holder_layout.setContentsMargins(0, 0, 0, 0)
                holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                holder_layout.addWidget(checkbox)

                self._checkboxes[row.dialogue_id] = checkbox

                in_item = QTableWidgetItem(row.time_in)
                out_item = QTableWidgetItem(row.time_out)
                dialogue_text = self._single_line_dialogue(row.dialogue)
                dialogue_item = QTableWidgetItem(
                    (
                        f"⚠ Source Revised · {dialogue_text}"
                        if row.source_revised
                        else dialogue_text
                    )
                )
                dialogue_item.setToolTip(
                    (
                        "Source berubah sejak dialog terakhir direkam. "
                        "Recording history tetap dipertahankan.\n\n"
                        + row.dialogue
                    )
                    if row.source_revised
                    else row.dialogue
                )
                self._dialogue_items[row.dialogue_id] = dialogue_item

                self.table.setCellWidget(row_index, 0, holder)
                self.table.setItem(row_index, 1, in_item)
                self.table.setItem(row_index, 2, out_item)
                self.table.setItem(row_index, 3, dialogue_item)
        finally:
            self.table.setUpdatesEnabled(True)
            self._updating_checks = False

    @staticmethod
    def _single_line_dialogue(value: str) -> str:
        return " ".join(str(value or "").splitlines()).strip()

    def copy_all_dialogues(self) -> int:
        lines = [
            self._single_line_dialogue(row.dialogue)
            for row in self._dialogue_rows
        ]
        lines = [line for line in lines if line]
        if not lines:
            return 0

        QApplication.clipboard().setText("\n".join(lines))
        return len(lines)

    def _copy_all_dialogues_clicked(self) -> None:
        count = self.copy_all_dialogues()
        if count <= 0:
            return

        self.copy_all_button.setText(f"Copied {count} Dialog")
        QTimer.singleShot(
            1500,
            lambda: self.copy_all_button.setText("Copy All Dialog"),
        )

    def _recording_checkbox_changed(self, dialogue_id: int, state: int) -> None:
        if self._updating_checks or self._service is None:
            return

        recorded = state == int(Qt.CheckState.Checked.value)
        checkbox = self._checkboxes.get(int(dialogue_id))

        try:
            self._service.set_recorded(int(dialogue_id), recorded)
        except Exception as exc:
            if checkbox is not None:
                checkbox.blockSignals(True)
                try:
                    checkbox.setChecked(not recorded)
                finally:
                    checkbox.blockSignals(False)

            QMessageBox.warning(
                self,
                "Recording Status",
                f"Gagal menyimpan status recording.\n\n{exc}",
            )
            return

        self._clear_source_revision_marker(int(dialogue_id))
        self._update_selection_info()

    def set_all_checked(self, checked: bool) -> None:
        if self._service is None or not self._checkboxes:
            return

        dialogue_ids = sorted(self._checkboxes)

        try:
            self._service.set_recorded_bulk(dialogue_ids, checked)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Recording Status",
                f"Gagal menyimpan status recording.\n\n{exc}",
            )
            return

        self._updating_checks = True
        try:
            for checkbox in self._checkboxes.values():
                checkbox.blockSignals(True)
                try:
                    checkbox.setChecked(checked)
                    checkbox.setProperty("source_revised", False)
                    checkbox.setToolTip("")
                finally:
                    checkbox.blockSignals(False)
        finally:
            self._updating_checks = False

        for dialogue_id in dialogue_ids:
            self._clear_source_revision_marker(dialogue_id)

        self._update_selection_info()

    def _update_selection_info(self) -> None:
        talent_name = self.talent_combo.currentText()
        character_name = self.character_combo.currentText()
        episode_number = self.episode_combo.currentData()

        if episode_number is None:
            return

        total = len(self._checkboxes)
        recorded = sum(
            1 for checkbox in self._checkboxes.values()
            if checkbox.isChecked()
        )

        revised = sum(
            1
            for checkbox in self._checkboxes.values()
            if bool(checkbox.property("source_revised"))
        )
        revision_text = (
            f" • ⚠ {revised} source revised"
            if revised
            else ""
        )

        self.selection_info.setText(
            f"{talent_name} • {character_name} • Episode {episode_number} • "
            f"{recorded}/{total} recorded{revision_text}"
        )

    def _clear_source_revision_marker(self, dialogue_id: int) -> None:
        checkbox = self._checkboxes.get(int(dialogue_id))
        if checkbox is not None:
            checkbox.setProperty("source_revised", False)
            checkbox.setToolTip("")

        item = self._dialogue_items.get(int(dialogue_id))
        if item is None:
            return

        row = next(
            (
                value
                for value in self._dialogue_rows
                if value.dialogue_id == int(dialogue_id)
            ),
            None,
        )
        if row is None:
            return

        item.setText(self._single_line_dialogue(row.dialogue))
        item.setToolTip(row.dialogue)

    # ------------------------------------------------------------------
    # SOURCE FILE
    # ------------------------------------------------------------------

    def _open_source_file(self) -> None:
        if not self._source_file_path:
            return

        path = Path(self._source_file_path)

        if not path.is_file():
            QMessageBox.warning(
                self,
                "Open Source File",
                f"Source file tidak ditemukan.\n\n{path}",
            )
            return

        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.warning(
                self,
                "Open Source File",
                f"Source file tidak dapat dibuka.\n\n{path}",
            )

    # ------------------------------------------------------------------
    # ERROR
    # ------------------------------------------------------------------

    def _show_load_error(self, title: str, exc: Exception) -> None:
        self._clear_episode_content()
        self.selection_info.setText(f"{title}: {exc}")
