from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.database import Database
from core.project import Project
from import_engine.inspector import (
    WorkbookInspection,
    WorkbookInspectionError,
    WorkbookInspector,
)
from import_engine.parser import (
    ScriptParseError,
    ScriptParseResult,
    ScriptParser,
)
from import_engine.scanner import (
    ScannedSourceFile,
    SourceScanner,
    SourceScanResult,
)
from import_engine.source_change_plan import (
    SourceChangePlan,
    SourceChangePlanBuilder,
)
from import_engine.synchronizer import DialogueSynchronizer
from services.audit_service import AuditService
from services.backup_service import BackupService
from services.source_change_service import (
    SourceChangePreview,
    SourceChangeService,
)


class SourceSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceSyncProgress:
    stage: str
    current: int = 0
    total: int = 0
    message: str = ""
    file_name: str = ""

    @property
    def is_determinate(self) -> bool:
        return self.total > 0


ProgressCallback = Callable[[SourceSyncProgress], None]


@dataclass
class SourceSyncReport:
    scanned: int = 0
    inspected: int = 0
    parsed_files: int = 0
    parsed_dialogues: int = 0

    added: int = 0
    changed: int = 0
    restored: int = 0
    unchanged: int = 0
    missing: int = 0

    dialogues_added: int = 0
    dialogues_updated: int = 0
    dialogues_reactivated: int = 0
    dialogues_deactivated: int = 0
    auto_locked: int = 0
    unresolved_cast: int = 0

    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    duplicate_episodes: dict[int, list[str]] = field(default_factory=dict)

    added_files: list[ScannedSourceFile] = field(default_factory=list)
    changed_files: list[ScannedSourceFile] = field(default_factory=list)
    restored_files: list[ScannedSourceFile] = field(default_factory=list)

    inspections: dict[str, WorkbookInspection] = field(default_factory=dict)
    parse_results: dict[str, ScriptParseResult] = field(default_factory=dict)
    scan: SourceScanResult | None = None
    plan: SourceChangePlan | None = None
    preview: SourceChangePreview | None = None

    synced_at: str = ""
    backup_path: str = ""

    @property
    def has_errors(self) -> bool:
        return bool(self.problems or self.duplicate_episodes)

    @property
    def files_to_process(self) -> list[ScannedSourceFile]:
        return [
            *self.added_files,
            *self.changed_files,
            *self.restored_files,
        ]

    def summary(self) -> str:
        return (
            f"Scanned: {self.scanned}\n"
            f"Inspected: {self.inspected}\n"
            f"Parsed Files: {self.parsed_files}\n"
            f"Parsed Dialogues: {self.parsed_dialogues}\n"
            f"New Source: {self.added}\n"
            f"Changed Source: {self.changed}\n"
            f"Restored Source: {self.restored}\n"
            f"Unchanged Source: {self.unchanged}\n"
            f"Missing Source: {self.missing}\n"
            f"Dialogues Added: {self.dialogues_added}\n"
            f"Dialogues Updated: {self.dialogues_updated}\n"
            f"Dialogues Reactivated: {self.dialogues_reactivated}\n"
            f"Dialogues Deactivated: {self.dialogues_deactivated}\n"
            f"Auto Locked Cast: {self.auto_locked}\n"
            f"Unresolved Cast: {self.unresolved_cast}\n"
            f"Warnings: {len(self.warnings)}"
        )


