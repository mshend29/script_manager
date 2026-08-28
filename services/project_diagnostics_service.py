from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.database import SCHEMA_VERSION
from core.project import Project
from services.backup_service import BackupService
from services.track_file_service import TrackAudioSpec, TrackFileService
from services.validation_service import ValidationService


STATUS_OK = "OK"
STATUS_WARNING = "WARNING"
STATUS_ERROR = "ERROR"
STATUS_INFO = "INFO"


@dataclass(frozen=True)
class DiagnosticCheck:
    key: str
    label: str
    status: str
    value: str
    detail: str = ""


@dataclass
class ProjectDiagnostics:
    checks: list[DiagnosticCheck] = field(default_factory=list)
    system_errors: int = 0
    needs_review: int = 0
    workflow_warnings: int = 0
    output_warnings: int = 0
    backup_count: int = 0
    audit_count: int = 0

    @property
    def error_count(self) -> int:
        return sum(
            1 for check in self.checks if check.status == STATUS_ERROR
        ) + self.system_errors

    @property
    def warning_count(self) -> int:
        return sum(
            1 for check in self.checks if check.status == STATUS_WARNING
        ) + self.needs_review + self.workflow_warnings + self.output_warnings

    @property
    def healthy(self) -> bool:
        return self.error_count == 0


