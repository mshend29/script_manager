from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHeaderView,
    QLabel,
    QListWidget,
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

        context = ContextPanel("DIALOG")

        context.add_widget(QLabel("Tokoh"))
        self.character_combo = QComboBox()
        self.character_combo.addItem("Pilih tokoh", None)
        context.add_widget(self.character_combo)

        context.add_widget(QLabel("Episode"))
        self.episode_combo = QComboBox()
        self.episode_combo.addItem("Pilih episode", None)
        self.episode_combo.setEnabled(False)
        context.add_widget(self.episode_combo)

        self.open_source_button = QPushButton("Open Source File")
        self.open_source_button.setProperty("secondary", True)
        self.open_source_button.setEnabled(False)
        context.add_widget(self.open_source_button)

        context.add_section_title("CAST EPISODE")
        self.cast_list = QListWidget()
        self.cast_list.setMinimumHeight(190)
        context.add_widget(self.cast_list)
        context.add_stretch()

        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel("Dialog")
        title.setObjectName("PageTitle")

        self.selection_info = QLabel(
            "Pilih tokoh dan episode untuk menampilkan dialog."
        )
        self.selection_info.setObjectName("PageSubtitle")

        layout.addWidget(title)
        layout.addWidget(self.selection_info)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["✓", "IN", "OUT", "DIALOG"])
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.table.setColumnWidth(0, 42)
        self.table.setColumnWidth(1, 115)
        self.table.setColumnWidth(2, 115)
        layout.addWidget(self.table, 1)

        super().__init__(context, workspace, parent)

        self.character_combo.currentIndexChanged.connect(
            self._character_changed
        )
        self.episode_combo.currentIndexChanged.connect(
            self._episode_changed
        )
        self.open_source_button.clicked.connect(self._open_source_file)
        self.table.itemChanged.connect(self._recording_item_changed)

    # ------------------------------------------------------------------
    # PROJECT / DATABASE BINDING
    # ------------------------------------------------------------------

    def set_database(self, database: Database | None) -> None:
        selected_character = self.character_combo.currentData()
        selected_episode = self.episode_combo.currentData()

        self._database = database
        self._service = RecordingService(database) if database is not None else None

        if self._service is None:
            self.clear_data()
            return

        self.reload(
            preferred_character_id=selected_character,
            preferred_episode=selected_episode,
        )

    def clear_data(self) -> None:
        self._service = None
        self._database = None
        self._source_file_path = ""

        self._loading_controls = True
        try:
            self.character_combo.clear()
            self.character_combo.addItem("Pilih tokoh", None)
            self.episode_combo.clear()
            self.episode_combo.addItem("Pilih episode", None)
            self.episode_combo.setEnabled(False)
        finally:
            self._loading_controls = False

        self.open_source_button.setEnabled(False)
        self.cast_list.clear()
        self.table.setRowCount(0)
        self.selection_info.setText("No project open")

    def reload(
        self,
        *,
        preferred_character_id: int | None = None,
        preferred_episode: int | None = None,
    ) -> None:
        if self._service is None:
            self.clear_data()
            return

        try:
            characters = self._service.get_characters()
        except Exception as exc:
            self._show_load_error("Gagal membaca daftar tokoh", exc)
            return

        self._loading_controls = True
        try:
            self.character_combo.clear()
            self.character_combo.addItem("Pilih tokoh", None)

            for character in characters:
                self.character_combo.addItem(character.name, character.id)

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
            self.selection_info.setText(
                "Pilih tokoh dan episode untuk menampilkan dialog."
            )
            return

        self._load_episodes(
            int(selected_character),
            preferred_episode=preferred_episode,
        )

    # ------------------------------------------------------------------
    # CHARACTER / EPISODE SELECTION
    # ------------------------------------------------------------------

    def _character_changed(self) -> None:
        if self._loading_controls:
            return

        character_id = self.character_combo.currentData()

        if character_id is None:
            self._reset_episode_selection()
            self.selection_info.setText(
                "Pilih tokoh dan episode untuk menampilkan dialog."
            )
            return

        self._load_episodes(int(character_id))

    def _load_episodes(
        self,
        character_id: int,
        *,
        preferred_episode: int | None = None,
    ) -> None:
        if self._service is None:
            return

        try:
            episodes = self._service.get_episodes_for_character(character_id)
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

        self._clear_episode_content()

        if not episodes:
            self.selection_info.setText(
                f"{self.character_combo.currentText()} belum memiliki episode aktif."
            )
            return

        if self.episode_combo.currentData() is not None:
            self._load_selected_episode()
        else:
            self.selection_info.setText(
                "Pilih episode untuk menampilkan dialog."
            )

    def _episode_changed(self) -> None:
        if self._loading_controls:
            return

        self._load_selected_episode()

    def _load_selected_episode(self) -> None:
        character_id = self.character_combo.currentData()
        episode_number = self.episode_combo.currentData()

        self._clear_episode_content()

        if (
            self._service is None
            or character_id is None
            or episode_number is None
        ):
            self.selection_info.setText(
                "Pilih tokoh dan episode untuk menampilkan dialog."
            )
            return

        try:
            cast = self._service.get_episode_cast(int(episode_number))
            rows = self._service.get_dialogues(
                character_id=int(character_id),
                episode_number=int(episode_number),
            )
            self._source_file_path = self._service.get_source_file_path(
                int(episode_number)
            )
        except Exception as exc:
            self._show_load_error("Gagal membaca data dialog", exc)
            return

        for member in cast:
            if member.is_resolved:
                text = f"{member.character_name} — {member.talent_name}"
            else:
                text = f"⚠ {member.character_name} — Unresolved"
            self.cast_list.addItem(text)

        self._populate_dialogues(rows)

        self.open_source_button.setEnabled(
            bool(self._source_file_path)
        )
        self._update_selection_info()

    def _reset_episode_selection(self) -> None:
        self._loading_controls = True
        try:
            self.episode_combo.clear()
            self.episode_combo.addItem("Pilih episode", None)
            self.episode_combo.setEnabled(False)
        finally:
            self._loading_controls = False

        self._clear_episode_content()

    def _clear_episode_content(self) -> None:
        self._source_file_path = ""
        self.open_source_button.setEnabled(False)
        self.cast_list.clear()

        self._updating_checks = True
        try:
            self.table.setRowCount(0)
        finally:
            self._updating_checks = False

    # ------------------------------------------------------------------
    # TABLE / RECORDING STATUS
    # ------------------------------------------------------------------

    def _populate_dialogues(self, rows: list[RecordingDialogueRow]) -> None:
        self._updating_checks = True
        self.table.setUpdatesEnabled(False)

        try:
            self.table.clearContents()
            self.table.setRowCount(len(rows))

            for row_index, row in enumerate(rows):
                checkbox_item = QTableWidgetItem()
                checkbox_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                checkbox_item.setData(
                    Qt.ItemDataRole.UserRole,
                    row.dialogue_id,
                )
                checkbox_item.setCheckState(
                    Qt.CheckState.Checked
                    if row.is_recorded
                    else Qt.CheckState.Unchecked
                )

                in_item = QTableWidgetItem(row.time_in)
                out_item = QTableWidgetItem(row.time_out)
                dialogue_item = QTableWidgetItem(row.dialogue)

                self.table.setItem(row_index, 0, checkbox_item)
                self.table.setItem(row_index, 1, in_item)
                self.table.setItem(row_index, 2, out_item)
                self.table.setItem(row_index, 3, dialogue_item)
        finally:
            self.table.setUpdatesEnabled(True)
            self._updating_checks = False

    def _recording_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_checks or item.column() != 0:
            return

        if self._service is None:
            return

        dialogue_id = item.data(Qt.ItemDataRole.UserRole)
        if dialogue_id is None:
            return

        recorded = item.checkState() == Qt.CheckState.Checked

        try:
            self._service.set_recorded(int(dialogue_id), recorded)
        except Exception as exc:
            self._updating_checks = True
            try:
                item.setCheckState(
                    Qt.CheckState.Unchecked
                    if recorded
                    else Qt.CheckState.Checked
                )
            finally:
                self._updating_checks = False

            QMessageBox.warning(
                self,
                "Recording Status",
                f"Gagal menyimpan status recording.\n\n{exc}",
            )
            return

        self._update_selection_info()

    def set_all_checked(self, checked: bool) -> None:
        if self._service is None or self.table.rowCount() == 0:
            return

        dialogue_ids: list[int] = []

        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is None:
                continue

            dialogue_id = item.data(Qt.ItemDataRole.UserRole)
            if dialogue_id is not None:
                dialogue_ids.append(int(dialogue_id))

        if not dialogue_ids:
            return

        try:
            self._service.set_recorded_bulk(dialogue_ids, checked)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Recording Status",
                f"Gagal menyimpan status recording.\n\n{exc}",
            )
            return

        state = (
            Qt.CheckState.Checked
            if checked
            else Qt.CheckState.Unchecked
        )

        self._updating_checks = True
        try:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item is not None:
                    item.setCheckState(state)
        finally:
            self._updating_checks = False

        self._update_selection_info()

    def _update_selection_info(self) -> None:
        character_name = self.character_combo.currentText()
        episode_number = self.episode_combo.currentData()

        if episode_number is None:
            return

        total = self.table.rowCount()
        recorded = 0

        for row in range(total):
            item = self.table.item(row, 0)
            if (
                item is not None
                and item.checkState() == Qt.CheckState.Checked
            ):
                recorded += 1

        self.selection_info.setText(
            f"{character_name} • Episode {episode_number} • "
            f"{recorded}/{total} recorded"
        )

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
