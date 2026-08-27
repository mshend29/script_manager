from __future__ import annotations

from dataclasses import dataclass, field

from core.database import Database
from core.project_settings import ProjectSettings
from services.audit_service import AuditEntry, AuditService
from services.track_file_service import (
    TrackAudioSpec,
    TrackFileService,
)
from services.validation_service import ValidationService


@dataclass(frozen=True)
class DashboardAction:
    key: str
    label: str
    count: int
    detail: str
    severity: str = "INFO"


@dataclass
class ProjectDashboardSnapshot:
    needs_review: int = 0
    system_errors: int = 0
    workflow_warnings: int = 0
    recording_episodes: int = 0
    recorded_waiting_stem: int = 0
    stemmed_waiting_delivery: int = 0
    revisions: int = 0
    file_warnings: int = 0
    delivered_tracks: int = 0
    total_tracks: int = 0
    actions: list[DashboardAction] = field(default_factory=list)
    recent_activity: list[AuditEntry] = field(default_factory=list)


class ProjectDashboardService:
    def __init__(
        self,
        database: Database,
        settings: ProjectSettings,
    ):
        self.database = database
        self.settings = settings

    def build(self) -> ProjectDashboardSnapshot:
        snapshot = ProjectDashboardSnapshot()

        issues = ValidationService(self.database).validate()
        summary = ValidationService(self.database).summarize(issues)
        snapshot.needs_review = int(summary.needs_review)
        snapshot.system_errors = int(summary.system_errors)
        snapshot.workflow_warnings = int(summary.workflow_warnings)

        with self.database.connect() as connection:
            recording = connection.execute(
                """
                SELECT COUNT(DISTINCT e.id) AS total
                FROM dialogues AS d
                JOIN episodes AS e
                  ON e.id = d.episode_id
                 AND e.is_active = 1
                JOIN dialog_cast AS dc
                  ON dc.dialogue_id = d.id
                 AND dc.talent_id IS NOT NULL
                LEFT JOIN recording_status AS rs
                  ON rs.dialogue_id = d.id
                WHERE d.is_active = 1
                  AND COALESCE(rs.is_recorded, 0) = 0
                """
            ).fetchone()
            snapshot.recording_episodes = int(
                recording["total"] if recording else 0
            )

            revision = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM stem_status
                WHERE status = 'REVISION'
                """
            ).fetchone()
            snapshot.revisions = int(
                revision["total"] if revision else 0
            )

        try:
            inventory = TrackFileService(
                self.database,
                output_folder=self.settings.stem_output_folder,
                delivery_folder=self.settings.delivery_folder,
                audio_spec=TrackAudioSpec(
                    file_format="WAV",
                    sample_rate=int(
                        self.settings.audio_sample_rate or 48000
                    ),
                    bit_depth=int(
                        self.settings.audio_bit_depth or 24
                    ),
                    channels=int(
                        self.settings.audio_channels or 1
                    ),
                ),
            ).scan_and_sync()
        except Exception:
            inventory = None

        if inventory is not None:
            snapshot.total_tracks = len(inventory.rows)
            snapshot.delivered_tracks = sum(
                1 for row in inventory.rows if row.delivered.valid
            )
            snapshot.recorded_waiting_stem = sum(
                1
                for row in inventory.rows
                if (
                    row.total_dialogues > 0
                    and row.recorded_dialogues == row.total_dialogues
                    and not row.output.valid
                    and not row.delivered.valid
                )
            )
            snapshot.stemmed_waiting_delivery = sum(
                1
                for row in inventory.rows
                if (
                    row.output.valid
                    and not row.delivered.valid
                )
            )
            snapshot.file_warnings = (
                len(inventory.warnings)
                + sum(len(row.warnings) for row in inventory.rows)
            )

        actions: list[DashboardAction] = []

        def add(
            key: str,
            label: str,
            count: int,
            detail: str,
            severity: str = "INFO",
        ) -> None:
            if int(count) <= 0:
                return
            actions.append(
                DashboardAction(
                    key=key,
                    label=label,
                    count=int(count),
                    detail=detail,
                    severity=severity,
                )
            )

        add(
            "system_errors",
            "System Errors",
            snapshot.system_errors,
            "Buka DATA → Validation dan selesaikan error struktur.",
            "ERROR",
        )
        add(
            "needs_review",
            "Needs Review",
            snapshot.needs_review,
            "Keputusan manusia masih diperlukan di DATA → Unresolved.",
            "WARNING",
        )
        add(
            "revision",
            "Revision",
            snapshot.revisions,
            "Scope recording yang sedang ditandai Revision.",
            "ERROR",
        )
        add(
            "recording",
            "Recording Incomplete",
            snapshot.recording_episodes,
            "Episode masih memiliki line yang belum checked.",
        )
        add(
            "ready_to_stem",
            "Recorded → Stem",
            snapshot.recorded_waiting_stem,
            "Expected track sudah Recorded tetapi file output belum ada.",
        )
        add(
            "pending_delivery",
            "Stemmed → Delivery",
            snapshot.stemmed_waiting_delivery,
            "Stem valid tersedia tetapi belum ditemukan di SETORAN.",
        )
        add(
            "file_warnings",
            "Output Warnings",
            snapshot.file_warnings,
            "Periksa format/nama/mismatch file di TRACKING.",
            "WARNING",
        )
        add(
            "workflow_warnings",
            "Workflow Warnings",
            snapshot.workflow_warnings,
            "Buka DATA → Validation untuk workflow warning.",
            "WARNING",
        )

        snapshot.actions = actions
        snapshot.recent_activity = AuditService(self.database).recent(8)
        return snapshot
