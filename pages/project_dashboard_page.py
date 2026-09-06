from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.theme import COLORS, RADII
from services.project_dashboard_service import ProjectDashboardSnapshot


class DashboardCard(QFrame):
    """Small dashboard value surface used inside larger visual compositions."""

    def __init__(
        self,
        value: str,
        label: str,
        *,
        detail: str = "",
        role: str = "metric",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("ProjectMetricCard")
        self.setProperty("dashboardRole", role)
        self.setProperty("pipelineState", "IDLE")
        self.setMinimumHeight(72 if role == "metric" else 88)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(1)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("ProjectMetricValue")

        self.label_widget = QLabel(label)
        self.label_widget.setObjectName("ProjectMetricLabel")
        self.label_widget.setWordWrap(True)

        self.detail_label = QLabel(detail)
        self.detail_label.setObjectName("ProjectMetricDetail")
        self.detail_label.setWordWrap(True)
        self.detail_label.setVisible(bool(detail))

        layout.addWidget(self.value_label)
        layout.addWidget(self.label_widget)
        layout.addWidget(self.detail_label)
        layout.addStretch(1)

        # Project dashboard intentionally uses one large composition instead of
        # a matrix of bordered cards. Theme tokens stay centralized even though
        # these role-specific overrides are local to this workspace.
        self.setStyleSheet(
            f"""
            QFrame#ProjectMetricCard {{
                border: none;
                background: transparent;
                border-radius: {RADII['md']}px;
            }}
            QFrame#ProjectMetricCard[dashboardRole="pipeline"] {{
                padding: 2px;
            }}
            QFrame#ProjectMetricCard[dashboardRole="pipeline"][pipelineState="ACTIVE"] {{
                background: {COLORS['accent_soft']};
            }}
            QFrame#ProjectMetricCard[dashboardRole="pipeline"][pipelineState="DONE"] {{
                background: {COLORS['recorded_soft']};
            }}
            QFrame#ProjectMetricCard[dashboardRole="revision"][pipelineState="REVISION"] {{
                background: {COLORS['revision_soft']};
            }}
            """
        )

    def set_value(self, value: int | str) -> None:
        self.value_label.setText(str(value))

    def set_detail(self, detail: str) -> None:
        self.detail_label.setText(detail)
        self.detail_label.setVisible(bool(detail))

    def set_pipeline_state(self, state: str) -> None:
        self.setProperty("pipelineState", str(state or "IDLE").upper())
        self.style().unpolish(self)
        self.style().polish(self)


class ProjectPage(QWidget):
    action_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("ProjectWorkspace")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("ProjectScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        root.addWidget(scroll)

        body = QWidget()
        body.setObjectName("ProjectBody")
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(28, 24, 28, 30)
        self.body_layout.setSpacing(18)
        scroll.setWidget(body)

        self.body_layout.addWidget(self._build_identity_panel())

        self.empty_action_bar = self._build_empty_action_bar()
        self.body_layout.addWidget(self.empty_action_bar)

        dashboard_columns = QGridLayout()
        dashboard_columns.setObjectName("ProjectDashboardColumns")
        dashboard_columns.setContentsMargins(0, 0, 0, 0)
        dashboard_columns.setHorizontalSpacing(22)
        dashboard_columns.setVerticalSpacing(0)
        # Keep the production side clearly dominant while leaving enough room
        # for attention/activity copy at common desktop sizes (~65 / 35).
        dashboard_columns.setColumnStretch(0, 13)
        dashboard_columns.setColumnStretch(1, 7)

        production_column = QWidget()
        production_column.setObjectName("ProjectProductionColumn")
        production_layout = QVBoxLayout(production_column)
        production_layout.setContentsMargins(0, 0, 0, 0)
        production_layout.setSpacing(12)

        data_header = QHBoxLayout()
        data_header.setContentsMargins(2, 0, 2, 0)
        data_title = QLabel('DATA PROYEK')
        data_title.setObjectName("ProjectSectionTitle")
        data_header.addWidget(data_title)
        data_header.addStretch(1)
        data_hint = QLabel('Ringkasan cepat database naskah saat ini')
        data_hint.setObjectName("ProjectSectionHelper")
        data_header.addWidget(data_hint)
        production_layout.addLayout(data_header)
        production_layout.addWidget(self._build_metric_strip())
        production_layout.addSpacing(4)

        pipeline_title = QLabel('ALUR PRODUKSI')
        pipeline_title.setObjectName("ProjectSectionTitle")
        production_layout.addWidget(pipeline_title)

        pipeline_helper = QLabel(
            "Ikuti alur kerja dari Rekaman ke Stem hingga Setoran akhir. "
            "Revisi tampil sebagai loop pengerjaan ulang, bukan tahap akhir terpisah."
        )
        pipeline_helper.setObjectName("ProjectSectionHelper")
        pipeline_helper.setWordWrap(True)
        production_layout.addWidget(pipeline_helper)
        production_layout.addWidget(self._build_pipeline_rail())
        production_layout.addStretch(1)

        monitoring_column = QWidget()
        monitoring_column.setObjectName("ProjectMonitoringColumn")
        monitoring_layout = QVBoxLayout(monitoring_column)
        monitoring_layout.setContentsMargins(0, 0, 0, 0)
        monitoring_layout.setSpacing(18)

        self.attention_panel = self._build_attention_panel()
        monitoring_layout.addWidget(self.attention_panel)

        self.activity_frame = self._build_activity_panel()
        monitoring_layout.addWidget(self.activity_frame, 1)

        dashboard_columns.addWidget(production_column, 0, 0)
        dashboard_columns.addWidget(monitoring_column, 0, 1)
        dashboard_columns.setRowStretch(0, 1)
        self.body_layout.addLayout(dashboard_columns, 1)
        self.body_layout.addStretch(1)

        # Compatibility counters retained for callers/tests while their visual
        # meaning now lives in the production flow and Needs Attention list.
        self.review_card = DashboardCard("0", 'Perlu Ditinjau')
        self.warning_card = DashboardCard("0", 'Peringatan Output')
        self.review_card.hide()
        self.warning_card.hide()

        self.reset_view()

    def _build_identity_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("ProjectIdentityCard")
        panel.setStyleSheet(
            f"""
            QFrame#ProjectIdentityCard {{
                background: {COLORS['accent_soft']};
                border: 1px solid {COLORS['border']};
                border-radius: {RADII['lg']}px;
            }}
            """
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(13)

        eyebrow = QLabel('PROYEK AKTIF')
        eyebrow.setObjectName("ProjectMetaKey")
        layout.addWidget(eyebrow)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(14)

        identity = QVBoxLayout()
        identity.setContentsMargins(0, 0, 0, 0)
        identity.setSpacing(3)

        self.project_name = QLabel('Belum ada proyek terbuka')
        self.project_name.setObjectName("ProjectIdentityName")
        self.project_name.setMinimumWidth(0)
        self.project_name.setWordWrap(True)
        identity.addWidget(self.project_name)

        self.project_identity = QLabel('Proyek belum dibuka')
        self.project_identity.setObjectName("ProjectIdentityMeta")
        self.project_identity.setMinimumWidth(0)
        self.project_identity.setWordWrap(True)
        identity.addWidget(self.project_identity)

        top.addLayout(identity, 1)

        self.health_badge = QLabel('BELUM ADA PROYEK')
        self.health_badge.setObjectName("ProjectHealthBadge")
        self.health_badge.setProperty("healthState", "NEUTRAL")
        top.addWidget(
            self.health_badge,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        layout.addLayout(top)

        metadata = QGridLayout()
        metadata.setContentsMargins(0, 5, 0, 0)
        metadata.setHorizontalSpacing(20)
        metadata.setVerticalSpacing(8)
        metadata.setColumnStretch(1, 1)
        metadata.setColumnStretch(3, 1)

        self.project_location = QLabel('File proyek: -')
        self.source_path = QLabel('Folder sumber: -')
        self.start_date = QLabel('Tanggal mulai: -')
        self.last_refresh = QLabel('Sinkron terakhir: -')
        self.drive_status = QLabel('Drive utama: -')

        rows = (
            ('FILE PROYEK', self.project_location),
            ('FOLDER SUMBER', self.source_path),
            ('TANGGAL MULAI', self.start_date),
            ('SINKRON TERAKHIR', self.last_refresh),
            ('DRIVE UTAMA', self.drive_status),
        )

        for index, (key, value) in enumerate(rows):
            key_label = QLabel(key)
            key_label.setObjectName("ProjectMetaKey")
            value.setObjectName("ProjectMetaValue")
            value.setWordWrap(True)

            row = index // 2
            column = (index % 2) * 2
            metadata.addWidget(
                key_label,
                row,
                column,
                Qt.AlignmentFlag.AlignTop,
            )
            metadata.addWidget(value, row, column + 1)

        layout.addLayout(metadata)

        self.info = QFrame()
        self.info.setObjectName("ProjectHealthBanner")
        self.info.setStyleSheet(
            f"""
            QFrame#ProjectHealthBanner {{
                background: {COLORS['surface']};
                border: none;
                border-radius: {RADII['md']}px;
            }}
            """
        )
        info_layout = QHBoxLayout(self.info)
        info_layout.setContentsMargins(12, 9, 12, 9)
        info_layout.setSpacing(8)

        self.info_title = QLabel('Belum ada proyek terbuka')
        self.info_title.setObjectName("ProjectHealthTitle")
        info_layout.addWidget(self.info_title)

        info_separator = QLabel("•")
        info_separator.setObjectName("ProjectSectionHelper")
        info_layout.addWidget(info_separator)

        self.info_text = QLabel(
            'Buat proyek baru atau buka proyek yang sudah ada.'
        )
        self.info_text.setObjectName("ProjectHealthText")
        self.info_text.setWordWrap(True)
        info_layout.addWidget(self.info_text, 1)
        layout.addWidget(self.info)

        return panel

    def _build_metric_strip(self) -> QFrame:
        strip = QFrame()
        strip.setObjectName("ProjectMetricStrip")
        strip.setStyleSheet(
            f"""
            QFrame#ProjectMetricStrip {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: {RADII['lg']}px;
            }}
            QFrame#ProjectMetricSeparator {{
                background: {COLORS['border']};
                border: none;
            }}
            """
        )

        layout = QHBoxLayout(strip)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        self.episodes_card = DashboardCard("0", 'Episode', role="metric")
        self.dialogues_card = DashboardCard("0", 'Dialog', role="metric")
        self.characters_card = DashboardCard("0", 'Tokoh', role="metric")
        self.talents_card = DashboardCard("0", 'Talent', role="metric")

        cards = (
            self.episodes_card,
            self.dialogues_card,
            self.characters_card,
            self.talents_card,
        )
        for index, card in enumerate(cards):
            layout.addWidget(card, 1)
            if index < len(cards) - 1:
                separator = QFrame()
                separator.setObjectName("ProjectMetricSeparator")
                separator.setFixedWidth(1)
                separator.setMinimumHeight(46)
                layout.addWidget(separator)

        return strip

    def _build_pipeline_rail(self) -> QFrame:
        rail = QFrame()
        rail.setObjectName("ProjectPipelineRail")
        rail.setStyleSheet(
            f"""
            QFrame#ProjectPipelineRail {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: {RADII['lg']}px;
            }}
            QLabel#ProjectPipelineArrow {{
                color: {COLORS['text_muted']};
                font-size: 16pt;
                font-weight: 700;
            }}
            QFrame#ProjectRevisionLoop {{
                background: {COLORS['surface_subtle']};
                border: 1px solid {COLORS['border']};
                border-radius: {RADII['md']}px;
            }}
            """
        )

        root = QVBoxLayout(rail)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        stages = QHBoxLayout()
        stages.setContentsMargins(0, 0, 0, 0)
        stages.setSpacing(8)

        self.recording_card = DashboardCard(
            "0",
            'REKAMAN',
            detail='episode belum lengkap',
            role="pipeline",
        )
        self.stem_card = DashboardCard(
            "0",
            "STEM",
            detail='terekam / menunggu output',
            role="pipeline",
        )
        self.delivery_card = DashboardCard(
            "0",
            'ANTREAN SETORAN',
            detail='selesai stem / menunggu setoran',
            role="pipeline",
        )
        self.delivered_card = DashboardCard(
            "0 / 0",
            'DISETOR',
            detail='lingkup track',
            role="pipeline",
        )

        stage_cards = (
            self.recording_card,
            self.stem_card,
            self.delivery_card,
            self.delivered_card,
        )
        for index, card in enumerate(stage_cards):
            stages.addWidget(card, 1)
            if index < len(stage_cards) - 1:
                arrow = QLabel("→")
                arrow.setObjectName("ProjectPipelineArrow")
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                stages.addWidget(arrow)
        root.addLayout(stages)

        progress_row = QHBoxLayout()
        progress_row.setContentsMargins(8, 0, 8, 0)
        progress_row.setSpacing(10)

        self.delivery_progress = QProgressBar()
        self.delivery_progress.setObjectName("ProjectDeliveryProgress")
        self.delivery_progress.setRange(0, 1)
        self.delivery_progress.setValue(0)
        self.delivery_progress.setTextVisible(False)
        progress_row.addWidget(self.delivery_progress, 1)

        self.pipeline_progress_text = QLabel('Belum ada track yang diharapkan')
        self.pipeline_progress_text.setObjectName("ProjectMetricDetail")
        progress_row.addWidget(self.pipeline_progress_text)
        root.addLayout(progress_row)

        revision_loop = QFrame()
        revision_loop.setObjectName("ProjectRevisionLoop")
        revision_layout = QHBoxLayout(revision_loop)
        revision_layout.setContentsMargins(10, 6, 10, 6)
        revision_layout.setSpacing(8)

        revision_label = QLabel('↺  LOOP REVISI')
        revision_label.setObjectName("ProjectMetricLabel")
        revision_layout.addWidget(revision_label)

        revision_help = QLabel(
            'Pengerjaan ulang kembali ke Stem, lalu dilanjutkan lagi ke Setoran.'
        )
        revision_help.setObjectName("ProjectMetricDetail")
        revision_help.setWordWrap(True)
        revision_layout.addWidget(revision_help, 1)

        self.revision_card = DashboardCard(
            "0",
            'Revisi',
            detail='perlu dikerjakan ulang',
            role="revision",
        )
        self.revision_card.setMaximumWidth(150)
        self.revision_card.setMinimumHeight(54)
        revision_layout.addWidget(self.revision_card)
        root.addWidget(revision_loop)

        return rail

    def _build_empty_action_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("ProjectEmptyActions")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        hint = QLabel(
            'Mulai dengan membuat proyek baru atau membuka file .smproj.'
        )
        hint.setObjectName("ProjectEmptyHint")
        layout.addWidget(hint, 1)

        self.new_button = QPushButton('Proyek Baru')
        self.new_button.setProperty("primary", True)
        layout.addWidget(self.new_button)

        self.open_button = QPushButton('Buka Proyek')
        self.open_button.setProperty("secondary", True)
        layout.addWidget(self.open_button)

        self.open_recent_button = QPushButton('Buka Terbaru')
        self.open_recent_button.setProperty("secondary", True)
        self.open_recent_button.clicked.connect(
            lambda: self.action_requested.emit("project.open_recent")
        )
        layout.addWidget(self.open_recent_button)

        self.recover_button = QPushButton('Pulihkan Proyek')
        self.recover_button.setProperty("secondary", True)
        self.recover_button.clicked.connect(
            lambda: self.action_requested.emit("project.recover")
        )
        layout.addWidget(self.recover_button)

        return bar

    def _build_attention_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("ProjectPanel")
        panel.setStyleSheet(
            f"""
            QFrame#ProjectPanel {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: {RADII['lg']}px;
            }}
            """
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 15, 18, 16)
        layout.setSpacing(9)

        heading = QHBoxLayout()
        title = QLabel('PERLU PERHATIAN')
        title.setObjectName("ProjectSectionTitle")
        heading.addWidget(title)
        heading.addStretch(1)
        self.attention_count = QLabel("0")
        self.attention_count.setObjectName("ProjectHealthBadge")
        self.attention_count.setProperty("healthState", "NEUTRAL")
        heading.addWidget(self.attention_count)
        layout.addLayout(heading)

        helper = QLabel(
            'Hanya item yang membutuhkan keputusan operator atau tindakan berikutnya yang tampil di sini.'
        )
        helper.setObjectName("ProjectSectionHelper")
        helper.setWordWrap(True)
        layout.addWidget(helper)

        self.action_holder = QWidget()
        self.action_layout = QGridLayout(self.action_holder)
        self.action_layout.setContentsMargins(0, 5, 0, 0)
        self.action_layout.setHorizontalSpacing(0)
        self.action_layout.setVerticalSpacing(7)
        layout.addWidget(self.action_holder)
        layout.addStretch(1)

        return panel

    def _build_activity_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("ProjectActivityPanel")
        panel.setStyleSheet(
            f"""
            QFrame#ProjectActivityPanel {{
                background: transparent;
                border: none;
            }}
            QLabel#ProjectActivityDot {{
                color: {COLORS['accent']};
                font-size: 15pt;
                font-weight: 700;
            }}
            """
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 2, 4, 4)
        layout.setSpacing(7)

        title = QLabel('AKTIVITAS TERBARU')
        title.setObjectName("ProjectSectionTitle")
        layout.addWidget(title)

        helper = QLabel('Perubahan penting terbaru yang tercatat pada proyek ini.')
        helper.setObjectName("ProjectSectionHelper")
        helper.setWordWrap(True)
        layout.addWidget(helper)

        self.activity_layout = QVBoxLayout()
        self.activity_layout.setContentsMargins(0, 5, 0, 0)
        self.activity_layout.setSpacing(0)
        layout.addLayout(self.activity_layout)
        layout.addStretch(1)

        return panel

    def set_project_metadata(
        self,
        *,
        project_code: str = "",
        client_name: str = "",
        drive_configured: bool = False,
    ) -> None:
        identity_parts = [
            part
            for part in (
                str(project_code or "").strip(),
                str(client_name or "").strip(),
            )
            if part
        ]
        self.project_identity.setText(
            "  •  ".join(identity_parts)
            if identity_parts
            else 'Metadata proyek'
        )
        self.drive_status.setText(
            "Drive utama: Dikonfigurasi"
            if drive_configured
            else "Drive utama: Belum dikonfigurasi"
        )
        self.empty_action_bar.hide()

    def set_counts(self, counts: dict[str, int]) -> None:
        self.episodes_card.set_value(counts.get("episodes", 0))
        self.characters_card.set_value(counts.get("characters", 0))
        self.talents_card.set_value(counts.get("talents", 0))
        self.dialogues_card.set_value(counts.get("dialogues", 0))

    def set_dashboard(self, snapshot: ProjectDashboardSnapshot) -> None:
        self.review_card.set_value(snapshot.needs_review)
        self.recording_card.set_value(snapshot.recording_episodes)
        self.stem_card.set_value(snapshot.recorded_waiting_stem)
        self.delivery_card.set_value(snapshot.stemmed_waiting_delivery)
        self.delivered_card.set_value(
            f"{snapshot.delivered_tracks} / {snapshot.total_tracks}"
        )
        self.revision_card.set_value(snapshot.revisions)
        self.warning_card.set_value(snapshot.file_warnings)

        self.recording_card.set_pipeline_state(
            "ACTIVE" if snapshot.recording_episodes else "DONE"
        )
        self.stem_card.set_pipeline_state(
            "ACTIVE" if snapshot.recorded_waiting_stem else "DONE"
        )
        self.delivery_card.set_pipeline_state(
            "ACTIVE" if snapshot.stemmed_waiting_delivery else "DONE"
        )
        delivered_done = (
            snapshot.total_tracks > 0
            and snapshot.delivered_tracks >= snapshot.total_tracks
        )
        self.delivered_card.set_pipeline_state(
            "DONE" if delivered_done else "ACTIVE"
        )
        self.revision_card.set_pipeline_state(
            "REVISION" if snapshot.revisions else "IDLE"
        )

        total_tracks = max(0, int(snapshot.total_tracks))
        delivered_tracks = max(0, int(snapshot.delivered_tracks))
        progress_max = max(total_tracks, 1)
        self.delivery_progress.setRange(0, progress_max)
        self.delivery_progress.setValue(min(delivered_tracks, progress_max))
        if total_tracks:
            percent = round((delivered_tracks / total_tracks) * 100)
            self.pipeline_progress_text.setText(
                f"{delivered_tracks}/{total_tracks} track disetor  •  {percent}%"
            )
        else:
            self.pipeline_progress_text.setText('Belum ada track yang diharapkan')

        self._clear_layout(self.action_layout)
        self.attention_count.setText(str(len(snapshot.actions)))
        attention_state = "ATTENTION" if snapshot.actions else "HEALTHY"
        self.attention_count.setProperty("healthState", attention_state)
        self.attention_count.style().unpolish(self.attention_count)
        self.attention_count.style().polish(self.attention_count)

        if snapshot.actions:
            for index, action in enumerate(snapshot.actions):
                button = QPushButton(
                    f"{action.count}  {action.label}\n{action.detail}"
                )
                button.setProperty("attentionAction", True)
                button.setProperty(
                    "dashboardSeverity",
                    str(action.severity or "INFO").upper(),
                )
                button.setMinimumHeight(58)
                button.clicked.connect(
                    lambda checked=False, key=action.key:
                    self.action_requested.emit(key)
                )
                # One action per row keeps this section closer to a work queue
                # than an ERP-style tile dashboard.
                self.action_layout.addWidget(button, index, 0)
        else:
            clean = QLabel("✓ Tidak ada tindakan penting yang tertunda.")
            clean.setObjectName("ProjectCleanState")
            self.action_layout.addWidget(clean, 0, 0)

        self._clear_layout(self.activity_layout)
        if snapshot.recent_activity:
            for entry in snapshot.recent_activity:
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 6, 0, 6)
                row_layout.setSpacing(8)

                dot = QLabel("•")
                dot.setObjectName("ProjectActivityDot")
                dot.setAlignment(
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
                )
                dot.setFixedWidth(14)
                row_layout.addWidget(dot)

                text_layout = QVBoxLayout()
                text_layout.setContentsMargins(0, 0, 0, 0)
                text_layout.setSpacing(2)

                summary = QLabel(entry.summary)
                summary.setObjectName("ProjectActivitySummary")
                summary.setWordWrap(True)

                meta = QLabel(
                    f"{entry.created_at}  •  {entry.event_type} / {entry.action}"
                )
                meta.setObjectName("ProjectActivityMeta")
                meta.setWordWrap(True)

                text_layout.addWidget(summary)
                text_layout.addWidget(meta)
                row_layout.addLayout(text_layout, 1)
                self.activity_layout.addWidget(row)
        else:
            label = QLabel("Belum ada aktivitas audit.")
            label.setObjectName("ProjectSectionHelper")
            self.activity_layout.addWidget(label)

        self._update_health(snapshot)

    def _update_health(
        self,
        snapshot: ProjectDashboardSnapshot,
    ) -> None:
        if snapshot.system_errors:
            state = "ERROR"
            text = 'ERROR SISTEM'
        elif snapshot.actions:
            state = "ATTENTION"
            text = 'PERLU PERHATIAN'
        else:
            state = "HEALTHY"
            text = "SEHAT"

        self.health_badge.setProperty("healthState", state)
        self.health_badge.setText(text)
        self.health_badge.style().unpolish(self.health_badge)
        self.health_badge.style().polish(self.health_badge)

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                ProjectPage._clear_layout(child_layout)

    def reset_view(self) -> None:
        self.project_name.setText('Belum ada proyek terbuka')
        self.project_identity.setText('Proyek belum dibuka')
        self.project_location.setText('File proyek: -')
        self.source_path.setText('Folder sumber: -')
        self.start_date.setText('Tanggal mulai: -')
        self.last_refresh.setText('Sinkron terakhir: -')
        self.drive_status.setText('Drive utama: -')
        self.empty_action_bar.show()

        self.set_counts({})
        self.set_dashboard(ProjectDashboardSnapshot())

        self.health_badge.setProperty("healthState", "NEUTRAL")
        self.health_badge.setText('BELUM ADA PROYEK')
        self.health_badge.style().unpolish(self.health_badge)
        self.health_badge.style().polish(self.health_badge)

        self.info_title.setText('Belum ada proyek terbuka')
        self.info_text.setText(
            'Buat proyek baru atau buka proyek yang sudah ada.'
        )
