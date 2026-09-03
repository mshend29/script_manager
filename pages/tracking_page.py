from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QListView,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.database import Database
from services.tracking_service import (
    DELIVERED,
    IN_PROGRESS,
    NOT_STARTED,
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
from widgets.flow_layout import FlowLayout
from widgets.page_shell import PageShell


STATUS_ORDER = (
    NOT_STARTED,
    IN_PROGRESS,
    RECORDED,
    STEMMED,
    DELIVERED,
    REVISION,
)


class TrackingEpisodeComboBox(QComboBox):
    """Episode selector with a fully controlled compact popup."""

    MAX_VISIBLE_EPISODES = 8
    MAX_POPUP_HEIGHT = 250
    MIN_ROW_HEIGHT = 28
    MIN_POPUP_WIDTH = 150

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaxVisibleItems(self.MAX_VISIBLE_EPISODES)
        self._episode_popup: QFrame | None = None
        self._episode_popup_view: QListView | None = None

    def _ensure_popup(self) -> None:
        if self._episode_popup is not None:
            return

        popup = QFrame(
            None,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint,
        )
        popup.setObjectName("TrackingEpisodePopup")
        popup_layout = QVBoxLayout(popup)
        popup_layout.setContentsMargins(1, 1, 1, 1)
        popup_layout.setSpacing(0)

        view = QListView(popup)
        view.setObjectName("TrackingEpisodePopupList")
        view.setModel(self.model())
        view.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        view.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        view.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        view.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        view.setUniformItemSizes(True)
        view.clicked.connect(self._popup_index_clicked)
        view.activated.connect(self._popup_index_clicked)
        popup_layout.addWidget(view)

        self._episode_popup = popup
        self._episode_popup_view = view

    def showPopup(self) -> None:
        self._ensure_popup()
        popup = self._episode_popup
        view = self._episode_popup_view
        if popup is None or view is None:
            return

        # The combo's model can be cleared/repopulated when Talent changes.
        # Keep the popup view bound to the current model explicitly.
        if view.model() is not self.model():
            view.setModel(self.model())

        count = max(self.count(), 1)
        visible_rows = min(count, self.MAX_VISIBLE_EPISODES)
        row_height = max(
            view.sizeHintForRow(0),
            self.MIN_ROW_HEIGHT,
        )
        popup_height = min(
            row_height * visible_rows + 4,
            self.MAX_POPUP_HEIGHT,
        )

        screen = self.screen().availableGeometry()
        popup_width = min(
            max(self.width(), self.MIN_POPUP_WIDTH),
            max(self.MIN_POPUP_WIDTH, screen.width() - 8),
        )

        below = self.mapToGlobal(QPoint(0, self.height()))
        above_y = self.mapToGlobal(QPoint(0, 0)).y() - popup_height

        x = min(
            max(below.x(), screen.left() + 4),
            max(screen.left() + 4, screen.right() - popup_width + 1),
        )
        if below.y() + popup_height <= screen.bottom() + 1:
            y = below.y()
        else:
            y = max(screen.top() + 4, above_y)

        popup.setFixedSize(popup_width, popup_height)
        popup.move(x, y)

        current = self.currentIndex()
        if current >= 0:
            index = self.model().index(
                current,
                self.modelColumn(),
                self.rootModelIndex(),
            )
            view.setCurrentIndex(index)
            view.scrollTo(
                index,
                QAbstractItemView.ScrollHint.PositionAtCenter,
            )

        popup.show()
        popup.raise()
        view.setFocus(Qt.FocusReason.PopupFocusReason)

    def hidePopup(self) -> None:
        if self._episode_popup is not None:
            self._episode_popup.hide()

    def _popup_index_clicked(self, index) -> None:
        row = index.row()
        if 0 <= row < self.count():
            self.setCurrentIndex(row)
        self.hidePopup()


class TrackingPage(PageShell):
    tracking_detail_changed = Signal(object)
    data_changed = Signal()

    def __init__(self, parent=None):
        self._database: Database | None = None
        self._service: TrackingService | None = None
        self._loading = False
        self._workspace_rows: list[TrackingCharacterRow] = []
        self._selected_chip_key: tuple[int, int, int] | None = None

        context = ContextPanel("TRACKING")

        self.drive_button = QPushButton("Open Client Drive")
        self.drive_button.setProperty("primary", True)
        context.add_widget(self.drive_button)

        context.add_section_title("TALENT")
        self.talent_combo = QComboBox()
        self.talent_combo.setObjectName("TrackingTalentFilter")
        self.talent_combo.addItem("Pilih talent", None)
        self.talent_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.talent_combo.setMinimumContentsLength(12)
        context.add_widget(self.talent_combo)

        context.add_section_title("STATUS")
        for status in STATUS_ORDER:
            context.add_widget(self._status_legend_label(status))

        context.add_section_title("EPISODE")
        self.episode_combo = TrackingEpisodeComboBox()
        self.episode_combo.setObjectName("TrackingEpisodeFilter")
        self.episode_combo.addItem("Pilih episode", None)
        self.episode_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.episode_combo.setMinimumContentsLength(12)
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

        context.add_section_title("CHARACTER TO STEM")
        self.character_table = QTableWidget(0, 2)
        self.character_table.setObjectName("TrackingCharacterQueue")
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

        self.title_label = QLabel("Tracking")
        self.title_label.setObjectName("PageTitle")
        self.summary_label = QLabel("No project open")
        self.summary_label.setObjectName("TrackingSummary")
        self.summary_label.setContentsMargins(8, 0, 5, 0)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)
        header_row.addWidget(self.title_label)
        header_row.addWidget(self.summary_label, 1)
        layout.addLayout(header_row)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("TrackingScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.grid_header = QFrame()
        self.grid_header.setObjectName("TrackingGridHeader")
        grid_header_layout = QGridLayout(self.grid_header)
        grid_header_layout.setContentsMargins(0, 0, 0, 0)
        grid_header_layout.setHorizontalSpacing(12)
        grid_header_layout.setVerticalSpacing(0)
        grid_header_layout.setColumnStretch(1, 1)

        self.character_header_label = QLabel("TOKOH")
        self.character_header_label.setObjectName("SectionTitle")
        self.character_header_label.setMinimumWidth(190)
        self.character_header_label.setMaximumWidth(230)
        self.episode_header_label = QLabel("EPISODE")
        self.episode_header_label.setObjectName("SectionTitle")
        grid_header_layout.addWidget(self.character_header_label, 0, 0)
        grid_header_layout.addWidget(self.episode_header_label, 0, 1)
        layout.addWidget(self.grid_header)

        self.rows_container = QWidget()
        self.rows_container.setObjectName("TrackingRows")
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
        self.prev_episode_button.clicked.connect(
            lambda: self._select_adjacent_episode(-1)
        )
        self.next_episode_button.clicked.connect(
            lambda: self._select_adjacent_episode(1)
        )
        self._update_episode_navigation()

    @staticmethod
    def _status_legend_label(status: str) -> QLabel:
        background, foreground, border = status_palette(status)
        label = QLabel(f"■  {STATUS_LABELS[status]}")
        label.setObjectName("TrackingLegendChip")
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
        self._clear_tracking_detail()

        if self._service is None:
            self.clear_data()
            return

        self.reload(
            preferred_talent=current_talent,
            preferred_episode=current_episode,
        )

    def refresh_from_database(self, database: Database | None) -> None:
        current_talent = self.talent_combo.currentData()
        current_episode = self.episode_combo.currentData()

        if database is not self._database or self._service is None:
            self.set_database(database)
            return

        if database is None:
            self.clear_data()
            return

        self.reload(
            preferred_talent=current_talent,
            preferred_episode=current_episode,
        )

    def clear_data(self) -> None:
        self._service = None
        self._database = None
        self._workspace_rows = []
        self._clear_tracking_detail()
        self._loading = True
        try:
            self.talent_combo.clear()
            self.talent_combo.addItem("Pilih talent", None)
            self.episode_combo.clear()
            self.episode_combo.addItem("Pilih episode", None)
        finally:
            self._loading = False

        self._update_episode_navigation()
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
    # FILTER CHANGES / EPISODE NAVIGATION
    # ------------------------------------------------------------------

    def _talent_changed(self) -> None:
        if self._loading:
            return

        self._clear_tracking_detail()
        self._reload_episodes()
        self._refresh_workspace()
        self._refresh_character_queue()

    def _episode_changed(self) -> None:
        if self._loading:
            return
        self._update_episode_navigation()
        self._refresh_character_queue()

    def _reload_episodes(self, *, preferred_episode: int | None = None) -> None:
        talent_id = self.talent_combo.currentData()
        episodes: list[int] = []

        self._loading = True
        try:
            self.episode_combo.clear()
            self.episode_combo.addItem("Pilih episode", None)

            if self._service is None or talent_id is None:
                return

            # TrackingService scopes this list to active dialogues belonging
            # to the selected talent only.
            episodes = self._service.get_episodes_for_talent(int(talent_id))
            for episode in episodes:
                self.episode_combo.addItem(f"Episode {episode}", episode)

            index = self.episode_combo.findData(preferred_episode)
            if index < 0 and episodes:
                index = 1
            self.episode_combo.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self._loading = False
            self._update_episode_navigation()

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
            has_episodes and 0 < current < count - 1
        )

    # ------------------------------------------------------------------
    # WORKSPACE
    # ------------------------------------------------------------------

    def _reset_tracking_grid(self) -> None:
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _refresh_workspace(self) -> None:
        self._reset_tracking_grid()
        self._workspace_rows = []

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

        self._workspace_rows = rows

        if not rows:
            self._show_empty_state("Talent ini belum memiliki dialog aktif.")
            self.summary_label.setText(f"Talent: {talent_name}")
            return

        self.summary_label.setText(f"Talent: {talent_name}")

        for row_number, row in enumerate(rows):
            self._add_character_row(row_number, row)

    def _add_character_row(
        self,
        row_number: int,
        row: TrackingCharacterRow,
    ) -> None:
        character = QLabel(row.character_name)
        character.setMinimumWidth(190)
        character.setMaximumWidth(230)
        character.setMinimumHeight(40)
        character.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        character.setObjectName("TrackingCharacterName")
        character.setWordWrap(True)
        character.setToolTip(row.character_name)

        episode_holder = QWidget()
        episode_holder.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        episode_layout = FlowLayout(episode_holder, margin=1, spacing=6)

        for chip in row.chips:
            button = EpisodeChipButton(chip)
            button.detail_requested.connect(self._select_episode_detail)
            episode_layout.addWidget(button)

        self.rows_layout.addWidget(character, row_number, 0)
        self.rows_layout.addWidget(episode_holder, row_number, 1)

    def _show_empty_state(self, text: str) -> None:
        label = QLabel(text)
        label.setObjectName("TrackingEmptyState")
        label.setWordWrap(True)
        self.rows_layout.addWidget(label, 0, 0, 1, 2)

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

    def _select_episode_detail(self, chip: TrackingChip) -> None:
        self._selected_chip_key = (
            chip.episode_id,
            chip.talent_id,
            chip.character_id,
        )
        self.tracking_detail_changed.emit(chip)

    def _clear_tracking_detail(self) -> None:
        self._selected_chip_key = None
        try:
            self.tracking_detail_changed.emit(None)
        except RuntimeError:
            # Can only happen during very early/late QObject lifecycle.
            pass

    def apply_selected_status(self, status: str) -> None:
        if self._service is None or self._selected_chip_key is None:
            return

        episode_id, talent_id, character_id = self._selected_chip_key
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
            self._refresh_selected_detail()
            return

        self._refresh_workspace()
        self._refresh_character_queue()
        self._refresh_selected_detail()
        self.data_changed.emit()

    def _refresh_selected_detail(self) -> None:
        if self._selected_chip_key is None:
            self.tracking_detail_changed.emit(None)
            return

        episode_id, talent_id, character_id = self._selected_chip_key
        for row in self._workspace_rows:
            for chip in row.chips:
                if (
                    chip.episode_id == episode_id
                    and chip.talent_id == talent_id
                    and chip.character_id == character_id
                ):
                    self.tracking_detail_changed.emit(chip)
                    return

        self._clear_tracking_detail()

    def _show_error(self, message: str) -> None:
        self._workspace_rows = []
        self._reset_tracking_grid()
        self._show_empty_state(message)
        self.summary_label.setText(message)
