from __future__ import annotations

from core.database import Database
from core.project_settings import ProjectSettings
from services.track_file_service import (
    TrackAudioSpec,
    TrackFileInventory,
    TrackFileService,
)
from services.track_rename_service import (
    TrackRenamePlan,
    TrackRenameService,
)


class TrackFileWorkspaceController:
    """Own filesystem-facing Tracking services and their derived state."""

    def __init__(self) -> None:
        self.database: Database | None = None
        self.settings = ProjectSettings()
        self.file_service: TrackFileService | None = None
        self.rename_service: TrackRenameService | None = None
        self.inventory = TrackFileInventory()
        self.rename_plan = TrackRenamePlan()

    def configure(self, settings: ProjectSettings | None) -> None:
        self.settings = settings or ProjectSettings()

    def bind_database(self, database: Database | None) -> None:
        self.database = database
        self.rename_plan = TrackRenamePlan()

        if database is None:
            self.file_service = None
            self.rename_service = None
            self.inventory = TrackFileInventory()
            return

        self._rebuild_services()
        self.inventory = self._scan_inventory()

    def refresh(self) -> TrackFileInventory:
        if self.database is None:
            self.file_service = None
            self.rename_service = None
            self.inventory = TrackFileInventory()
            self.rename_plan = TrackRenamePlan()
            return self.inventory

        self._rebuild_services()
        self.inventory = self._scan_inventory()
        return self.inventory

    def build_rename_plan(
        self,
        *,
        talent_id: int,
        episode_number: int | None = None,
        selected_source_path: str | None = None,
    ) -> TrackRenamePlan:
        if self.rename_service is None:
            self.rename_plan = TrackRenamePlan()
            return self.rename_plan

        self.rename_plan = self.rename_service.build_plan(
            self.inventory.rows,
            talent_id=int(talent_id),
            episode_number=(
                int(episode_number)
                if episode_number is not None
                else None
            ),
            selected_source_path=selected_source_path,
        )
        return self.rename_plan

    def execute_rename(self, plan: TrackRenamePlan):
        if self.rename_service is None:
            return []
        return self.rename_service.execute(plan)

    def _rebuild_services(self) -> None:
        assert self.database is not None
        settings = self.settings

        self.file_service = TrackFileService(
            self.database,
            output_folder=settings.stem_output_folder,
            delivery_folder=settings.delivery_folder,
            audio_spec=TrackAudioSpec(
                file_format="WAV",
                sample_rate=int(settings.audio_sample_rate or 48000),
                bit_depth=int(settings.audio_bit_depth or 24),
                channels=int(settings.audio_channels or 1),
            ),
        )
        self.rename_service = TrackRenameService(
            self.database,
            output_folder=settings.stem_output_folder,
        )

    def _scan_inventory(self) -> TrackFileInventory:
        if self.file_service is None:
            return TrackFileInventory()

        try:
            return self.file_service.scan_and_sync()
        except Exception:
            # Filesystem failure must not make the DB Tracking workspace unusable.
            return TrackFileInventory(
                output_folder=self.settings.stem_output_folder,
                delivery_folder=self.settings.delivery_folder,
            )
