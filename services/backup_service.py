from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

from core.app_paths import database_backups_dir
from core.database import Database, SCHEMA_VERSION
from core.project import PROJECT_FORMAT_ID
from services.audit_service import AuditService


_SAFE_REASON = re.compile(r"[^a-z0-9_-]+")


class BackupService:
    def __init__(self, database: Database, *, keep: int = 20):
        self.database = database
        self.keep = max(1, int(keep))

    @property
    def backup_dir(self) -> Path:
        project_id = self.database.get_smproj_meta(
            "project_id",
            default="",
        )
        return database_backups_dir(
            self.database.path,
            project_id=project_id,
        )

    def create(self, reason: str = "manual") -> Path:
        backup_dir = self.backup_dir
        backup_dir.mkdir(parents=True, exist_ok=True)

        reason_key = _SAFE_REASON.sub(
            "-",
            str(reason or "manual").strip().casefold(),
        ).strip("-") or "manual"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        target = backup_dir / (
            f"{self.database.path.stem}_{reason_key}_{stamp}.smproj"
        )
        suffix = 1
        while target.exists():
            target = backup_dir / (
                f"{self.database.path.stem}_{reason_key}_{stamp}_{suffix}.smproj"
            )
            suffix += 1

        with self.database.connect() as source:
            destination = sqlite3.connect(target)
            try:
                source.backup(destination)
            finally:
                destination.close()

        self._prune(backup_dir)
        return target

    def list_backups(self) -> list[Path]:
        backup_dir = self.backup_dir
        if not backup_dir.exists():
            return []
        return sorted(
            backup_dir.glob("*.smproj"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

    def validate_backup(self, backup_path: str | Path) -> tuple[bool, str]:
        path = Path(backup_path)
        if not path.is_file():
            return False, "Backup file tidak ditemukan."

        version = 0
        try:
            connection = sqlite3.connect(path)
            try:
                integrity = [
                    str(row[0])
                    for row in connection.execute(
                        "PRAGMA integrity_check"
                    ).fetchall()
                ]
                if integrity != ["ok"]:
                    return (
                        False,
                        "SQLite integrity check gagal: "
                        + "; ".join(integrity[:5]),
                    )

                table = connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table' AND name = 'app_meta'
                    """
                ).fetchone()
                if table is None:
                    return False, "File bukan database Script Manager."

                row = connection.execute(
                    """
                    SELECT value
                    FROM app_meta
                    WHERE key = 'schema_version'
                    """
                ).fetchone()
                if row is None:
                    return False, "Schema version backup tidak ditemukan."

                try:
                    version = int(str(row[0]))
                except ValueError:
                    return False, "Schema version backup tidak valid."

                if version > SCHEMA_VERSION:
                    return (
                        False,
                        f"Backup schema v{version} lebih baru dari aplikasi "
                        f"yang mendukung sampai v{SCHEMA_VERSION}.",
                    )

                smproj_table = connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table' AND name = 'smproj_meta'
                    """
                ).fetchone()
                if smproj_table is not None:
                    format_row = connection.execute(
                        """
                        SELECT value
                        FROM smproj_meta
                        WHERE key = 'format_id'
                        """
                    ).fetchone()
                    if (
                        format_row is not None
                        and str(format_row[0]) != PROJECT_FORMAT_ID
                    ):
                        return False, "Backup bukan Script Management Project."
            finally:
                connection.close()
        except sqlite3.DatabaseError as exc:
            return False, f"Backup database tidak dapat dibaca: {exc}"

        return True, f"Valid Script Manager backup (schema v{version})."

    def restore(self, backup_path: str | Path) -> tuple[Path, int]:
        source_path = Path(backup_path)
        valid, message = self.validate_backup(source_path)
        if not valid:
            raise ValueError(message)

        current_project_id = self.database.get_smproj_meta(
            "project_id",
            default="",
        )
        source_project_id = self._read_backup_project_id(source_path)
        if (
            current_project_id
            and source_project_id
            and current_project_id != source_project_id
        ):
            raise ValueError(
                "Backup berasal dari project yang berbeda."
            )

        safety_backup = self.create("before-restore")

        source = sqlite3.connect(source_path)
        destination = sqlite3.connect(self.database.path)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()

        self.database.initialize()

        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT value
                FROM app_meta
                WHERE key = 'schema_version'
                """
            ).fetchone()
            restored_schema = int(str(row["value"] if row else 0))

        AuditService(self.database).record(
            event_type="DATABASE",
            action="RESTORE_BACKUP",
            entity_type="project",
            summary=f"Database restored from backup {source_path.name}.",
            details={
                "source_backup": str(source_path),
                "safety_backup": str(safety_backup),
                "schema_version": restored_schema,
            },
        )

        return safety_backup, restored_schema

    @staticmethod
    def _read_backup_project_id(path: Path) -> str:
        try:
            connection = sqlite3.connect(path)
            try:
                table = connection.execute(
                    """
                    SELECT 1
                    FROM sqlite_master
                    WHERE type = 'table' AND name = 'smproj_meta'
                    """
                ).fetchone()
                if table is None:
                    return ""
                row = connection.execute(
                    """
                    SELECT value
                    FROM smproj_meta
                    WHERE key = 'project_id'
                    """
                ).fetchone()
                return str(row[0] if row else "")
            finally:
                connection.close()
        except sqlite3.DatabaseError:
            return ""

    def _prune(self, backup_dir: Path) -> None:
        backups = sorted(
            backup_dir.glob("*.smproj"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for stale in backups[self.keep:]:
            try:
                stale.unlink()
            except OSError:
                pass
