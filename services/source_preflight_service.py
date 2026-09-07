from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

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
from import_engine.scanner import SourceScanner, SourceScanError, SourceScanResult
from import_engine.source_change_plan import SourceChangePlanBuilder
from services.source_setup_validation import SourceFilenameValidation


@dataclass(frozen=True)
class SourcePreflightProgress:
    stage: str
    current: int
    total: int
    message: str
    file_name: str = ""


ProgressCallback = Callable[[SourcePreflightProgress], None]
CancelCallback = Callable[[], bool]


@dataclass(frozen=True)
class SourcePreflightFileResult:
    file_path: str
    file_name: str
    episode_number: int
    inspected: bool = False
    parsed: bool = False
    dialogue_count: int = 0
    layout_detection: str = ""
    warnings: tuple[str, ...] = ()
    error: str = ""


@dataclass
class SourcePreflightReport:
    files: list[SourcePreflightFileResult] = field(default_factory=list)
    inspections: dict[str, WorkbookInspection] = field(default_factory=dict)
    parse_results: dict[str, ScriptParseResult] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    cancelled: bool = False
    scan: SourceScanResult | None = None
    source_snapshot: tuple[tuple[str, str, int], ...] = ()

    @property
    def inspected_files(self) -> int:
        return sum(1 for item in self.files if item.inspected)

    @property
    def parsed_files(self) -> int:
        return sum(1 for item in self.files if item.parsed)

    @property
    def parsed_dialogues(self) -> int:
        return sum(item.dialogue_count for item in self.files)

    @property
    def is_valid(self) -> bool:
        return (
            not self.cancelled
            and not self.problems
            and bool(self.files)
            and self.parsed_files == len(self.files)
        )

    @property
    def is_reusable(self) -> bool:
        expected_paths = {item.file_path for item in self.files}
        return (
            self.is_valid
            and self.scan is not None
            and bool(self.source_snapshot)
            and set(self.inspections) == expected_paths
            and set(self.parse_results) == expected_paths
        )


