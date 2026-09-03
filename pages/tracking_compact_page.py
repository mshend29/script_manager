from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from app.theme import COLORS
from core.database import Database
from core.project_settings import ProjectSettings
from dialogs.track_rename_preview_dialog import TrackRenamePreviewDialog
from pages.tracking_page import STATUS_ORDER, TrackingPage
from services.track_file_service import (
    AudioFileCheck,
    TrackAudioSpec,
    TrackFileInventory,
    TrackFileRow,
    TrackFileService,
    TrackFileWarning,
    sanitize_filename_component,
)
from services.track_rename_service import (
    MATCH_SIMPLE_EXPORT,
    RENAME_AMBIGUOUS,
    RENAME_COLLISION,
    RENAME_MATCHED,
    RENAME_UNMATCHED,
    TrackRenameItem,
    TrackRenamePlan,
    TrackRenameService,
    parse_simple_export_filename,
)
from services.tracking_service import NOT_READY, REVISION, STATUS_LABELS
from services.tracking_summary_service import TrackingSummaryService
from widgets.episode_chip import open_dialog_scope, status_palette


WORKSPACE_TRACKING = "tracking"
WORKSPACE_TRACK_FILES = "track_files"
WORKSPACE_OUTPUT_HEALTH = "output_health"


class CompactTrackingPage(TrackingPage):
    """Tracking with dedicated Tracking, Track Files and Output Health workspaces."""

    def __init__(self, parent=None):
        self._summary_service: TrackingSummaryService | None = None
        self._track_file_service: TrackFileService | None = None
        self._track_rename_service: TrackRenameService | None = None
        self._track_file_inventory = TrackFileInventory()
        self._track_rename_plan = TrackRenamePlan()
        self._track_file_settings = ProjectSettings()
        self._workspace_key = WORKSPACE_TRACKING
        super().__init__(parent)

        self.summary_label.setContentsMargins(8, 2, 8, 2)
        self._compact_status_legend()
        self._add_output_health_sidebar()
        self._build_tracking_workspaces()
        self.tracking_detail_changed.connect(
            self._update_tracking_detail_bar
        )
        self.show_workspace(WORKSPACE_TRACKING)

    # ------------------------------------------------------------------
    # PROJECT / FILE INVENTORY
    # ------------------------------------------------------------------

    def configure_track_files(self, settings: ProjectSettings | None) -> None:
        self._track_file_settings = settings or ProjectSettings()

    def set_database(self, database: Database | None) -> None:
        self._summary_service = (
            TrackingSummaryService(database) if database is not None else None
        )
        self._track_file_service = (
            self._build_track_file_service(database)
            if database is not None
            else None
        )
        self._track_rename_service = (
            self._build_track_rename_service(database)
            if database is not None
            else None
        )
        self._track_file_inventory = self._scan_track_files()
        super().set_database(database)
        self._refresh_track_file_ui()

    def refresh_from_database(self, database: Database | None) -> None:
        if database is not self._database or self._service is None:
            self.set_database(database)
            return

        if database is None:
            self.clear_data()
            return

        # Tracking depends on both SQLite state and filesystem state. Unlike
        # the base page, refreshing this workspace must rescan Stem/Delivery
        # folders so Drive Desktop changes become visible immediately.
        self.refresh_track_files(notify=False)

    def refresh_track_files(
        self,
        checked: bool = False,
        *,
        notify: bool = True,
    ) -> None:
        if self._database is None:
            return

        current_talent = self.talent_combo.currentData()
        current_episode = self.episode_combo.currentData()
        self._track_file_service = self._build_track_file_service(self._database)
        self._track_rename_service = self._build_track_rename_service(
            self._database
        )
        self._track_file_inventory = self._scan_track_files()

        super().reload(
            preferred_talent=(
                int(current_talent) if current_talent is not None else None
            ),
            preferred_episode=(
                int(current_episode) if current_episode is not None else None
            ),
        )
        self._refresh_track_file_ui()
        if notify:
            self.data_changed.emit()

    def _build_track_file_service(self, database: Database) -> TrackFileService:
        settings = self._track_file_settings
        return TrackFileService(
            database,
            output_folder=settings.stem_output_folder,
            delivery_folder=settings.delivery_folder,
            audio_spec=TrackAudioSpec(
                file_format="WAV",
                sample_rate=int(settings.audio_sample_rate or 48000),
                bit_depth=int(settings.audio_bit_depth or 24),
                channels=int(settings.audio_channels or 1),
            ),
        )

    def _build_track_rename_service(
        self,
        database: Database,
    ) -> TrackRenameService:
        return TrackRenameService(
            database,
            output_folder=self._track_file_settings.stem_output_folder,
        )

    def _scan_track_files(self) -> TrackFileInventory:
        if self._track_file_service is None:
            return TrackFileInventory()
        try:
            return self._track_file_service.scan_and_sync()
        except Exception:
            # The DB tracking view must remain usable even when filesystem
            # inspection fails. Folder configuration is surfaced in Output Health.
            return TrackFileInventory(
                output_folder=self._track_file_settings.stem_output_folder,
                delivery_folder=self._track_file_settings.delivery_folder,
            )

    # ------------------------------------------------------------------
    # WORKSPACE SUMMARY / TALENT CHANGE
    # ------------------------------------------------------------------

    def _refresh_workspace(self) -> None:
        super()._refresh_workspace()

        talent_id = self.talent_combo.currentData()
        if self._summary_service is not None and talent_id is not None:
            try:
                summary = self._summary_service.get_talent_summary(int(talent_id))
            except Exception:
                pass
            else:
                talent_name = self.talent_combo.currentText().strip()
                self.summary_label.setText(
                    f"Talent: {talent_name}   •   "
                    f"Tokoh: {self._format_count(summary.character_count)}   •   "
                    f"Episode: {self._format_count(summary.episode_count)}   •   "
                    f"Dialog: {self._format_count(summary.dialogue_count)}"
                )

        self._refresh_track_file_ui()

    @staticmethod
    def _format_count(value: int) -> str:
        return f"{int(value):,}".replace(",", ".")

    # ------------------------------------------------------------------
    # WORKSPACE SWITCHER
    # ------------------------------------------------------------------

    def _build_tracking_workspaces(self) -> None:
        shell_layout = self.layout()
        context = (
            shell_layout.itemAt(0).widget()
            if shell_layout and shell_layout.count() > 1
            else None
        )
        workspace = (
            shell_layout.itemAt(1).widget()
            if shell_layout and shell_layout.count() > 1
            else None
        )
        root = workspace.layout() if workspace is not None else None
        if root is None:
            return

        if context is not None:
            context.hide()

        self.drive_button.hide()
        self.title_label.hide()
        root.removeWidget(self.scroll)

        filter_bar = QFrame()
        filter_bar.setObjectName("TrackingFilterBar")
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(12, 9, 12, 9)
        filter_layout.setSpacing(8)

        talent_label = QLabel("Talent")
        talent_label.setObjectName("TrackingFilterLabel")
        filter_layout.addWidget(talent_label)
        self.talent_combo.setMinimumWidth(180)
        filter_layout.addWidget(self.talent_combo)
        filter_layout.addSpacing(8)
        filter_layout.addWidget(self.summary_label, 1)

        self.tracking_workspace_stack = QStackedWidget()
        self.tracking_workspace_stack.setObjectName(
            "TrackingWorkspaceStack"
        )
        self.tracking_workspace_stack.addWidget(
            self._build_tracking_grid_workspace()
        )

        root.insertWidget(0, filter_bar)
        root.insertWidget(1, self.status_legend_widget)
        root.insertWidget(2, self.tracking_workspace_stack, 1)

    def _build_tracking_grid_workspace(self) -> QWidget:
        page = QWidget()
        page.setObjectName("TrackingGridWorkspace")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        body = QSplitter(Qt.Orientation.Horizontal)
        body.setChildrenCollapsible(False)
        body.setHandleWidth(6)

        matrix_panel = QWidget()
        matrix_layout = QVBoxLayout(matrix_panel)
        matrix_layout.setContentsMargins(0, 0, 0, 0)
        matrix_layout.setSpacing(8)
        matrix_layout.addWidget(self.scroll, 1)
        matrix_layout.addWidget(self._build_tracking_detail_bar())
        body.addWidget(matrix_panel)

        queue_panel = QFrame()
        queue_panel.setObjectName("TrackingQueuePanel")
        queue_panel.setMinimumWidth(280)
        queue_layout = QVBoxLayout(queue_panel)
        queue_layout.setContentsMargins(10, 9, 10, 10)
        queue_layout.setSpacing(6)

        queue_title = QLabel("TRACKS TO STEM")
        queue_title.setObjectName("TrackingFooterTitle")
        queue_layout.addWidget(queue_title)

        episode_row = QHBoxLayout()
        episode_row.setContentsMargins(0, 0, 0, 0)
        episode_row.setSpacing(6)

        episode_label = QLabel("Episode")
        episode_label.setObjectName("TrackingFilterLabel")
        episode_row.addWidget(episode_label)

        self.episode_combo.setMinimumWidth(128)
        episode_row.addWidget(self.episode_combo, 1)

        self.prev_episode_button.setProperty("trackingNav", True)
        self.next_episode_button.setProperty("trackingNav", True)
        episode_row.addWidget(self.prev_episode_button)
        episode_row.addWidget(self.next_episode_button)
        queue_layout.addLayout(episode_row)

        queue_help = QLabel(
            "Episode hanya menampilkan episode yang dimainkan talent terpilih. "
            "Daftar di bawah menunjukkan track yang harus dibuat stem."
        )
        queue_help.setObjectName("PageSubtitle")
        queue_help.setWordWrap(True)
        queue_layout.addWidget(queue_help)

        self.character_table.setMinimumHeight(180)
        self.character_table.setMaximumHeight(16777215)
        self.character_table.setAlternatingRowColors(False)
        self.character_table.setShowGrid(False)
        queue_layout.addWidget(self.character_table, 1)

        body.addWidget(queue_panel)
        body.setStretchFactor(0, 7)
        body.setStretchFactor(1, 3)
        body.setSizes([760, 320])

        layout.addWidget(body, 1)
        return page

    def _build_tracking_detail_bar(self) -> QFrame:
        self._detail_chip = None

        bar = QFrame()
        bar.setObjectName("TrackingDetailBar")
        bar.setVisible(False)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(10)

        self.detail_episode = QLabel("Episode —")
        self.detail_episode.setObjectName("TrackingDetailPrimary")
        layout.addWidget(self.detail_episode)

        self.detail_character = QLabel("Pilih episode")
        self.detail_character.setObjectName("TrackingDetailText")
        self.detail_character.setMinimumWidth(160)
        layout.addWidget(self.detail_character, 1)

        self.detail_progress = QLabel("0/0 dialog")
        self.detail_progress.setObjectName("TrackingDetailText")
        layout.addWidget(self.detail_progress)

        self.detail_status = QLabel("-")
        self.detail_status.setObjectName("TrackingDetailStatus")
        self.detail_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.detail_status)

        self.detail_go_dialog_button = QPushButton("Go to Dialog")
        self.detail_go_dialog_button.setProperty("secondary", True)
        self.detail_go_dialog_button.clicked.connect(
            self._go_to_selected_dialog
        )
        layout.addWidget(self.detail_go_dialog_button)

        self.detail_revision_button = QPushButton("Mark Revision")
        self.detail_revision_button.setProperty("trackingRevisionAction", True)
        self.detail_revision_button.clicked.connect(
            self._tracking_revision_clicked
        )
        layout.addWidget(self.detail_revision_button)

        self.tracking_detail_bar = bar
        return bar

    def _update_tracking_detail_bar(self, chip) -> None:
        self._detail_chip = chip
        if not hasattr(self, "tracking_detail_bar"):
            return

        if chip is None:
            self.tracking_detail_bar.hide()
            return

        self.detail_episode.setText(f"Episode {chip.episode_number}")
        self.detail_character.setText(chip.character_name)
        self.detail_character.setToolTip(chip.character_name)
        self.detail_progress.setText(
            f"{chip.recorded_dialogues}/{chip.total_dialogues} dialog"
        )
        self.detail_status.setText(
            STATUS_LABELS.get(
                chip.display_status,
                chip.display_status,
            )
        )

        background, foreground, border = status_palette(
            chip.display_status
        )
        self.detail_status.setStyleSheet(
            f"background: {background}; color: {foreground}; "
            f"border: 1px solid {border}; border-radius: 6px; "
            "padding: 4px 9px; font-weight: 750;"
        )

        self.detail_revision_button.setText(
            "Clear Revision"
            if chip.display_status == REVISION
            else "Mark Revision"
        )
        self.tracking_detail_bar.show()

    def _tracking_revision_clicked(self) -> None:
        chip = self._detail_chip
        if chip is None:
            return

        requested = (
            NOT_READY
            if chip.display_status == REVISION
            else REVISION
        )
        self.apply_selected_status(requested)

    def _go_to_selected_dialog(self) -> None:
        chip = self._detail_chip
        if chip is None:
            return
        open_dialog_scope(self.window(), chip)

    def show_workspace(self, key: str) -> None:
        if not hasattr(self, "tracking_workspace_stack"):
            return
        self._workspace_key = WORKSPACE_TRACKING
        self.tracking_workspace_stack.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # COMPACT STATUS LEGEND
    # ------------------------------------------------------------------

    def _compact_status_legend(self) -> None:
        self.status_legend_widget = QFrame()
        self.status_legend_widget.setObjectName("TrackingLegendBar")

        layout = QHBoxLayout(self.status_legend_widget)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(5)

        title = QLabel("STATUS")
        title.setObjectName("TrackingFilterLabel")
        layout.addWidget(title)

        for status in STATUS_ORDER:
            label = self._status_legend_label(status)
            label.setMinimumWidth(0)
            layout.addWidget(label)

        layout.addStretch(1)

    def _add_output_health_sidebar(self) -> None:
        self.output_health_title = QLabel("OUTPUT HEALTH")
        self.output_health_title.setObjectName("TrackingFooterTitle")

        holder = QFrame()
        holder.setObjectName("TrackingHealthStrip")
        holder.setMaximumWidth(300)
        health_layout = QGridLayout(holder)
        health_layout.setContentsMargins(10, 8, 10, 8)
        health_layout.setHorizontalSpacing(10)
        health_layout.setVerticalSpacing(4)

        self.stemmed_health_label = QLabel("Stemmed")
        self.stemmed_health_value = QLabel("0/0")
        self.delivered_health_label = QLabel("Delivered")
        self.delivered_health_value = QLabel("0/0")
        self.warning_health_label = QLabel("Warnings")
        self.warning_health_value = QLabel("0")

        for label in (
            self.stemmed_health_label,
            self.delivered_health_label,
            self.warning_health_label,
        ):
            label.setObjectName("TrackingHealthLabel")

        for value in (
            self.stemmed_health_value,
            self.delivered_health_value,
            self.warning_health_value,
        ):
            value.setObjectName("TrackingHealthValue")
            value.setAlignment(Qt.AlignmentFlag.AlignRight)

        health_layout.addWidget(self.output_health_title, 0, 0, 1, 2)
        health_layout.addWidget(self.stemmed_health_label, 1, 0)
        health_layout.addWidget(self.stemmed_health_value, 1, 1)
        health_layout.addWidget(self.delivered_health_label, 2, 0)
        health_layout.addWidget(self.delivered_health_value, 2, 1)
        health_layout.addWidget(self.warning_health_label, 3, 0)
        health_layout.addWidget(self.warning_health_value, 3, 1)

        self.go_output_health_button = QPushButton("Go to Output Health")
        self.go_output_health_button.setProperty("secondary", True)
        self.go_output_health_button.clicked.connect(
            lambda: self.show_workspace(WORKSPACE_OUTPUT_HEALTH)
        )
        health_layout.addWidget(
            self.go_output_health_button,
            4,
            0,
            1,
            2,
        )

        self.output_health_summary = holder

    # ------------------------------------------------------------------
    # TRACK FILES WORKSPACE
    # ------------------------------------------------------------------

    def _build_track_files_workspace(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        body = QSplitter(Qt.Orientation.Horizontal)
        body.setChildrenCollapsible(False)
        body.setHandleWidth(6)

        suggestion_panel = QFrame()
        suggestion_panel.setObjectName("DashboardCard")
        suggestion_panel.setMinimumWidth(190)
        suggestion_root = QVBoxLayout(suggestion_panel)
        suggestion_root.setContentsMargins(10, 10, 10, 10)
        suggestion_root.setSpacing(7)

        suggestion_title = QLabel("TRACK NAME SUGGESTION")
        suggestion_title.setObjectName("SectionTitle")
        suggestion_root.addWidget(suggestion_title)

        suggestion_help = QLabel(
            "Canonical character name untuk track DAW. "
            "Klik nama untuk menyalin."
        )
        suggestion_help.setObjectName("MutedLabel")
        suggestion_help.setWordWrap(True)
        suggestion_root.addWidget(suggestion_help)

        self.track_name_scroll = QScrollArea()
        self.track_name_scroll.setWidgetResizable(True)
        self.track_name_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.track_name_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.track_name_holder = QWidget()
        self.track_name_grid = QGridLayout(self.track_name_holder)
        self.track_name_grid.setContentsMargins(0, 0, 0, 0)
        self.track_name_grid.setHorizontalSpacing(0)
        self.track_name_grid.setVerticalSpacing(6)
        self.track_name_grid.setColumnStretch(0, 1)
        self.track_name_scroll.setWidget(self.track_name_holder)
        suggestion_root.addWidget(self.track_name_scroll, 1)

        body.addWidget(suggestion_panel)

        files_panel = QWidget()
        files_root = QVBoxLayout(files_panel)
        files_root.setContentsMargins(0, 0, 0, 0)
        files_root.setSpacing(8)

        track_files_header = QHBoxLayout()
        track_files_header.setContentsMargins(0, 0, 0, 0)
        track_files_header.setSpacing(6)

        self.track_files_title = QLabel("TRACK FILES")
        self.track_files_title.setObjectName("SectionTitle")
        track_files_header.addWidget(self.track_files_title)
        track_files_header.addStretch(1)

        self.rename_episode_button = QPushButton("Match & Rename Episode")
        self.rename_episode_button.setProperty("secondary", True)
        self.rename_episode_button.clicked.connect(
            self._rename_current_episode
        )
        track_files_header.addWidget(self.rename_episode_button)

        self.rename_talent_button = QPushButton("Batch Match & Rename Talent")
        self.rename_talent_button.setProperty("secondary", True)
        self.rename_talent_button.clicked.connect(
            self._rename_current_talent
        )
        track_files_header.addWidget(self.rename_talent_button)

        self.refresh_track_files_button = QPushButton("Refresh Files")
        self.refresh_track_files_button.setProperty("secondary", True)
        self.refresh_track_files_button.clicked.connect(
            self.refresh_track_files
        )
        track_files_header.addWidget(self.refresh_track_files_button)

        files_root.addLayout(track_files_header)

        self.track_files_table = QTableWidget(0, 3)
        self.track_files_table.setHorizontalHeaderLabels(
            ["TRACK SUGGESTION", "STEM / EXPORT", "DELIVERED"]
        )
        self.track_files_table.setAlternatingRowColors(True)
        self.track_files_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.track_files_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.track_files_table.verticalHeader().setVisible(False)
        self.track_files_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.track_files_table.customContextMenuRequested.connect(
            self._show_track_file_context_menu
        )
        self.track_files_table.cellDoubleClicked.connect(
            self._track_file_double_clicked
        )
        header = self.track_files_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        files_root.addWidget(self.track_files_table, 1)

        body.addWidget(files_panel)
        body.setStretchFactor(0, 1)
        body.setStretchFactor(1, 4)
        body.setSizes([220, 880])

        root.addWidget(body, 1)
        return page

    def _track_name_entries(self) -> list[tuple[int, str, tuple[str, ...]]]:
        entries: list[tuple[int, str, tuple[str, ...]]] = []
        seen: set[int] = set()

        for row in self._workspace_rows:
            character_id = int(row.character_id)
            if character_id in seen:
                continue
            seen.add(character_id)

            aliases: list[str] = []
            alias_seen: set[str] = set()
            for item in self._track_file_inventory.rows:
                if item.character_id != character_id:
                    continue
                for alias in item.aliases:
                    key = alias.casefold()
                    if key not in alias_seen:
                        alias_seen.add(key)
                        aliases.append(alias)

            entries.append(
                (
                    character_id,
                    str(row.character_name).upper(),
                    tuple(aliases),
                )
            )
        return entries

    def _refresh_track_name_suggestions(self) -> None:
        if not hasattr(self, "track_name_grid"):
            return

        self._clear_grid(self.track_name_grid)
        entries = self._track_name_entries()

        if not entries:
            label = QLabel("Pilih talent untuk melihat track name suggestion.")
            label.setObjectName("MutedLabel")
            label.setWordWrap(True)
            self.track_name_grid.addWidget(label, 0, 0)
            self.track_name_grid.setRowStretch(1, 1)
            return

        for index, (_character_id, name, aliases) in enumerate(entries):
            button = QPushButton(name)
            button.setProperty("secondary", True)
            button.setStyleSheet("text-align: left; padding: 5px 8px;")
            button.clicked.connect(
                lambda checked=False, track_name=name:
                self._copy_track_name(track_name)
            )
            alias_text = ", ".join(aliases) if aliases else "—"
            button.setToolTip(
                f"Track Name: {name}\nAliases: {alias_text}\n"
                "Click to copy"
            )
            self.track_name_grid.addWidget(button, index, 0)

        self.track_name_grid.setRowStretch(len(entries), 1)

    @staticmethod
    def _copy_track_name(name: str) -> None:
        text = str(name)
        QApplication.clipboard().setText(text)
        QToolTip.showText(
            QCursor.pos(),
            f"Copied: {text}",
        )

    # ------------------------------------------------------------------
    # OUTPUT HEALTH WORKSPACE
    # ------------------------------------------------------------------

    def _build_output_health_workspace(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        summary_title = QLabel("OUTPUT SUMMARY")
        summary_title.setObjectName("SectionTitle")
        root.addWidget(summary_title)

        summary_frame = QFrame()
        summary_frame.setObjectName("DashboardCard")
        summary_grid = QGridLayout(summary_frame)
        summary_grid.setContentsMargins(10, 8, 10, 8)
        summary_grid.setHorizontalSpacing(14)
        summary_grid.setVerticalSpacing(4)

        self.output_summary_values: dict[str, QLabel] = {}
        for column, (key, label) in enumerate(
            (
                ("expected", "Expected Tracks"),
                ("stem", "Valid Stem"),
                ("delivery", "Valid Delivery"),
                ("stem_ep", "Stemmed Episodes"),
                ("delivery_ep", "Delivered Episodes"),
                ("warnings", "Warnings"),
            )
        ):
            value = QLabel("0")
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value.setStyleSheet("font-size: 14pt; font-weight: 700;")
            caption = QLabel(label)
            caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
            caption.setObjectName("MutedLabel")
            summary_grid.addWidget(value, 0, column)
            summary_grid.addWidget(caption, 1, column)
            self.output_summary_values[key] = value

        root.addWidget(summary_frame)

        episode_title = QLabel("EPISODE STATUS")
        episode_title.setObjectName("SectionTitle")
        root.addWidget(episode_title)

        self.output_episode_table = QTableWidget(0, 4)
        self.output_episode_table.setHorizontalHeaderLabels(
            ["EPS", "STEM", "DELIVERY", "WARNING"]
        )
        self.output_episode_table.setMaximumHeight(230)
        self.output_episode_table.setAlternatingRowColors(True)
        self.output_episode_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.output_episode_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.output_episode_table.verticalHeader().setVisible(False)
        episode_header = self.output_episode_table.horizontalHeader()
        episode_header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        episode_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        episode_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        episode_header.setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        root.addWidget(self.output_episode_table)

        warning_title = QLabel("WARNINGS")
        warning_title.setObjectName("SectionTitle")
        root.addWidget(warning_title)

        self.output_warning_table = QTableWidget(0, 5)
        self.output_warning_table.setHorizontalHeaderLabels(
            ["TYPE", "EPS", "CHARACTER", "FILE", "MESSAGE"]
        )
        self.output_warning_table.setAlternatingRowColors(True)
        self.output_warning_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.output_warning_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.output_warning_table.verticalHeader().setVisible(False)
        self.output_warning_table.cellDoubleClicked.connect(
            self._output_warning_double_clicked
        )
        warning_header = self.output_warning_table.horizontalHeader()
        warning_header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        warning_header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        warning_header.setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        warning_header.setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        warning_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.output_warning_table, 1)

        return page

    def _refresh_output_health_workspace(self) -> None:
        if not hasattr(self, "output_episode_table"):
            return

        talent_id = self.talent_combo.currentData()
        if talent_id is None:
            for label in self.output_summary_values.values():
                label.setText("0")
            self.output_episode_table.setRowCount(0)
            self.output_warning_table.setRowCount(0)
            return

        talent_id = int(talent_id)
        rows = self._track_file_inventory.rows_for_talent(talent_id)
        health = self._track_file_inventory.health_for_talent(talent_id)
        scoped_global_warnings = self._scoped_global_warnings(talent_id)
        rename_by_source = self._rename_recommendations_by_source(talent_id)

        warning_rows: list[
            tuple[TrackFileWarning, str, TrackRenameItem | None]
        ] = []
        for row in rows:
            warning_rows.extend(
                (warning, row.character_name, None)
                for warning in row.warnings
            )

        for warning in scoped_global_warnings:
            rename_item = rename_by_source.get(
                str(Path(warning.path)).casefold()
                if warning.path
                else ""
            )
            if (
                warning.code == "UNEXPECTED_TRACK_FILE"
                and rename_item is not None
            ):
                if rename_item.target_path:
                    rename_message = (
                        f"{Path(rename_item.source_path).name} dapat "
                        f"dinormalisasi menjadi "
                        f"{Path(rename_item.target_path).name}."
                    )
                else:
                    rename_message = (
                        f"{Path(rename_item.source_path).name} belum cocok "
                        "otomatis. Double-click untuk memilih expected "
                        "filename secara manual."
                    )

                synthetic = TrackFileWarning(
                    code="RENAME_RECOMMENDED",
                    message=rename_message,
                    path=rename_item.source_path,
                    talent_id=talent_id,
                    episode_number=rename_item.episode_number,
                )
                warning_rows.append(
                    (
                        synthetic,
                        rename_item.character_name,
                        rename_item,
                    )
                )
            else:
                warning_rows.append((warning, "—", None))

        total_warning_count = len(warning_rows)

        self.output_summary_values["expected"].setText(str(health.total_tracks))
        self.output_summary_values["stem"].setText(str(health.stemmed_tracks))
        self.output_summary_values["delivery"].setText(
            str(health.delivered_tracks)
        )
        self.output_summary_values["stem_ep"].setText(
            f"{health.stemmed_episodes}/{health.total_episodes}"
        )
        self.output_summary_values["delivery_ep"].setText(
            f"{health.delivered_episodes}/{health.total_episodes}"
        )
        self.output_summary_values["warnings"].setText(
            str(total_warning_count)
        )
        self.output_summary_values["warnings"].setStyleSheet(
            f"font-size: 14pt; font-weight: 700; color: {COLORS['error']};"
            if total_warning_count
            else (
                f"font-size: 14pt; font-weight: 700; "
                f"color: {COLORS['recorded']};"
            )
        )

        by_episode: dict[int, list[TrackFileRow]] = {}
        for row in rows:
            by_episode.setdefault(row.episode_number, []).append(row)

        self.output_episode_table.setRowCount(len(by_episode))
        for row_index, episode_number in enumerate(sorted(by_episode)):
            group = by_episode[episode_number]
            total = len(group)
            stem = sum(1 for item in group if item.output.valid)
            delivered = sum(1 for item in group if item.delivered.valid)
            warning_count = sum(len(item.warnings) for item in group)
            warning_count += sum(
                1
                for warning, _character, _rename_item in warning_rows
                if (
                    warning.episode_number == episode_number
                    and warning not in [
                        row_warning
                        for row_item in group
                        for row_warning in row_item.warnings
                    ]
                )
            )

            stem_text = (
                "✓ Complete" if total > 0 and stem == total
                else f"{stem}/{total} Tracks"
            )
            delivery_text = (
                "✓ Complete" if total > 0 and delivered == total
                else f"{delivered}/{total} Tracks"
            )
            values = [
                str(episode_number),
                stem_text,
                delivery_text,
                str(warning_count) if warning_count else "—",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                self.output_episode_table.setItem(row_index, column, item)

            if warning_count:
                self.output_episode_table.item(row_index, 3).setForeground(
                    QColor(COLORS["error_text"])
                )

        warning_rows.sort(
            key=lambda item: (
                item[0].episode_number
                if item[0].episode_number is not None
                else 999999999,
                item[0].code,
                item[1].casefold(),
            )
        )

        self.output_warning_table.setRowCount(len(warning_rows))
        for row_index, (
            warning,
            character_name,
            rename_item,
        ) in enumerate(warning_rows):
            filename = (
                Path(warning.path).name if warning.path else "—"
            )
            values = [
                warning.code.replace("_", " ").title(),
                (
                    str(warning.episode_number)
                    if warning.episode_number is not None
                    else "—"
                ),
                character_name,
                filename,
                warning.message,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(
                    warning.path if column == 3 and warning.path
                    else warning.message
                )
                if rename_item is not None:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        rename_item.source_path,
                    )
                self.output_warning_table.setItem(
                    row_index,
                    column,
                    item,
                )

    def _scoped_global_warnings(
        self,
        talent_id: int,
    ) -> list[TrackFileWarning]:
        result: list[TrackFileWarning] = []

        for warning in self._track_file_inventory.warnings:
            if warning.talent_id is not None:
                if int(warning.talent_id) == int(talent_id):
                    result.append(warning)
                continue

            if (
                warning.code == "UNEXPECTED_TRACK_FILE"
                and warning.path
            ):
                simple = parse_simple_export_filename(
                    Path(warning.path).name
                )
                if simple is not None:
                    candidate_talents = {
                        row.talent_id
                        for row in self._track_file_inventory.rows
                        if (
                            row.episode_number == simple.episode_number
                            and sanitize_filename_component(
                                row.character_name,
                                uppercase=True,
                            ).casefold()
                            == simple.track_name.casefold()
                        )
                    }
                    if candidate_talents:
                        if int(talent_id) in candidate_talents:
                            result.append(warning)
                        continue

            # Truly unattributed filesystem warnings remain visible to every
            # talent because they require project-level attention.
            result.append(warning)

        return result

    def _rename_recommendations_by_source(
        self,
        talent_id: int,
    ) -> dict[str, TrackRenameItem]:
        plan = self._track_rename_plan
        if plan.talent_id != int(talent_id):
            plan = self._build_rename_plan(talent_id=int(talent_id))

        return {
            str(Path(item.source_path)).casefold(): item
            for item in plan.items
            if (
                item.match_kind == MATCH_SIMPLE_EXPORT
                and item.status in {
                    RENAME_MATCHED,
                    RENAME_COLLISION,
                    RENAME_UNMATCHED,
                    RENAME_AMBIGUOUS,
                }
                and item.source_path
            )
        }

    def _output_warning_double_clicked(
        self,
        row: int,
        column: int,
    ) -> None:
        item = self.output_warning_table.item(row, column)
        if item is None:
            return
        source_path = item.data(Qt.ItemDataRole.UserRole)
        if source_path:
            self._rename_single_source(str(source_path))

    # ------------------------------------------------------------------
    # TRACK FILE TABLE + SIDEBAR SUMMARY
    # ------------------------------------------------------------------

    def _refresh_track_file_ui(self) -> None:
        if not hasattr(self, "track_files_table"):
            return

        talent_id = self.talent_combo.currentData()
        if talent_id is None:
            self.track_files_table.setRowCount(0)
            self._set_output_health_empty()
            self._refresh_track_name_suggestions()
            self._refresh_output_health_workspace()
            return

        self._refresh_track_files_table()

        talent_id = int(talent_id)
        health = self._track_file_inventory.health_for_talent(talent_id)
        scoped_warning_count = (
            sum(
                len(row.warnings)
                for row in self._track_file_inventory.rows_for_talent(
                    talent_id
                )
            )
            + len(self._scoped_global_warnings(talent_id))
        )
        self.stemmed_health_value.setText(
            f"{health.stemmed_episodes}/{health.total_episodes}"
        )
        self.delivered_health_value.setText(
            f"{health.delivered_episodes}/{health.total_episodes}"
        )
        self.warning_health_value.setText(str(scoped_warning_count))
        self.warning_health_value.setStyleSheet(
            f"font-weight: 700; color: {COLORS['error']};"
            if scoped_warning_count
            else f"font-weight: 700; color: {COLORS['recorded']};"
        )

        self._refresh_track_name_suggestions()
        self._refresh_output_health_workspace()

    def _refresh_track_files_table(self) -> None:
        talent_id = self.talent_combo.currentData()
        if talent_id is None:
            self.track_files_table.setRowCount(0)
            self._track_rename_plan = TrackRenamePlan()
            return

        talent_id = int(talent_id)
        rows = self._track_file_inventory.rows_for_talent(talent_id)
        self._track_rename_plan = self._build_rename_plan(
            talent_id=talent_id,
        )
        rename_by_scope = {
            (
                item.episode_number,
                item.character_id,
                item.talent_id,
            ): item
            for item in self._track_rename_plan.items
            if (
                item.character_id is not None
                and item.talent_id is not None
                and item.status in {RENAME_MATCHED, RENAME_COLLISION}
            )
        }

        # Files with a readable episode but no automatic character match must
        # remain visible. They are appended after expected rows and can be
        # manually assigned through the same rename preview.
        unmatched_items = [
            item
            for item in self._track_rename_plan.items
            if (
                item.character_id is None
                and item.status in {
                    RENAME_UNMATCHED,
                    RENAME_AMBIGUOUS,
                }
                and item.source_path
            )
        ]

        self.track_files_table.setRowCount(
            len(rows) + len(unmatched_items)
        )
        for row_index, row in enumerate(rows):
            suggestion = QTableWidgetItem(row.track_suggestion)
            suggestion.setToolTip(self._track_suggestion_tooltip(row))

            rename_item = rename_by_scope.get(
                (
                    row.episode_number,
                    row.character_id,
                    row.talent_id,
                )
            )
            simplified_candidate = (
                rename_item is not None
                and rename_item.match_kind == MATCH_SIMPLE_EXPORT
                and not row.output.exists
            )

            if simplified_candidate:
                source_name = Path(rename_item.source_path).name
                output = QTableWidgetItem(f"↻ {source_name}")
                output.setToolTip(
                    "Rename Recommended\n"
                    f"Current: {source_name}\n"
                    f"Expected: {Path(rename_item.target_path).name}\n"
                    f"{rename_item.detail}\n\n"
                    "Right-click or double-click to preview rename."
                )
                output.setForeground(QColor(COLORS["attention_text"]))
            else:
                output = QTableWidgetItem(
                    self._file_cell_text(row.output, pending=False)
                )
                output.setToolTip(self._file_tooltip(row.output))

            if rename_item is not None and rename_item.can_rename:
                output.setData(
                    Qt.ItemDataRole.UserRole,
                    rename_item.source_path,
                )
                output.setData(
                    Qt.ItemDataRole.UserRole + 1,
                    rename_item.target_path,
                )

            delivery_pending = (
                row.output.valid
                and not row.delivered.exists
            )
            delivered = QTableWidgetItem(
                self._file_cell_text(
                    row.delivered,
                    pending=delivery_pending,
                )
            )
            delivered.setToolTip(self._file_tooltip(row.delivered))

            for column, item in enumerate(
                (suggestion, output, delivered)
            ):
                self.track_files_table.setItem(
                    row_index,
                    column,
                    item,
                )

            if row.output.valid and not simplified_candidate:
                output.setForeground(QColor(COLORS["recorded_text"]))
            elif row.output.exists and not simplified_candidate:
                output.setForeground(QColor(COLORS["attention_text"]))

            if row.delivered.valid:
                delivered.setForeground(QColor(COLORS["recorded_text"]))
            elif row.delivered.exists:
                delivered.setForeground(QColor(COLORS["attention_text"]))
            elif delivery_pending:
                delivered.setForeground(QColor(COLORS["text_secondary"]))

            if row.warnings:
                suggestion.setBackground(QColor(COLORS["attention_soft"]))
                suggestion.setToolTip(
                    suggestion.toolTip()
                    + "\n\nWarnings:\n"
                    + "\n".join(
                        f"• {warning.message}"
                        for warning in row.warnings
                    )
                )

        offset = len(rows)
        for extra_index, rename_item in enumerate(unmatched_items):
            table_row = offset + extra_index
            status_label = (
                "AMBIGUOUS EXPORT"
                if rename_item.status == RENAME_AMBIGUOUS
                else "UNMATCHED EXPORT"
            )
            episode_label = (
                f"EP{rename_item.episode_number} "
                if rename_item.episode_number is not None
                else ""
            )

            suggestion = QTableWidgetItem(
                f"⚠ {episode_label}{status_label}"
            )
            suggestion.setBackground(QColor(COLORS["attention_soft"]))
            suggestion.setToolTip(
                rename_item.detail
                + "\n\nDouble-click Stem / Export untuk memilih "
                "expected filename secara manual."
            )

            output = QTableWidgetItem(
                f"↻ {Path(rename_item.source_path).name}"
            )
            output.setForeground(QColor(COLORS["attention_text"]))
            output.setToolTip(
                f"{rename_item.detail}\n\n"
                "Right-click atau double-click untuk manual match."
            )
            output.setData(
                Qt.ItemDataRole.UserRole,
                rename_item.source_path,
            )

            delivered = QTableWidgetItem("—")

            self.track_files_table.setItem(
                table_row,
                0,
                suggestion,
            )
            self.track_files_table.setItem(
                table_row,
                1,
                output,
            )
            self.track_files_table.setItem(
                table_row,
                2,
                delivered,
            )

    def _build_rename_plan(
        self,
        *,
        talent_id: int,
        episode_number: int | None = None,
        selected_source_path: str | None = None,
    ) -> TrackRenamePlan:
        if self._track_rename_service is None:
            return TrackRenamePlan()

        return self._track_rename_service.build_plan(
            self._track_file_inventory.rows,
            talent_id=int(talent_id),
            episode_number=(
                int(episode_number)
                if episode_number is not None
                else None
            ),
            selected_source_path=selected_source_path,
        )

    def _rename_current_episode(self) -> None:
        talent_id = self.talent_combo.currentData()
        episode_number = self.episode_combo.currentData()
        if talent_id is None:
            QMessageBox.information(
                self,
                "Rename Track Files",
                "Pilih talent terlebih dahulu.",
            )
            return
        if episode_number is None:
            QMessageBox.information(
                self,
                "Rename Track Files",
                "Pilih episode yang akan di-match dan rename.",
            )
            return

        plan = self._build_rename_plan(
            talent_id=int(talent_id),
            episode_number=int(episode_number),
        )
        self._preview_and_execute_rename(plan)

    def _rename_current_talent(self) -> None:
        talent_id = self.talent_combo.currentData()
        if talent_id is None:
            QMessageBox.information(
                self,
                "Rename Track Files",
                "Pilih talent terlebih dahulu.",
            )
            return

        plan = self._build_rename_plan(
            talent_id=int(talent_id),
        )
        self._preview_and_execute_rename(plan)

    def _show_track_file_context_menu(self, position) -> None:
        item = self.track_files_table.itemAt(position)
        if item is None:
            return

        row = item.row()
        output_item = self.track_files_table.item(row, 1)
        if output_item is None:
            return

        source_path = output_item.data(Qt.ItemDataRole.UserRole)
        if not source_path:
            return

        menu = QMenu(self.track_files_table)
        action = menu.addAction("Match / Rename Stem / Export…")
        selected = menu.exec(
            self.track_files_table.viewport().mapToGlobal(position)
        )
        if selected == action:
            self._rename_single_source(str(source_path))

    def _track_file_double_clicked(
        self,
        row: int,
        column: int,
    ) -> None:
        if column != 1:
            return
        item = self.track_files_table.item(row, column)
        if item is None:
            return
        source_path = item.data(Qt.ItemDataRole.UserRole)
        if source_path:
            self._rename_single_source(str(source_path))

    def _rename_single_source(self, source_path: str) -> None:
        talent_id = self.talent_combo.currentData()
        if talent_id is None:
            return

        plan = self._build_rename_plan(
            talent_id=int(talent_id),
            selected_source_path=source_path,
        )
        self._preview_and_execute_rename(plan)

    def _preview_and_execute_rename(
        self,
        plan: TrackRenamePlan,
    ) -> None:
        if not plan.items:
            QMessageBox.information(
                self,
                "Rename Track Files",
                "Tidak ada file yang cocok pada scope ini.",
            )
            return

        dialog = TrackRenamePreviewDialog(plan, parent=self)
        if not dialog.exec():
            return

        if self._track_rename_service is None:
            return

        try:
            renamed = self._track_rename_service.execute(plan)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Rename Track Files",
                f"Rename gagal. Tidak ada file yang sengaja dioverwrite.\n\n{exc}",
            )
            return

        self.refresh_track_files()
        QMessageBox.information(
            self,
            "Rename Track Files",
            f"{len(renamed)} file berhasil dinormalisasi ke expected filename.",
        )

    def _set_output_health_empty(self) -> None:
        self.stemmed_health_value.setText("0/0")
        self.delivered_health_value.setText("0/0")
        self.warning_health_value.setText("0")
        self.warning_health_value.setStyleSheet("font-weight: 700;")

    @staticmethod
    def _file_cell_text(check: AudioFileCheck, *, pending: bool) -> str:
        if check.valid:
            return "✓ " + Path(check.path).name
        if check.exists:
            return "⚠ " + Path(check.path).name
        if pending:
            return "Pending Delivery"
        return "—"

    @staticmethod
    def _file_tooltip(check: AudioFileCheck) -> str:
        if not check.exists:
            return "File belum ditemukan."

        lines = [check.path]
        if check.info is not None:
            channel = (
                "Mono"
                if check.info.channels == 1
                else f"{check.info.channels} ch"
            )
            lines.extend(
                [
                    f"{check.info.sample_rate} Hz",
                    f"{check.info.bit_depth}-bit",
                    channel,
                ]
            )
        if check.problems:
            lines.extend(
                ["", *[f"⚠ {problem}" for problem in check.problems]]
            )
        return "\n".join(lines)

    @staticmethod
    def _track_suggestion_tooltip(row: TrackFileRow) -> str:
        alias_text = ", ".join(row.aliases) if row.aliases else "—"
        return (
            f"Episode: {row.episode_number}\n"
            f"Canonical Character: {row.character_name}\n"
            f"Source Aliases in Episode: {alias_text}\n"
            f"Talent: {row.talent_name}\n"
            f"Expected File: {row.expected_filename}"
        )

    @staticmethod
    def _clear_grid(grid: QGridLayout) -> None:
        while grid.count():
            item = grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    # ------------------------------------------------------------------
    # REVISION OVERRIDE
    # ------------------------------------------------------------------

    def apply_selected_status(self, status: str) -> None:
        super().apply_selected_status(status)
        # Clearing Revision should immediately restore the automatic file-based
        # state if valid files are still present.
        if status == "NOT_READY" and self._database is not None:
            self.refresh_track_files(notify=False)
