from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from core.database import Database
from core.project_settings import ProjectSettings
from pages.tracking_page import STATUS_ORDER, TrackingPage
from services.track_file_service import (
    AudioFileCheck,
    TrackAudioSpec,
    TrackFileInventory,
    TrackFileRow,
    TrackFileService,
)
from services.tracking_summary_service import TrackingSummaryService


class CompactTrackingPage(TrackingPage):
    """Tracking page with compact legend plus filesystem track inventory."""

    def __init__(self, parent=None):
        self._summary_service: TrackingSummaryService | None = None
        self._track_file_service: TrackFileService | None = None
        self._track_file_inventory = TrackFileInventory()
        self._track_file_settings = ProjectSettings()
        super().__init__(parent)
        self.summary_label.setContentsMargins(8, 2, 8, 2)
        self._compact_status_legend()
        self._add_output_health()
        self._add_track_files_table()

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
        self._track_file_inventory = self._scan_track_files()
        super().set_database(database)
        self._refresh_track_file_ui()

    def refresh_track_files(self) -> None:
        if self._database is None:
            return

        current_talent = self.talent_combo.currentData()
        current_episode = self.episode_combo.currentData()
        self._track_file_service = self._build_track_file_service(self._database)
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

    def _build_track_file_service(self, database: Database) -> TrackFileService:
        settings = self._track_file_settings
        return TrackFileService(
            database,
            output_folder=settings.stem_output_folder,
            delivery_folder=settings.delivery_folder,
            audio_spec=TrackAudioSpec(
                file_format=str(settings.audio_format or "WAV"),
                sample_rate=int(settings.audio_sample_rate or 48000),
                bit_depth=int(settings.audio_bit_depth or 24),
                channels=int(settings.audio_channels or 1),
            ),
        )

    def _scan_track_files(self) -> TrackFileInventory:
        if self._track_file_service is None:
            return TrackFileInventory()
        try:
            return self._track_file_service.scan_and_sync()
        except Exception:
            # Tracking database view must remain usable even if filesystem scan
            # fails. Project Settings / OUTPUT HEALTH will expose configuration
            # problems on the next successful scan.
            return TrackFileInventory(
                output_folder=self._track_file_settings.stem_output_folder,
                delivery_folder=self._track_file_settings.delivery_folder,
            )

    # ------------------------------------------------------------------
    # WORKSPACE SUMMARY
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
    # COMPACT STATUS LEGEND
    # ------------------------------------------------------------------

    def _compact_status_legend(self) -> None:
        shell_layout = self.layout()
        if shell_layout is None or shell_layout.count() < 1:
            return
        context = shell_layout.itemAt(0).widget()
        root = getattr(context, "layout_root", None)
        if root is None:
            return

        status_index = -1
        episode_index = -1
        old_status_labels: list[QLabel] = []

        for index in range(root.count()):
            item = root.itemAt(index)
            widget = item.widget()
            if isinstance(widget, QLabel) and widget.objectName() == "SectionTitle":
                if widget.text() == "STATUS":
                    status_index = index
                elif widget.text() == "EPISODE" and status_index >= 0:
                    episode_index = index
                    break

        if status_index < 0:
            return

        stop = episode_index if episode_index >= 0 else root.count()
        for index in range(status_index + 1, stop):
            widget = root.itemAt(index).widget()
            if isinstance(widget, QLabel) and widget.objectName() != "SectionTitle":
                old_status_labels.append(widget)

        for label in old_status_labels:
            label.hide()

        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        for index, status in enumerate(STATUS_ORDER):
            label = self._status_legend_label(status)
            label.setMinimumWidth(0)
            grid.addWidget(label, index // 2, index % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        root.insertWidget(status_index + 1, holder)

    # ------------------------------------------------------------------
    # OUTPUT HEALTH SIDEBAR
    # ------------------------------------------------------------------

    def _add_output_health(self) -> None:
        shell_layout = self.layout()
        context = shell_layout.itemAt(0).widget() if shell_layout else None
        root = getattr(context, "layout_root", None)
        if root is None:
            return

        self.output_health_title = QLabel("OUTPUT HEALTH")
        self.output_health_title.setObjectName("SectionTitle")

        holder = QFrame()
        holder.setObjectName("DashboardCard")
        health_layout = QGridLayout(holder)
        health_layout.setContentsMargins(8, 8, 8, 8)
        health_layout.setHorizontalSpacing(6)
        health_layout.setVerticalSpacing(5)

        self.stemmed_health_label = QLabel("Stemmed Episodes")
        self.stemmed_health_value = QLabel("0/0")
        self.delivered_health_label = QLabel("Delivered Episodes")
        self.delivered_health_value = QLabel("0/0")
        self.warning_health_label = QLabel("Warnings")
        self.warning_health_value = QLabel("0")

        for value in (
            self.stemmed_health_value,
            self.delivered_health_value,
            self.warning_health_value,
        ):
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            value.setStyleSheet("font-weight: 700;")

        health_layout.addWidget(self.stemmed_health_label, 0, 0)
        health_layout.addWidget(self.stemmed_health_value, 0, 1)
        health_layout.addWidget(self.delivered_health_label, 1, 0)
        health_layout.addWidget(self.delivered_health_value, 1, 1)
        health_layout.addWidget(self.warning_health_label, 2, 0)
        health_layout.addWidget(self.warning_health_value, 2, 1)

        insert_at = max(0, root.count() - 1)
        root.insertWidget(insert_at, self.output_health_title)
        root.insertWidget(insert_at + 1, holder)

    # ------------------------------------------------------------------
    # TRACK FILES TABLE
    # ------------------------------------------------------------------

    def _add_track_files_table(self) -> None:
        shell_layout = self.layout()
        workspace = shell_layout.itemAt(1).widget() if shell_layout else None
        root = workspace.layout() if workspace is not None else None
        if root is None:
            return

        self.track_files_title = QLabel("TRACK FILES")
        self.track_files_title.setObjectName("SectionTitle")
        root.addWidget(self.track_files_title)

        self.track_files_table = QTableWidget(0, 3)
        self.track_files_table.setHorizontalHeaderLabels(
            ["TRACK SUGGESTION", "STEM / EXPORT", "DELIVERED"]
        )
        self.track_files_table.setMinimumHeight(170)
        self.track_files_table.setMaximumHeight(260)
        self.track_files_table.setAlternatingRowColors(True)
        self.track_files_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.track_files_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.track_files_table.verticalHeader().setVisible(False)
        header = self.track_files_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.track_files_table)

    def _refresh_track_file_ui(self) -> None:
        if not hasattr(self, "track_files_table"):
            return

        talent_id = self.talent_combo.currentData()
        if talent_id is None:
            self.track_files_table.setRowCount(0)
            self._set_output_health_empty()
            return

        rows = self._track_file_inventory.rows_for_talent(int(talent_id))
        self.track_files_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            suggestion = QTableWidgetItem(row.track_suggestion)
            suggestion.setToolTip(self._track_suggestion_tooltip(row))

            output = QTableWidgetItem(self._file_cell_text(row.output, pending=False))
            output.setToolTip(self._file_tooltip(row.output))

            delivery_pending = row.output.valid and not row.delivered.exists
            delivered = QTableWidgetItem(
                self._file_cell_text(row.delivered, pending=delivery_pending)
            )
            delivered.setToolTip(self._file_tooltip(row.delivered))

            for column, item in enumerate((suggestion, output, delivered)):
                self.track_files_table.setItem(row_index, column, item)

            if row.output.valid:
                output.setForeground(QColor("#176b2c"))
            elif row.output.exists:
                output.setForeground(QColor("#9a5a00"))

            if row.delivered.valid:
                delivered.setForeground(QColor("#176b2c"))
            elif row.delivered.exists:
                delivered.setForeground(QColor("#9a5a00"))
            elif delivery_pending:
                delivered.setForeground(QColor("#6b7075"))

            if row.warnings:
                suggestion.setBackground(QColor("#FFF4CE"))
                suggestion.setToolTip(
                    suggestion.toolTip()
                    + "\n\nWarnings:\n"
                    + "\n".join(f"• {warning.message}" for warning in row.warnings)
                )

        health = self._track_file_inventory.health_for_talent(int(talent_id))
        self.stemmed_health_value.setText(
            f"{health.stemmed_episodes}/{health.total_episodes}"
        )
        self.delivered_health_value.setText(
            f"{health.delivered_episodes}/{health.total_episodes}"
        )
        self.warning_health_value.setText(str(health.warnings))
        self.warning_health_value.setStyleSheet(
            "font-weight: 700; color: #b3261e;"
            if health.warnings
            else "font-weight: 700; color: #176b2c;"
        )

    def _set_output_health_empty(self) -> None:
        self.stemmed_health_value.setText("0/0")
        self.delivered_health_value.setText("0/0")
        self.warning_health_value.setText("0")
        self.warning_health_value.setStyleSheet("font-weight: 700;")

    @staticmethod
    def _file_cell_text(check: AudioFileCheck, *, pending: bool) -> str:
        if check.valid:
            return "✓ " + check.path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
        if check.exists:
            return "⚠ " + check.path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
        if pending:
            return "Pending Delivery"
        return "—"

    @staticmethod
    def _file_tooltip(check: AudioFileCheck) -> str:
        if not check.exists:
            return "File belum ditemukan."
        lines = [check.path]
        if check.info is not None:
            channel = "Mono" if check.info.channels == 1 else f"{check.info.channels} ch"
            lines.extend(
                [
                    f"{check.info.sample_rate} Hz",
                    f"{check.info.bit_depth}-bit",
                    channel,
                ]
            )
        if check.problems:
            lines.extend(["", *[f"⚠ {problem}" for problem in check.problems]])
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

    # ------------------------------------------------------------------
    # REVISION OVERRIDE
    # ------------------------------------------------------------------

    def apply_selected_status(self, status: str) -> None:
        super().apply_selected_status(status)
        # Clearing Revision should immediately restore the automatic file-based
        # status if valid files are still present.
        if status == "NOT_READY" and self._database is not None:
            self.refresh_track_files()