class SourceSyncEngine:
    def __init__(
        self,
        scanner: SourceScanner | None = None,
        inspector: WorkbookInspector | None = None,
        parser: ScriptParser | None = None,
        synchronizer: DialogueSynchronizer | None = None,
    ) -> None:
        self.scanner = scanner or SourceScanner()
        self.inspector = inspector or WorkbookInspector()
        self.parser = parser or ScriptParser()
        self.synchronizer = synchronizer or DialogueSynchronizer()

    def synchronize(
        self,
        project: Project,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> SourceSyncReport:
        """Backward-compatible one-shot sync used by engine/tests."""
        report = self.prepare(
            project,
            progress_callback=progress_callback,
        )
        if report.has_errors:
            return report
        return self.apply(
            project,
            report,
            progress_callback=progress_callback,
        )

    def prepare(
        self,
        project: Project,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> SourceSyncReport:
        """Scan/inspect/parse and build a diff without changing the database."""
        settings = project.settings
        source_folder = settings.source_folder.strip()

        if not source_folder:
            raise SourceSyncError("Source Folder belum diisi di Project Settings.")

        self._emit_progress(
            progress_callback,
            stage="scanning",
            message="Scanning source files...",
        )

        scan = self.scanner.scan(
            source_folder,
            episode_before=settings.episode_before,
            episode_after=settings.episode_after,
        )

        report = SourceSyncReport(
            scanned=len(scan.files),
            scan=scan,
            problems=[
                f"{Path(problem.file_path).name}: {problem.message}"
                for problem in scan.problems
            ],
            duplicate_episodes=scan.duplicate_episodes,
        )

        self._emit_progress(
            progress_callback,
            stage="classifying",
            current=len(scan.files),
            total=len(scan.files),
            message=f"Scanned {len(scan.files)} source files",
        )

        if not scan.files and not report.problems:
            report.problems.append(
                "Tidak ada file Excel .xlsx atau .xlsm di Source Folder."
            )

        if report.has_errors:
            return report

        self._classify_scan(
            database=project.database,
            scan=scan,
            report=report,
        )

        self._inspect_files(report, progress_callback)
        if report.has_errors:
            return report

        self._parse_files(report, progress_callback)
        if report.has_errors:
            return report

        for parse_result in report.parse_results.values():
            report.warnings.extend(
                f"{parse_result.file_name}: {warning}"
                for warning in parse_result.warnings
            )

        self._emit_progress(
            progress_callback,
            stage="diffing",
            message="Building source change preview...",
        )
        report.plan = SourceChangePlanBuilder(project.database).build(
            scan=scan,
            parse_results=report.parse_results,
        )
        report.preview = SourceChangeService(
            project.database
        ).build_from_plan(report.plan)

        if report.plan.has_ambiguities:
            report.problems.extend(report.plan.ambiguity_messages)
            return report

        self._emit_progress(
            progress_callback,
            stage="preview_ready",
            current=1,
            total=1,
            message="Source refresh preview ready",
        )
        return report

    def apply(
        self,
        project: Project,
        report: SourceSyncReport,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> SourceSyncReport:
        """Apply a previously prepared report after a safety backup."""
        if report.has_errors:
            return report
        if report.scan is None:
            raise SourceSyncError(
                "Source refresh plan tidak memiliki scan context."
            )
        if report.plan is None:
            report.plan = SourceChangePlanBuilder(
                project.database
            ).build(
                scan=report.scan,
                parse_results=report.parse_results,
            )
        if report.plan.has_ambiguities:
            raise SourceSyncError(
                "Source refresh memiliki dialogue lineage ambigu. "
                "Jalankan Sync Source lagi setelah source diperiksa."
            )

        self._validate_plan_is_fresh(project, report.plan)

        self._emit_progress(
            progress_callback,
            stage="backup",
            message="Creating safety backup...",
        )
        backup = BackupService(project.database).create(
            "before-source-refresh"
        )
        report.backup_path = str(backup)

        self._emit_progress(
            progress_callback,
            stage="synchronizing",
            message="Applying source changes...",
        )

        now = datetime.now().isoformat(timespec="seconds")  # noqa: DTZ005
        report.synced_at = now

        sync_report = self.synchronizer.synchronize(
            database=project.database,
            scan=report.scan,
            parse_results=report.parse_results,
            synced_at=now,
            plan=report.plan,
        )

        report.dialogues_added = sync_report.dialogues_added
        report.dialogues_updated = sync_report.dialogues_updated
        report.dialogues_reactivated = sync_report.dialogues_reactivated
        report.dialogues_deactivated = sync_report.dialogues_deactivated
        report.auto_locked = sync_report.auto_locked
        report.unresolved_cast = sync_report.unresolved_cast
        report.warnings.extend(sync_report.warnings)

        preview = report.preview or SourceChangePreview()
        AuditService(project.database).record(
            event_type="SOURCE",
            action="REFRESH_APPLIED",
            summary=(
                f"Source refresh applied: {preview.changed_episodes} episode, "
                f"{preview.dialogues_added} dialog added, "
                f"{preview.dialogues_removed} removed, "
                f"{preview.text_changed + preview.cast_changed} changed."
            ),
            entity_type="project",
            details={
                "source_added": preview.source_added,
                "source_changed": preview.source_changed,
                "source_restored": preview.source_restored,
                "source_missing": preview.source_missing,
                "dialogues_added": preview.dialogues_added,
                "dialogues_removed": preview.dialogues_removed,
                "text_changed": preview.text_changed,
                "cast_changed": preview.cast_changed,
                "recording_affected": preview.recording_affected,
                "tracking_affected": preview.tracking_affected,
                "backup_path": report.backup_path,
            },
            created_at=now,
        )

        self._emit_progress(
            progress_callback,
            stage="complete",
            current=1,
            total=1,
            message="Source synchronization complete",
        )

        return report

    def _validate_plan_is_fresh(
        self,
        project: Project,
        plan: SourceChangePlan,
    ) -> None:
        settings = project.settings
        current_scan = self.scanner.scan(
            settings.source_folder.strip(),
            episode_before=settings.episode_before,
            episode_after=settings.episode_after,
        )

        if current_scan.problems:
            details = "; ".join(
                f"{Path(problem.file_path).name}: {problem.message}"
                for problem in current_scan.problems
            )
            raise SourceSyncError(
                "Source berubah atau tidak dapat dibaca setelah preview. "
                f"Jalankan Sync Source lagi. {details}"
            )

        if current_scan.duplicate_episodes:
            raise SourceSyncError(
                "Source berubah setelah preview dan sekarang memiliki "
                "duplicate episode. Jalankan Sync Source lagi."
            )

        current_snapshot = SourceChangePlanBuilder.scan_snapshot(
            current_scan
        )
        if current_snapshot != plan.source_snapshot:
            raise SourceSyncError(
                "Source berubah setelah preview. "
                "Jalankan Sync Source lagi sebelum Apply."
            )

        with project.database.connect() as connection:
            current_token = (
                SourceChangePlanBuilder.compute_database_token(connection)
            )
        if current_token != plan.database_token:
            raise SourceSyncError(
                "Database project berubah setelah preview. "
                "Jalankan Sync Source lagi sebelum Apply."
            )

    @staticmethod
    def _emit_progress(
        callback: ProgressCallback | None,
        *,
        stage: str,
        current: int = 0,
        total: int = 0,
        message: str = "",
        file_name: str = "",
    ) -> None:
        if callback is None:
            return

        callback(
            SourceSyncProgress(
                stage=stage,
                current=current,
                total=total,
                message=message,
                file_name=file_name,
            )
        )

    @staticmethod
    def _classify_scan(
        *,
        database: Database,
        scan: SourceScanResult,
        report: SourceSyncReport,
    ) -> None:
        scanned_by_path = {item.file_path: item for item in scan.files}

        with database.connect() as connection:
            existing_rows = connection.execute(
                """
                SELECT file_path, fingerprint, is_active
                FROM source_files
                """
            ).fetchall()

        existing_by_path = {
            str(row["file_path"]): row for row in existing_rows
        }

        missing_paths = set(existing_by_path) - set(scanned_by_path)
        report.missing = sum(
            1
            for file_path in missing_paths
            if int(existing_by_path[file_path]["is_active"] or 0) == 1
        )

        for item in scan.files:
            existing = existing_by_path.get(item.file_path)

            if existing is None:
                report.added += 1
                report.added_files.append(item)
                continue

            fingerprint_changed = (
                str(existing["fingerprint"] or "") != item.fingerprint
            )

            if fingerprint_changed:
                report.changed += 1
                report.changed_files.append(item)
                continue

            if int(existing["is_active"] or 0) != 1:
                # A source can disappear temporarily (for example while Drive
                # Desktop is syncing) and later return byte-identical. It must
                # still be inspected/parsed so its dialogue set is reactivated.
                report.restored += 1
                report.restored_files.append(item)
                continue

            report.unchanged += 1

    def _inspect_files(
        self,
        report: SourceSyncReport,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        files = report.files_to_process
        total = len(files)

        if total:
            self._emit_progress(
                progress_callback,
                stage="inspecting",
                current=0,
                total=total,
                message=f"Inspecting workbooks 0/{total}",
            )

        for index, item in enumerate(files, start=1):
            try:
                inspection = self.inspector.inspect(item.file_path)
            except WorkbookInspectionError as exc:
                report.problems.append(f"{item.file_name}: {exc}")
            else:
                report.inspected += 1
                report.inspections[item.file_path] = inspection

            self._emit_progress(
                progress_callback,
                stage="inspecting",
                current=index,
                total=total,
                message=f"Inspecting workbooks {index}/{total}",
                file_name=item.file_name,
            )

    def _parse_files(
        self,
        report: SourceSyncReport,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        files = report.files_to_process
        total = len(files)

        if total:
            self._emit_progress(
                progress_callback,
                stage="parsing",
                current=0,
                total=total,
                message=f"Parsing scripts 0/{total}",
            )

        for index, item in enumerate(files, start=1):
            try:
                parse_result = self.parser.parse(
                    item.file_path,
                    episode_number=item.episode_number,
                )
            except ScriptParseError as exc:
                report.problems.append(f"{item.file_name}: {exc}")
            else:
                report.parsed_files += 1
                report.parsed_dialogues += parse_result.dialogue_count
                report.parse_results[item.file_path] = parse_result

            self._emit_progress(
                progress_callback,
                stage="parsing",
                current=index,
                total=total,
                message=f"Parsing scripts {index}/{total}",
                file_name=item.file_name,
            )

    def get_last_sync_at(self, project: Project) -> str:
        with project.database.connect() as connection:
            row = connection.execute(
                """
                SELECT value
                FROM app_meta
                WHERE key = 'last_source_sync_at'
                """
            ).fetchone()

            return str(row["value"]) if row else ""
