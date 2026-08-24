from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.database import Database
from services.tracking_service import (
    STATUS_LABELS,
    TrackingCharacterRow,
    TrackingService,
)
from widgets.context_panel import ContextPanel
from widgets.episode_chip import EpisodeChipButton
from widgets.page_shell import PageShell


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
        for text in [
            "■ Not Started",
            "■ In Progress",
            "■ Recorded",
            "■ Ready to Stem",
            "■ Stemmed",
            "■ Delivered",
            "■ Revision",
        ]:
            context.add_widget(QLabel(text))

        context.add_section_title("EPISODE")
        self.episode_combo = QComboBox()
        self.episode_combo.addItem("Pilih episode", None)
        context.add_widget(self.episode_combo)

        context.add_section_title("CHARACTER TO STEM")
        self.character_list = QListWidget()
        self.character_list.setMinimumHeight(180)
        context.add_widget(self.character_list)
        context.add_stretch()

        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel("Tracking")
        title.setObjectName("PageTitle")

        subtitle = QLabel(
            "Recording status dihitung otomatis dari checkbox Dialog. "
            "Klik chip episode untuk mengubah status downstream."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)

        self.summary_label = QLabel("No project open")
        self.summary_label.setObjectName("MutedLabel")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.summary_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(10)
        self.rows_layout.addStretch(1)

        self.scroll.setWidget(self.rows_container)
        layout.addWidget(self.scroll, 1)

        super().__init__(context, workspace, parent)

        self.talent_combo.currentIndexChanged.connect(self._talent_changed)
        self.episode_combo.currentIndexChanged.connect(self._episode_changed)

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

        self.character_list.clear()
        self._clear_rows()
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

    def _refresh_workspace(self) -> None:
        self._clear_rows()

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
            self.summary_label.setText(f"{talent_name} • 0 character")
            return

        total_chips = sum(len(row.chips) for row in rows)
        self.summary_label.setText(
            f"{talent_name} • {len(rows)} character • {total_chips} episode assignment"
        )

        for row in rows:
            self.rows_layout.insertWidget(
                self.rows_layout.count() - 1,
                self._build_character_card(row),
            )

    def _build_character_card(self, row: TrackingCharacterRow) -> QFrame:
        card = QFrame()
        card.setObjectName("DashboardCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 14)
        card_layout.setSpacing(8)

        name = QLabel(row.character_name)
        name.setStyleSheet("font-size: 11pt; font-weight: 600;")
        card_layout.addWidget(name)

        grid_holder = QWidget()
        grid = QGridLayout(grid_holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        columns = 7
        for index, chip in enumerate(row.chips):
            button = EpisodeChipButton(chip)
            button.status_change_requested.connect(self._change_status)
            grid.addWidget(button, index // columns, index % columns)

        card_layout.addWidget(grid_holder)
        return card

    def _show_empty_state(self, text: str) -> None:
        card = QFrame()
        card.setObjectName("DashboardCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)

        label = QLabel(text)
        label.setWordWrap(True)
        card_layout.addWidget(label)

        self.rows_layout.insertWidget(self.rows_layout.count() - 1, card)

    def _clear_rows(self) -> None:
        while self.rows_layout.count() > 1:
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    # ------------------------------------------------------------------
    # CHARACTER QUEUE
    # ------------------------------------------------------------------

    def _refresh_character_queue(self) -> None:
        self.character_list.clear()

        if self._service is None:
            return

        talent_id = self.talent_combo.currentData()
        episode_number = self.episode_combo.currentData()

        if talent_id is None or episode_number is None:
            self.character_list.addItem("Pilih talent dan episode")
            return

        try:
            chips = self._service.get_characters_to_stem(
                int(talent_id),
                int(episode_number),
            )
        except Exception as exc:
            self.character_list.addItem(f"Error: {exc}")
            return

        if not chips:
            self.character_list.addItem("Tidak ada character yang perlu diproses")
            return

        for chip in chips:
            self.character_list.addItem(
                f"{chip.character_name} — {chip.status_label} ({chip.progress_text})"
            )

    # ------------------------------------------------------------------
    # DOWNSTREAM STATUS
    # ------------------------------------------------------------------

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
        self._clear_rows()
        self._show_empty_state(message)
        self.summary_label.setText(message)