class SourcePreflightService:
    """Read-only workbook preflight using the production source pipeline pieces.

    The service keeps no Project/Database dependency. It uses SourceScanner for
    the same fingerprint snapshot used by Source Sync, then reuses the exact
    WorkbookInspector and ScriptParser classes used by SourceSyncEngine.prepare().
    """

    def __init__(
        self,
        *,
        scanner: SourceScanner | None = None,
        inspector: WorkbookInspector | None = None,
        parser: ScriptParser | None = None,
    ) -> None:
        self.scanner = scanner or SourceScanner()
        self.inspector = inspector or WorkbookInspector()
        self.parser = parser or ScriptParser()

    def run(
        self,
        filename_validation: SourceFilenameValidation,
        *,
        progress_callback: ProgressCallback | None = None,
        cancel_callback: CancelCallback | None = None,
    ) -> SourcePreflightReport:
        report = SourcePreflightReport()

        if not filename_validation.is_valid:
            report.problems.extend(
                issue.message for issue in filename_validation.errors
            )
            if not report.problems:
                report.problems.append(
                    "Validasi nama file sumber belum siap untuk preflight."
                )
            return report

        mappings = tuple(filename_validation.mappings)
        if not mappings:
            report.problems.append("Tidak ada workbook yang siap untuk preflight.")
            return report

        if self._cancelled(cancel_callback):
            report.cancelled = True
            self._emit_cancelled(progress_callback, 0, len(mappings))
            return report

        scan = self._capture_source_snapshot(
            filename_validation,
            report,
            progress_callback,
        )
        if scan is None or report.problems:
            return report

        report.scan = scan
        report.source_snapshot = SourceChangePlanBuilder.scan_snapshot(scan)

        total = len(mappings)
        file_results: dict[str, SourcePreflightFileResult] = {
            item.file_path: SourcePreflightFileResult(
                file_path=item.file_path,
                file_name=item.file_name,
                episode_number=item.episode_number,
            )
            for item in mappings
        }

        self._emit(
            progress_callback,
            stage="inspecting",
            current=0,
            total=total,
            message=f"Memeriksa workbook 0/{total}",
        )

        for index, item in enumerate(mappings, start=1):
            if self._cancelled(cancel_callback):
                report.cancelled = True
                report.files = list(file_results.values())
                self._emit_cancelled(progress_callback, index - 1, total)
                return report

            try:
                inspection = self.inspector.inspect(item.file_path)
            except WorkbookInspectionError as exc:
                message = f"{item.file_name}: {exc}"
                report.problems.append(message)
                file_results[item.file_path] = SourcePreflightFileResult(
                    file_path=item.file_path,
                    file_name=item.file_name,
                    episode_number=item.episode_number,
                    error=str(exc),
                )
            except Exception as exc:  # noqa: BLE001 - preflight boundary
                message = f"{item.file_name}: Workbook inspection gagal: {exc}"
                report.problems.append(message)
                file_results[item.file_path] = SourcePreflightFileResult(
                    file_path=item.file_path,
                    file_name=item.file_name,
                    episode_number=item.episode_number,
                    error=f"Workbook inspection gagal: {exc}",
                )
            else:
                report.inspections[item.file_path] = inspection
                file_results[item.file_path] = SourcePreflightFileResult(
                    file_path=item.file_path,
                    file_name=item.file_name,
                    episode_number=item.episode_number,
                    inspected=True,
                )

            self._emit(
                progress_callback,
                stage="inspecting",
                current=index,
                total=total,
                message=f"Memeriksa workbook {index}/{total}",
                file_name=item.file_name,
            )

        report.files = list(file_results.values())
        if report.problems:
            return report

        if self._cancelled(cancel_callback):
            report.cancelled = True
            self._emit_cancelled(progress_callback, 0, total)
            return report

        self._emit(
            progress_callback,
            stage="parsing",
            current=0,
            total=total,
            message=f"Mem-parse naskah 0/{total}",
        )

        for index, item in enumerate(mappings, start=1):
            if self._cancelled(cancel_callback):
                report.cancelled = True
                report.files = list(file_results.values())
                self._emit_cancelled(progress_callback, index - 1, total)
                return report

            previous = file_results[item.file_path]
            try:
                parsed = self.parser.parse(
                    item.file_path,
                    episode_number=item.episode_number,
                )
            except ScriptParseError as exc:
                message = f"{item.file_name}: {exc}"
                report.problems.append(message)
                file_results[item.file_path] = SourcePreflightFileResult(
                    file_path=item.file_path,
                    file_name=item.file_name,
                    episode_number=item.episode_number,
                    inspected=previous.inspected,
                    error=str(exc),
                )
            except Exception as exc:  # noqa: BLE001 - preflight boundary
                message = f"{item.file_name}: Parsing naskah gagal: {exc}"
                report.problems.append(message)
                file_results[item.file_path] = SourcePreflightFileResult(
                    file_path=item.file_path,
                    file_name=item.file_name,
                    episode_number=item.episode_number,
                    inspected=previous.inspected,
                    error=f"Parsing naskah gagal: {exc}",
                )
            else:
                warnings = tuple(parsed.warnings)
                report.parse_results[item.file_path] = parsed
                report.warnings.extend(
                    f"{item.file_name}: {warning}" for warning in warnings
                )
                file_results[item.file_path] = SourcePreflightFileResult(
                    file_path=item.file_path,
                    file_name=item.file_name,
                    episode_number=item.episode_number,
                    inspected=previous.inspected,
                    parsed=True,
                    dialogue_count=parsed.dialogue_count,
                    layout_detection=parsed.layout.detection,
                    warnings=warnings,
                )

            self._emit(
                progress_callback,
                stage="parsing",
                current=index,
                total=total,
                message=f"Mem-parse naskah {index}/{total}",
                file_name=item.file_name,
            )

        report.files = list(file_results.values())
        if report.problems:
            return report

        if not self._verify_source_unchanged_after_parse(
            filename_validation,
            report,
            progress_callback,
        ):
            return report

        self._emit(
            progress_callback,
            stage="complete",
            current=total,
            total=total,
            message=(
                f"Preflight selesai: {report.parsed_files} workbook, "
                f"{report.parsed_dialogues} dialog siap."
            ),
        )
        return report

    def _capture_source_snapshot(
        self,
        validation: SourceFilenameValidation,
        report: SourcePreflightReport,
        progress_callback: ProgressCallback | None,
    ) -> SourceScanResult | None:
        self._emit(
            progress_callback,
            stage="snapshotting",
            current=0,
            total=len(validation.mappings),
            message="Menyimpan fingerprint source untuk safety check...",
        )
        try:
            scan = self.scanner.scan(
                validation.source_folder,
                episode_before=validation.episode_before,
                episode_after=validation.episode_after,
            )
        except SourceScanError as exc:
            report.problems.append(str(exc))
            return None

        report.problems.extend(
            f"{Path(problem.file_path).name}: {problem.message}"
            for problem in scan.problems
        )
        for episode, paths in sorted(scan.duplicate_episodes.items()):
            names = ", ".join(Path(path).name for path in paths)
            report.problems.append(
                f"Episode {episode} terbaca dari lebih dari satu file: {names}"
            )
        if report.problems:
            return scan

        expected = {
            (item.file_path, int(item.episode_number))
            for item in validation.mappings
        }
        actual = {
            (item.file_path, int(item.episode_number))
            for item in scan.files
        }
        if actual != expected:
            report.problems.append(
                "Source berubah sejak validasi filename dimulai. "
                "Validasi ulang Folder Sumber lalu jalankan Source Preflight lagi."
            )
            return scan

        self._emit(
            progress_callback,
            stage="snapshot_ready",
            current=len(scan.files),
            total=len(scan.files),
            message=f"Fingerprint {len(scan.files)} workbook tersimpan.",
        )
        return scan

    def _verify_source_unchanged_after_parse(
        self,
        validation: SourceFilenameValidation,
        report: SourcePreflightReport,
        progress_callback: ProgressCallback | None,
    ) -> bool:
        self._emit(
            progress_callback,
            stage="snapshot_verifying",
            current=0,
            total=len(validation.mappings),
            message="Memastikan source tidak berubah selama Source Preflight...",
        )
        try:
            scan = self.scanner.scan(
                validation.source_folder,
                episode_before=validation.episode_before,
                episode_after=validation.episode_after,
            )
        except SourceScanError as exc:
            report.problems.append(str(exc))
            return False

        if scan.problems:
            report.problems.extend(
                f"{Path(problem.file_path).name}: {problem.message}"
                for problem in scan.problems
            )
            return False
        if scan.duplicate_episodes:
            report.problems.append(
                "Source berubah selama Source Preflight dan sekarang memiliki "
                "duplicate episode. Jalankan Source Preflight ulang."
            )
            return False

        current_snapshot = SourceChangePlanBuilder.scan_snapshot(scan)
        if current_snapshot != report.source_snapshot:
            report.problems.append(
                "Source berubah selama Source Preflight. "
                "Jalankan Source Preflight ulang sebelum membuat project."
            )
            return False

        report.scan = scan
        self._emit(
            progress_callback,
            stage="snapshot_verified",
            current=len(scan.files),
            total=len(scan.files),
            message="Fingerprint source tetap sama selama Source Preflight.",
        )
        return True

    @staticmethod
    def _cancelled(callback: CancelCallback | None) -> bool:
        return bool(callback is not None and callback())

    @staticmethod
    def _emit(
        callback: ProgressCallback | None,
        *,
        stage: str,
        current: int,
        total: int,
        message: str,
        file_name: str = "",
    ) -> None:
        if callback is None:
            return
        callback(
            SourcePreflightProgress(
                stage=stage,
                current=current,
                total=total,
                message=message,
                file_name=file_name,
            )
        )

    @classmethod
    def _emit_cancelled(
        cls,
        callback: ProgressCallback | None,
        current: int,
        total: int,
    ) -> None:
        cls._emit(
            callback,
            stage="cancelled",
            current=current,
            total=total,
            message="Preflight dibatalkan.",
        )
