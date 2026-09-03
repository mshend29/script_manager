from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from services.project_dashboard_service import ProjectDashboardSnapshot


class DashboardCard(QFrame):
    def __init__(
        self,
        value: str,
        label: str,
        *,
        detail: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("ProjectMetricCard")
        self.setMinimumHeight(92)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)

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

    def set_value(self, value: int | str) -> None:
        self.value_label.setText(str(value))

    def set_detail(self, detail: str) -> None:
        self.detail_label.setText(detail)
        self.detail_label.setVisible(bool(detail))


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
        self.body_layout.setContentsMargins(24, 20, 24, 24)
        self.body_layout.setSpacing(16)
        scroll.setWidget(body)

        self.body_layout.addWidget(self._build_identity_panel())

        self.empty_action_bar = self._build_empty_action_bar()
        self.body_layout.addWidget(self.empty_action_bar)

        metrics_title = QLabel("PROJECT DATA")
        metrics_title.setObjectName("ProjectSectionTitle")
        self.body_layout.addWidget(metrics_title)

        metrics = QGridLayout()
        metrics.setContentsMargins(0, 0, 0, 0)
        metrics.setHorizontalSpacing(10)
        metrics.setVerticalSpacing(10)

        self.episodes_card = DashboardCard("0", "Episodes")
        self.dialogues_card = DashboardCard("0", "Dialogues")
        self.characters_card = DashboardCard("0", "Characters")
        self.talents_card = DashboardCard("0", "Talents")

        for column, card in enumerate(
            (
                self.episodes_card,
                self.dialogues_card,
                self.characters_card,
                self.talents_card,
            )
        ):
            metrics.addWidget(card, 0, column)
            metrics.setColumnStretch(column, 1)

        self.body_layout.addLayout(metrics)

        pipeline_title = QLabel("PRODUCTION PIPELINE")
        pipeline_title.setObjectName("ProjectSectionTitle")
        self.body_layout.addWidget(pipeline_title)

        pipeline = QGridLayout()
        pipeline.setContentsMargins(0, 0, 0, 0)
        pipeline.setHorizontalSpacing(10)
        pipeline.setVerticalSpacing(10)

        self.recording_card = DashboardCard(
            "0",
            "Recording incomplete",
            detail="episode",
        )
        self.stem_card = DashboardCard(
            "0",
            "Ready to stem",
            detail="track scope",
        )
        self.delivery_card = DashboardCard(
            "0",
            "Ready to deliver",
            detail="track scope",
        )
        self.delivered_card = DashboardCard(
            "0 / 0",
            "Delivered",
            detail="track scope",
        )
        self.revision_card = DashboardCard(
            "0",
            "Revision",
            detail="needs rework",
        )

        for column, card in enumerate(
            (
                self.recording_card,
                self.stem_card,
                self.delivery_card,
                self.delivered_card,
                self.revision_card,
            )
        ):
            pipeline.addWidget(card, 0, column)
            pipeline.setColumnStretch(column, 1)

        self.body_layout.addLayout(pipeline)

        lower = QGridLayout()
        lower.setContentsMargins(0, 0, 0, 0)
        lower.setHorizontalSpacing(12)
        lower.setVerticalSpacing(12)
        lower.setColumnStretch(0, 3)
        lower.setColumnStretch(1, 2)

        self.attention_panel = self._build_attention_panel()
        lower.addWidget(self.attention_panel, 0, 0)

        self.activity_frame = self._build_activity_panel()
        lower.addWidget(self.activity_frame, 0, 1)

        self.body_layout.addLayout(lower)
        self.body_layout.addStretch(1)

        # Compatibility counters retained for callers/tests while their visual
        # meaning now lives in the pipeline and Needs Attention panels.
        self.review_card = DashboardCard("0", "Needs Review")
        self.warning_card = DashboardCard("0", "Output Warnings")
        self.review_card.hide()
        self.warning_card.hide()

        self.reset_view()

    def _build_identity_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("ProjectIdentityCard")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)

        identity = QVBoxLayout()
        identity.setContentsMargins(0, 0, 0, 0)
        identity.setSpacing(2)

        self.project_name = QLabel("No project open")
        self.project_name.setObjectName("ProjectIdentityName")
        self.project_name.setMinimumWidth(0)
        self.project_name.setWordWrap(True)
        identity.addWidget(self.project_name)

        self.project_identity = QLabel("Project belum dibuka")
        self.project_identity.setObjectName("ProjectIdentityMeta")
        self.project_identity.setMinimumWidth(0)
        self.project_identity.setWordWrap(True)
        identity.addWidget(self.project_identity)

        top.addLayout(identity, 1)

        self.health_badge = QLabel("NO PROJECT")
        self.health_badge.setObjectName("ProjectHealthBadge")
        self.health_badge.setProperty("healthState", "NEUTRAL")
        top.addWidget(
            self.health_badge,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        layout.addLayout(top)

        metadata = QGridLayout()
        metadata.setContentsMargins(0, 4, 0, 0)
        metadata.setHorizontalSpacing(18)
        metadata.setVerticalSpacing(5)
        metadata.setColumnStretch(1, 1)
        metadata.setColumnStretch(3, 1)

        self.project_location = QLabel("Project file: -")
        self.source_path = QLabel("Source folder: -")
        self.start_date = QLabel("Start date: -")
        self.last_refresh = QLabel("Last sync: -")
        self.drive_status = QLabel("Main drive: -")

        rows = (
            ("PROJECT FILE", self.project_location),
            ("SOURCE FOLDER", self.source_path),
            ("START DATE", self.start_date),
            ("LAST SYNC", self.last_refresh),
            ("MAIN DRIVE", self.drive_status),
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
        info_layout = QVBoxLayout(self.info)
        info_layout.setContentsMargins(12, 9, 12, 9)
        info_layout.setSpacing(1)

        self.info_title = QLabel("No project open")
        self.info_title.setObjectName("ProjectHealthTitle")
        self.info_text = QLabel(
            "Buat project baru atau buka project yang sudah ada."
        )
        self.info_text.setObjectName("ProjectHealthText")
        self.info_text.setWordWrap(True)

        info_layout.addWidget(self.info_title)
        info_layout.addWidget(self.info_text)
        layout.addWidget(self.info)

        return panel

    def _build_empty_action_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("ProjectEmptyActions")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        hint = QLabel(
            "Mulai dengan membuat project baru atau membuka file .smproj."
        )
        hint.setObjectName("ProjectEmptyHint")
        layout.addWidget(hint, 1)

        self.new_button = QPushButton("New Project")
        self.new_button.setProperty("primary", True)
        layout.addWidget(self.new_button)

        self.open_button = QPushButton("Open Project")
        self.open_button.setProperty("secondary", True)
        layout.addWidget(self.open_button)

        self.open_recent_button = QPushButton("Open Recent")
        self.open_recent_button.setProperty("secondary", True)
        self.open_recent_button.clicked.connect(
            lambda: self.action_requested.emit("project.open_recent")
        )
        layout.addWidget(self.open_recent_button)

        self.recover_button = QPushButton("Recover Project")
        self.recover_button.setProperty("secondary", True)
        self.recover_button.clicked.connect(
            lambda: self.action_requested.emit("project.recover")
        )
        layout.addWidget(self.recover_button)

        return bar

    def _build_attention_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("ProjectPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(9)

        title = QLabel("NEEDS ATTENTION")
        title.setObjectName("ProjectSectionTitle")
        layout.addWidget(title)

        helper = QLabel(
            "Pekerjaan yang memerlukan keputusan atau tindakan operator."
        )
        helper.setObjectName("ProjectSectionHelper")
        helper.setWordWrap(True)
        layout.addWidget(helper)

        self.action_holder = QWidget()
        self.action_layout = QGridLayout(self.action_holder)
        self.action_layout.setContentsMargins(0, 4, 0, 0)
        self.action_layout.setHorizontalSpacing(8)
        self.action_layout.setVerticalSpacing(8)
        layout.addWidget(self.action_holder)

        return panel

    def _build_activity_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("ProjectPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(7)

        title = QLabel("RECENT ACTIVITY")
        title.setObjectName("ProjectSectionTitle")
        layout.addWidget(title)

        helper = QLabel("Perubahan terbaru yang tercatat di audit project.")
        helper.setObjectName("ProjectSectionHelper")
        helper.setWordWrap(True)
        layout.addWidget(helper)

        self.activity_layout = QVBoxLayout()
        self.activity_layout.setContentsMargins(0, 4, 0, 0)
        self.activity_layout.setSpacing(0)
        layout.addLayout(self.activity_layout)

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
            else "Project metadata"
        )
        self.drive_status.setText(
            "Main drive: Configured"
            if drive_configured
            else "Main drive: Not configured"
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

        self._clear_layout(self.action_layout)
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
                self.action_layout.addWidget(
                    button,
                    index // 2,
                    index % 2,
                )
        else:
            clean = QLabel("✓ Tidak ada action penting yang tertunda.")
            clean.setObjectName("ProjectCleanState")
            self.action_layout.addWidget(clean, 0, 0, 1, 2)

        self._clear_layout(self.activity_layout)
        if snapshot.recent_activity:
            for entry in snapshot.recent_activity:
                row = QFrame()
                row.setObjectName("ProjectActivityRow")
                row_layout = QVBoxLayout(row)
                row_layout.setContentsMargins(0, 8, 0, 8)
                row_layout.setSpacing(2)

                summary = QLabel(entry.summary)
                summary.setObjectName("ProjectActivitySummary")
                summary.setWordWrap(True)

                meta = QLabel(
                    f"{entry.created_at}  •  {entry.event_type} / {entry.action}"
                )
                meta.setObjectName("ProjectActivityMeta")
                meta.setWordWrap(True)

                row_layout.addWidget(summary)
                row_layout.addWidget(meta)
                self.activity_layout.addWidget(row)
        else:
            label = QLabel("Belum ada audit activity.")
            label.setObjectName("ProjectSectionHelper")
            self.activity_layout.addWidget(label)

        self._update_health(snapshot)

    def _update_health(
        self,
        snapshot: ProjectDashboardSnapshot,
    ) -> None:
        if snapshot.system_errors:
            state = "ERROR"
            text = "SYSTEM ERROR"
        elif snapshot.actions:
            state = "ATTENTION"
            text = "NEEDS ATTENTION"
        else:
            state = "HEALTHY"
            text = "HEALTHY"

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
        self.project_name.setText("No project open")
        self.project_identity.setText("Project belum dibuka")
        self.project_location.setText("Project file: -")
        self.source_path.setText("Source folder: -")
        self.start_date.setText("Start date: -")
        self.last_refresh.setText("Last sync: -")
        self.drive_status.setText("Main drive: -")
        self.empty_action_bar.show()

        self.set_counts({})
        self.set_dashboard(ProjectDashboardSnapshot())

        self.health_badge.setProperty("healthState", "NEUTRAL")
        self.health_badge.setText("NO PROJECT")
        self.health_badge.style().unpolish(self.health_badge)
        self.health_badge.style().polish(self.health_badge)

        self.info_title.setText("No project open")
        self.info_text.setText(
            "Buat project baru atau buka project yang sudah ada."
        )