class ProjectDiagnosticsService:
    def __init__(self, project: Project):
        self.project = project

    def run(self) -> ProjectDiagnostics:
        result = ProjectDiagnostics()
        database = self.project.database
        settings = self.project.settings

        result.checks.append(
            DiagnosticCheck(
                key="project_package",
                label="Project Package",
                status=STATUS_OK if self.project.is_package else STATUS_WARNING,
                value=(
                    self.project.package_name
                    if self.project.is_package
                    else "Legacy Folder"
                ),
                detail=(
                    "Writable .drsp directory package."
                    if self.project.is_package
                    else "Project lama masih didukung. Gunakan TOOLS → "
                    "Convert to .drsp untuk format project baru."
                ),
            )
        )
        result.checks.extend(self._database_checks())

        issues = ValidationService(database).validate()
        summary = ValidationService(database).summarize(issues)
        result.system_errors = int(summary.system_errors)
        result.needs_review = int(summary.needs_review)
        result.workflow_warnings = int(summary.workflow_warnings)

        result.checks.extend(
            [
                self._folder_check(
                    "source_folder",
                    "Source Folder",
                    settings.source_folder,
                    required=True,
                ),
                self._folder_check(
                    "stem_output_folder",
                    "Stem / Export Folder",
                    settings.stem_output_folder,
                    required=False,
                ),
                self._folder_check(
                    "delivery_folder",
                    "Setoran Folder",
                    settings.delivery_folder,
                    required=False,
                ),
            ]
        )

        result.checks.extend(
            [
                self._url_check(
                    "main_drive",
                    "Main Drive Link",
                    settings.main_drive_url,
                ),
                self._url_check(
                    "material_drive",
                    "Material Drive Link",
                    settings.material_drive_url,
                ),
                self._url_check(
                    "delivery_drive",
                    "Delivery Drive Link",
                    settings.delivery_drive_url,
                ),
            ]
        )

        try:
            inventory = TrackFileService(
                database,
                output_folder=settings.stem_output_folder,
                delivery_folder=settings.delivery_folder,
                audio_spec=TrackAudioSpec(
                    file_format="WAV",
                    sample_rate=int(settings.audio_sample_rate or 48000),
                    bit_depth=int(settings.audio_bit_depth or 24),
                    channels=int(settings.audio_channels or 1),
                ),
            ).scan_and_sync()
            result.output_warnings = (
                len(inventory.warnings)
                + sum(len(row.warnings) for row in inventory.rows)
            )
        except Exception as exc:
            result.output_warnings = 1
            result.checks.append(
                DiagnosticCheck(
                    key="track_scan",
                    label="Track File Scan",
                    status=STATUS_WARNING,
                    value="Unavailable",
                    detail=str(exc),
                )
            )
        else:
            result.checks.append(
                DiagnosticCheck(
                    key="track_scan",
                    label="Track File Scan",
                    status=(
                        STATUS_WARNING
                        if result.output_warnings
                        else STATUS_OK
                    ),
                    value=f"{result.output_warnings} warning",
                    detail=(
                        "Buka TRACKING → Output Health untuk detail."
                        if result.output_warnings
                        else "Tidak ada warning file yang terdeteksi."
                    ),
                )
            )

        backups = BackupService(database).list_backups()
        result.backup_count = len(backups)
        result.checks.append(
            DiagnosticCheck(
                key="backups",
                label="Database Backups",
                status=STATUS_OK if backups else STATUS_WARNING,
                value=str(len(backups)),
                detail=(
                    f"Backup terbaru: {backups[0].name}"
                    if backups
                    else "Belum ada database backup."
                ),
            )
        )

        try:
            with database.connect() as connection:
                row = connection.execute(
                    "SELECT COUNT(*) AS total FROM audit_log"
                ).fetchone()
                result.audit_count = int(row["total"] if row else 0)
        except Exception:
            result.audit_count = 0

        return result

    def _database_checks(self) -> list[DiagnosticCheck]:
        database = self.project.database
        checks: list[DiagnosticCheck] = []

        with database.connect() as connection:
            schema_row = connection.execute(
                "SELECT value FROM app_meta WHERE key = 'schema_version'"
            ).fetchone()
            schema = str(schema_row["value"] if schema_row else "?")
            checks.append(
                DiagnosticCheck(
                    key="schema",
                    label="Database Schema",
                    status=STATUS_OK if schema == str(SCHEMA_VERSION) else STATUS_ERROR,
                    value=f"v{schema}",
                    detail=f"Application schema: v{SCHEMA_VERSION}",
                )
            )

            integrity_rows = connection.execute(
                "PRAGMA integrity_check"
            ).fetchall()
            messages = [str(row[0]) for row in integrity_rows]
            integrity_ok = messages == ["ok"]
            checks.append(
                DiagnosticCheck(
                    key="integrity",
                    label="SQLite Integrity",
                    status=STATUS_OK if integrity_ok else STATUS_ERROR,
                    value="OK" if integrity_ok else "Failed",
                    detail=(
                        "Database integrity check passed."
                        if integrity_ok
                        else "; ".join(messages[:5])
                    ),
                )
            )

            foreign_keys = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()
            checks.append(
                DiagnosticCheck(
                    key="foreign_keys",
                    label="Foreign Keys",
                    status=STATUS_OK if not foreign_keys else STATUS_ERROR,
                    value="OK" if not foreign_keys else str(len(foreign_keys)),
                    detail=(
                        "Tidak ada foreign-key violation."
                        if not foreign_keys
                        else f"{len(foreign_keys)} foreign-key violation."
                    ),
                )
            )

        return checks

    @staticmethod
    def _folder_check(
        key: str,
        label: str,
        value: str,
        *,
        required: bool,
    ) -> DiagnosticCheck:
        raw = str(value or "").strip()
        if not raw:
            return DiagnosticCheck(
                key=key,
                label=label,
                status=STATUS_ERROR if required else STATUS_WARNING,
                value="Not configured",
                detail="Isi path melalui Project Settings.",
            )

        path = Path(raw)
        exists = path.is_dir()
        return DiagnosticCheck(
            key=key,
            label=label,
            status=STATUS_OK if exists else STATUS_ERROR,
            value="Available" if exists else "Missing",
            detail=str(path),
        )

    @staticmethod
    def _url_check(key: str, label: str, value: str) -> DiagnosticCheck:
        raw = str(value or "").strip()
        return DiagnosticCheck(
            key=key,
            label=label,
            status=STATUS_OK if raw else STATUS_INFO,
            value="Configured" if raw else "Not configured",
            detail=raw or "Optional navigation link.",
        )
