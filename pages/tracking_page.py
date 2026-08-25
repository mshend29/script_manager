from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.database import Database
from dialogs.tracking_episode_dialog import TrackingEpisodeDialog
from services.tracking_service import (
    DELIVERED,
    IN_PROGRESS,
    NOT_STARTED,
    READY_TO_STEM,
    RECORDED,
    REVISION,
    STATUS_LABELS,
    STEMMED,
    TrackingCharacterRow,
    TrackingChip,
    TrackingService,
)
from widgets.context_panel import ContextPanel
from widgets.episode_chip import EpisodeChipButton, status_palette
from widgets.page_shell import PageShell


STATUS_ORDER = (
    NOT_STARTED,
    IN_PROGRESS,
    RECORDED,
    READY_TO_STEM,
    STEMMED,
    DELIVERED,
    REVISION,
)


class TrackingPage(PageShell):
    def __init__(self, parent=None):
        self._database: Database | None = None
        self._service: TrackingService | None = None
        self._loading = False

        context = ContextPanel("TRACKING")

        self.drive_button = QPushButton("Open Client Drive")
        self.drive_button.setProperty("primary", True)
        context.add_widget(self.drive_button)

        context.add_section_title("TALENT")
        self.talent_combo = QComboBox()
        self.talent_combo.addItem("Pilih talent", None)
        context.add_widget(self.talent_combo)

        context.add_section_title("STATUS")
        for status in STATUS_ORDER:
            context.add_widget(self._status_legend_label(status))

        context.add_section_title("EPISODE")
        self.episode_combo = QComboBox()
        self.episode_combo.addItem("Pilih episode", None)
        context.add_widget(self.episode_combo)

        context.add_section_title("CHARACTER TO STEM")
        self.character_table = QTableWidget(0, 2)
        self.character_table.setHorizontalHeaderLabels(["TOKOH", "STATUS"])
        self.character_table.setMinimumHeight(180)
        self.character_table.setAlternatingRowColors(True)
        self.character_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.character_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.character_table.verticalHeader().setVisible(False)
        character_header = self.character_table.horizontalHeader()
        character_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        character_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        context.add_widget(self.character_table)
        context.add_stretch()

        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)

        title = QLabel("Tracking")
        title.setObjectName("PageTitle")
        self.summary_label = QLabel("No project open")
        self.summary_label.setObjectName("MutedLabel")

        layout.addWidget(title)
        layout.addWidget(self.summary_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.rows_container = QWidget()
        self.rows_layout = QGridLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setHorizontalSpacing(12)
        self.rows_layout.setVerticalSpacing(6)
        self.rows_layout.setColumnStretch(1, 1)
        self._reset_tracking_grid()

        self.scroll.setWidget(self.rows_container)
        layout.addWidget(self.scroll, 1)

        super().__init__(context, workspace, parent)

        self.talent_combo.currentIndexChanged.connect(self._talent_changed)
        self.episode_combo.currentIndexChanged.connect(self._episode_changed)

    @staticmethod
    def _status_legend_label(status: str) -> QLabel:
        background, foreground, border = status_palette(status)
        label = QLabel(f"■  {STATUS_LABELS[status]}")
        label.setStyleSheet(
            f"background: {background}; color: {foreground}; "
            f"border: 1px solid {border}; border-radius: 5px; "
            "padding: 4px 6px; font-weight: 600;"
        )
        return label

    # ------------------------------------------------------------------
    # PROJECT / DATABASE BINDING
    # ------------------------------------------------------------------

    def set_database(self, database: Database | None) -> None:
        current_talent = self.talent_combo.currentData()
        current_episode = self.episode_combo.currentData()

        self._database = database
        self._service = TrackingService(database) if database is not None else None

        if self._service is None:
            self.clear_data()
            return

        self.reload(
            preferred_talent=current_talent,
            preferred_episode=current_episode,
        )

    def clear_data(self) -> None:
        self._service = None
        self._database = None
        self._loading = True
        try:
            self.talent_combo.clear()
            self.talent_combo.addItem("Pilih talent", None)
            self.episode_combo.clear()
            self.episode_combo.addItem("Pilih episode", None)
        finally:
            self._loading = False

        self.character_table.setRowCount(0)
        self._reset_tracking_grid()
        self._show_empty_state("No project open")
        self.summary_label.setText("No project open")

    def reload(
        self,
        *,
        preferred_talent: int | None = None,
        preferred_episode: int | None = None,
    ) -> None:
        if self._service is None:
            self.clear_data()
            return

        try:
            talents = self._service.get_talents()
        except Exception as exc:
            self._show_error(f"Failed to load Tracking talents: {exc}")
            return

        self._loading = True
        try:
            self.talent_combo.clear()
            self.talent_combo.addItem("Pilih talent", None)
            for talent in talents:
                self.talent_combo.addItem(talent.label, talent.id)

            index = self.talent_combo.findData(preferred_talent)
            if index < 0 and len(talents) == 1:
                index = 1
            self.talent_combo.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self._loading = False

        self._reload_episodes(preferred_episode=preferred_episode)
        self._refresh_workspace()
        self._refresh_character_queue()

    # ------------------------------------------------------------------
    # FILTER CHANGES
    # ------------------------------------------------------------------

    def _talent_changed(self) -> None:
        if self._loading:
            return

        self._reload_episodes()
        self._refresh_workspace()
        self._refresh_character_queue()

    def _episode_changed(self) -> None:
        if self._loading:
            return
        self._refresh_character_queue()

    def _reload_episodes(self, *, preferred_episode: int | None = None) -> None:
        talent_id = self.talent_combo.currentData()

        self._loading = True
        try:
            self.episode_combo.clear()
            self.episode_combo.addItem("Pilih episode", None)

            if self._service is None or talent_id is None:
                return

            episodes = self._service.get_episodes_for_talent(int(talent_id))
            for episode in episodes:
                self.episode_combo.addItem(f"Episode {episode}", episode)

            index = self.episode_combo.findData(preferred_episode)
            self.episode_combo.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self._loading = False

    # ------------------------------------------------------------------
    # WORKSPACE
    # ------------------------------------------------------------------

    def _reset_tracking_grid(self) -> None:
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        character_header = QLabel("TOKOH")
        character_header.setObjectName("SectionTitle")
        episode_header = QLabel("EPISODE")
        episode_header.setObjectName("SectionTitle")
        self.rows_layout.addWidget(character_header, 0, 0)
        self.rows_layout.addWidget(episode_header, 0, 1)

    def _refresh_workspace(self) -> None:
        self._reset_tracking_grid()

        if self._service is None:
            self._show_empty_state("No project open")
            self.summary_label.setText("No project open")
            return

        talent_id = self.talent_combo.currentData()
        talent_name = self.talent_combo.currentText().strip()

        if talent_id is None:
            self._show_empty_state("Pilih talent untuk melihat tracking episode.")
            self.summary_label.setText("Belum ada talent dipilih")
            return

        try:
            rows = self._service.get_character_rows(int(talent_id))
        except Exception as exc:
            self._show_error(f"Failed to load Tracking data: {exc}")
            return

        if not rows:
            self._show_empty_state("Talent ini belum memiliki dialog aktif.")
            self.summary_label.setText(f"Talent: {talent_name}")
            return

        self.summary_label.setText(f"Talent: {talent_name}")
        max_chips = max((len(row.chips) for row in rows), default=1)
        self.rows_container.setMinimumWidth(250 + max_chips * 80)

        for row_number, row in enumerate(rows, start=1):
            self._add_character_row(row_number, row)

    def _add_character_row(
        self,
        row_number: int,
        row: TrackingCharacterRow,
    ) -> None:
        character = QLabel(row.character_name)
        character.setMinimumWidth(210)
        character.setMaximumWidth(240)
        character.setMinimumHeight(40)
        character.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        character.setStyleSheet(
            "background: #ffffff; border-bottom: 1px solid #ececec; "
            "padding: 4px 8px; font-weight: 600;"
        )

        episode_holder = QWidget()
        episode_layout = QHBoxLayout(episode_holder)
        episode_layout.setContentsMargins(0, 1, 0, 1)
        episode_layout.setSpacing(6)

        for chip in row.chips:
            button = EpisodeChipButton(chip)
            button.detail_requested.connect(self._open_episode_detail)
            episode_layout.addWidget(button)

        episode_layout.addStretch(1)

        self.rows_layout.addWidget(character, row_number, 0)
        self.rows_layout.addWidget(episode_holder, row_number, 1)

    def _show_empty_state(self, text: str) -> None:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("padding: 18px; color: #6b7075;")
        self.rows_layout.addWidget(label, 1, 0, 1, 2)

    # ------------------------------------------------------------------
    # CHARACTER QUEUE
    # ------------------------------------------------------------------

    def _refresh_character_queue(self) -> None:
        self.character_table.clearContents()
        self.character_table.setRowCount(0)

        if self._service is None:
            return

        talent_id = self.talent_combo.currentData()
        episode_number = self.episode_combo.currentData()

        if talent_id is None or episode_number is None:
            return

        try:
            chips = self._service.get_characters_to_stem(
                int(talent_id),
                int(episode_number),
            )
        except Exception as exc:
            self._show_character_queue_error(str(exc))
            return

        self.character_table.setRowCount(len(chips))
        for row_index, chip in enumerate(chips):
            character_item = QTableWidgetItem(chip.character_name)
            status_item = QTableWidgetItem(chip.status_label)
            background, foreground, _ = status_palette(chip.display_status)
            status_item.setBackground(QColor(background))
            status_item.setForeground(QColor(foreground))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.character_table.setItem(row_index, 0, character_item)
            self.character_table.setItem(row_index, 1, status_item)

    def _show_character_queue_error(self, message: str) -> None:
        self.character_table.setRowCount(1)
        item = QTableWidgetItem(f"Error: {message}")
        self.character_table.setItem(0, 0, item)

    # ------------------------------------------------------------------
    # EPISODE DETAIL / DOWNSTREAM STATUS
    # ------------------------------------------------------------------

    def _open_episode_detail(self, chip: TrackingChip) -> None:
        dialog = TrackingEpisodeDialog(chip, self)
        if not dialog.exec():
            return

        self._change_status(
            episode_id=chip.episode_id,
            talent_id=chip.talent_id,
            character_id=chip.character_id,
            status=dialog.selected_status,
        )

    def _change_status(
        self,
        episode_id: int,
        talent_id: int,
        character_id: int,
        status: str,
    ) -> None:
        if self._service is None:
            return

        try:
            self._service.set_downstream_status(
                episode_id=episode_id,
                talent_id=talent_id,
                character_id=character_id,
                status=status,
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Tracking Status",
                str(exc),
            )
            return

        self._refresh_workspace()
        self._refresh_character_queue()

    def _show_error(self, message: str) -> None:
        self._reset_tracking_grid()
        self._show_empty_state(message)
        self.summary_label.setText(message)
