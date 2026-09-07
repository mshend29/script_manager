from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.project import Project
from core.project_manager import ProjectManager
from core.project_settings import ProjectSettings
from import_engine.source_sync import (
    PreparedSourceSyncInput,
    ProgressCallback,
    SourceSyncEngine,
    SourceSyncError,
    SourceSyncProgress,
    SourceSyncReport,
)
from services.source_preflight_service import SourcePreflightReport


class InitialProjectCreationError(RuntimeError):
    pass


class InitialProjectSourceChangedError(InitialProjectCreationError):
    """Preflight snapshot is stale and must be rebuilt before Create retries."""


@dataclass(frozen=True)
class InitialProjectCreationResult:
    project: Project
    report: SourceSyncReport


class InitialProjectCreationService:
    """Create a project, run production source sync, then verify the database.

    When a valid Source Preflight report is supplied, its fingerprint snapshot
    is verified before the .smproj is created. The already parsed workbook data
    is then fed back into SourceSyncEngine; the engine's normal Apply freshness
    check still re-scans source immediately before database mutation.
    """

    def __init__(
        self,
        project_manager: ProjectManager,
        source_sync_engine: SourceSyncEngine,
    ) -> None:
        self.project_manager = project_manager
        self.source_sync_engine = source_sync_engine

    def run(
        self,
        settings: ProjectSettings,
        parent_folder: str | Path,
        *,
        progress_callback: ProgressCallback | None = None,
        preflight_report: SourcePreflightReport | None = None,
    ) -> InitialProjectCreationResult:
        report_holder: dict[str, SourceSyncReport] = {}
        prepared_input: PreparedSourceSyncInput | None = None

        if preflight_report is not None:
            prepared_input = self._prepare_verified_preflight(
                settings,
                preflight_report,
                progress_callback=progress_callback,
            )

        self._emit_progress(
            progress_callback,
            stage="creating_project",
            message="Membuat file project dan database...",
        )

        def after_create(project: Project) -> None:
            if prepared_input is None:
                report = self.source_sync_engine.synchronize(
                    project,
                    progress_callback=progress_callback,
                )
            else:
                report = self.source_sync_engine.synchronize(
                    project,
                    progress_callback=progress_callback,
                    prepared_input=prepared_input,
                )
            report_holder["report"] = report

            if report.has_errors:
                raise InitialProjectCreationError(
                    self._format_sync_errors(report)
                )

            self._emit_progress(
                progress_callback,
                stage="verifying",
                message="Memverifikasi hasil initial source sync...",
            )
            self._verify_database(project, report)

        project = self.project_manager.create_transactional(
            settings,
            parent_folder,
            after_create=after_create,
        )

        report = report_holder.get("report")
        if report is None:
            # Defensive guard: a transaction may only succeed when its
            # after-create stage has produced the sync report.
            self.project_manager.rollback_created_project(project)
            raise InitialProjectCreationError(
                "Initial Source Sync tidak menghasilkan laporan sinkronisasi."
            )

        self._emit_progress(
            progress_callback,
            stage="ready",
            current=1,
            total=1,
            message="Project siap digunakan.",
        )
        return InitialProjectCreationResult(project=project, report=report)

    def _prepare_verified_preflight(
        self,
        settings: ProjectSettings,
        preflight_report: SourcePreflightReport,
        *,
        progress_callback: ProgressCallback | None,
    ) -> PreparedSourceSyncInput:
        if (
            not preflight_report.is_valid
            or preflight_report.scan is None
            or not preflight_report.source_snapshot
        ):
            raise InitialProjectSourceChangedError(
                "Source Preflight belum memiliki snapshot fingerprint yang valid. "
                "Jalankan Source Preflight ulang sebelum membuat project."
            )

        try:
            fresh_scan = self.source_sync_engine.verify_source_snapshot(
                source_folder=settings.source_folder.strip(),
                episode_before=settings.episode_before,
                episode_after=settings.episode_after,
                expected_snapshot=preflight_report.source_snapshot,
                progress_callback=progress_callback,
            )
        except SourceSyncError as exc:
            raise InitialProjectSourceChangedError(str(exc)) from exc

        return PreparedSourceSyncInput(
            source_snapshot=preflight_report.source_snapshot,
            scan=fresh_scan,
            inspections=dict(preflight_report.inspections),
            parse_results=dict(preflight_report.parse_results),
        )

    @staticmethod
    def _verify_database(project: Project, report: SourceSyncReport) -> None:
        with project.database.connect() as connection:
            source_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM source_files WHERE is_active = 1"
                ).fetchone()[0]
            )
            episode_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM episodes WHERE is_active = 1"
                ).fetchone()[0]
            )
            dialogue_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM dialogues WHERE is_active = 1"
                ).fetchone()[0]
            )

        expected_sources = int(report.scanned)
        expected_dialogues = int(report.parsed_dialogues)
        mismatches: list[str] = []

        if source_count != expected_sources:
            mismatches.append(
                f"source aktif {source_count}, seharusnya {expected_sources}"
            )
        if episode_count != expected_sources:
            mismatches.append(
                f"episode aktif {episode_count}, seharusnya {expected_sources}"
            )
        if dialogue_count != expected_dialogues:
            mismatches.append(
                f"dialog aktif {dialogue_count}, seharusnya {expected_dialogues}"
            )

        if mismatches:
            raise InitialProjectCreationError(
                "Verifikasi database setelah Initial Source Sync gagal: "
                + "; ".join(mismatches)
                + "."
            )

    @staticmethod
    def _format_sync_errors(report: SourceSyncReport) -> str:
        lines = [str(message) for message in report.problems]
        for episode, paths in sorted(report.duplicate_episodes.items()):
            names = ", ".join(Path(path).name for path in paths)
            lines.append(f"Episode {episode} duplikat: {names}")

        detail = "\n".join(f"• {line}" for line in lines if line.strip())
        if not detail:
            detail = "• Source tidak dapat disinkronkan."
        return "Initial Source Sync gagal:\n" + detail

    @staticmethod
    def _emit_progress(
        callback: ProgressCallback | None,
        *,
        stage: str,
        current: int = 0,
        total: int = 0,
        message: str = "",
    ) -> None:
        if callback is None:
            return
        callback(
            SourceSyncProgress(
                stage=stage,
                current=current,
                total=total,
                message=message,
            )
        )
