from __future__ import annotations

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
from import_engine.synchronizer import DialogueSynchronizer


class SourceSyncError(RuntimeError):
    pass


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

    synced_at: str = ""

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

    def synchronize(self, project: Project) -> SourceSyncReport:
        settings = project.settings
        source_folder = settings.source_folder.strip()

        if not source_folder:
            raise SourceSyncError("Source Folder belum diisi di Project Settings.")

        scan = self.scanner.scan(
            source_folder,
            episode_before=settings.episode_before,
            episode_after=settings.episode_after,
        )

        report = SourceSyncReport(
            scanned=len(scan.files),
            problems=[
                f"{Path(problem.file_path).name}: {problem.message}"
                for problem in scan.problems
            ],
            duplicate_episodes=scan.duplicate_episodes,
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

        self._inspect_files(report)
        if report.has_errors:
            return report

        self._parse_files(report)
        if report.has_errors:
            return report

        now = datetime.now().isoformat(timespec="seconds")  # noqa: DTZ005
        report.synced_at = now

        sync_report = self.synchronizer.synchronize(
            database=project.database,
            scan=scan,
            parse_results=report.parse_results,
            synced_at=now,
        )

        report.dialogues_added = sync_report.dialogues_added
        report.dialogues_updated = sync_report.dialogues_updated
        report.dialogues_reactivated = sync_report.dialogues_reactivated
        report.dialogues_deactivated = sync_report.dialogues_deactivated
        report.auto_locked = sync_report.auto_locked
        report.unresolved_cast = sync_report.unresolved_cast
        report.warnings.extend(sync_report.warnings)

        for parse_result in report.parse_results.values():
            report.warnings.extend(
                f"{parse_result.file_name}: {warning}"
                for warning in parse_result.warnings
            )

        return report

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
                # Desktop is syncing) and later return byte-identical.  It must
                # still be inspected/parsed so its dialogue set is reactivated.
                report.restored += 1
                report.restored_files.append(item)
                continue

            report.unchanged += 1

    def _inspect_files(self, report: SourceSyncReport) -> None:
        for item in report.files_to_process:
            try:
                inspection = self.inspector.inspect(item.file_path)
            except WorkbookInspectionError as exc:
                report.problems.append(f"{item.file_name}: {exc}")
                continue

            report.inspected += 1
            report.inspections[item.file_path] = inspection

    def _parse_files(self, report: SourceSyncReport) -> None:
        for item in report.files_to_process:
            try:
                parse_result = self.parser.parse(
                    item.file_path,
                    episode_number=item.episode_number,
                )
            except ScriptParseError as exc:
                report.problems.append(f"{item.file_name}: {exc}")
                continue

            report.parsed_files += 1
            report.parsed_dialogues += parse_result.dialogue_count
            report.parse_results[item.file_path] = parse_result

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
