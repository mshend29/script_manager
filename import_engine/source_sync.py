from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.database import Database
from core.project import Project
from import_engine.scanner import (
    SourceScanner,
    SourceScanResult,
)


class SourceSyncError(RuntimeError):
    pass


@dataclass
class SourceSyncReport:
    scanned: int = 0

    added: int = 0

    changed: int = 0

    unchanged: int = 0

    missing: int = 0

    problems: list[str] = field(default_factory=list)

    duplicate_episodes: dict[
        int,
        list[str],
    ] = field(default_factory=dict)

    synced_at: str = ""

    @property
    def has_errors(self) -> bool:

        return bool(self.problems or self.duplicate_episodes)

    def summary(self) -> str:

        return (
            f"Scanned: {self.scanned}\n"
            f"New: {self.added}\n"
            f"Changed: {self.changed}\n"
            f"Unchanged: {self.unchanged}\n"
            f"Missing: {self.missing}"
        )


class SourceSyncEngine:
    def __init__(
        self,
        scanner: SourceScanner | None = None,
    ):

        self.scanner = scanner or SourceScanner()

    # =========================================================
    # SYNCHRONIZE
    # =========================================================

    def synchronize(
        self,
        project: Project,
    ) -> SourceSyncReport:

        settings = project.settings

        source_folder = settings.source_folder.strip()

        if not source_folder:
            raise SourceSyncError("Source Folder belum diisi di Project Settings.")

        # ---------------------------------
        # SCAN SOURCE
        # ---------------------------------

        scan = self.scanner.scan(
            source_folder,
            episode_before=(settings.episode_before),
            episode_after=(settings.episode_after),
        )

        report = SourceSyncReport(
            scanned=len(scan.files),
            problems=[
                (f"{Path(problem.file_path).name}: {problem.message}")
                for problem in scan.problems
            ],
            duplicate_episodes=(scan.duplicate_episodes),
        )

        # ---------------------------------
        # JANGAN KOSONGKAN DATABASE
        # JIKA SOURCE SALAH
        # ---------------------------------

        if not scan.files and not report.problems:
            report.problems.append(
                "Tidak ada file Excel .xlsx atau .xlsm di Source Folder."
            )

        # ---------------------------------
        # JIKA ADA ERROR
        # DATABASE TIDAK DIUBAH
        # ---------------------------------

        if report.has_errors:
            return report

        now = datetime.now().isoformat(timespec="seconds")  # noqa: DTZ005

        report.synced_at = now

        self._apply_scan(
            database=project.database,
            scan=scan,
            report=report,
            synced_at=now,
        )

        return report

    # =========================================================
    # LAST REFRESH
    # =========================================================

    def get_last_sync_at(
        self,
        project: Project,
    ) -> str:

        with project.database.connect() as connection:
            row = connection.execute(
                """
                SELECT value
                FROM app_meta
                WHERE key = 'last_source_sync_at'
                """
            ).fetchone()

            if row:
                return str(row["value"])

        return ""

    # =========================================================
    # APPLY SCAN
    # =========================================================

    @staticmethod
    def _apply_scan(
        *,
        database: Database,
        scan: SourceScanResult,
        report: SourceSyncReport,
        synced_at: str,
    ) -> None:

        scanned_by_path = {item.file_path: item for item in scan.files}

        with database.connect() as connection:
            # ---------------------------------
            # SOURCE FILE YANG SUDAH ADA
            # ---------------------------------

            existing_rows = connection.execute(
                """
                SELECT
                    id,
                    file_path,
                    fingerprint,
                    is_active
                FROM source_files
                """
            ).fetchall()

            existing_by_path = {str(row["file_path"]): row for row in existing_rows}

            # =================================================
            # FILE YANG HILANG
            # =================================================

            missing_paths = set(existing_by_path) - set(scanned_by_path)

            for file_path in missing_paths:
                row = existing_by_path[file_path]

                if int(row["is_active"] or 0) == 1:
                    report.missing += 1

                connection.execute(
                    """
                    UPDATE source_files

                    SET
                        is_active = 0,
                        last_seen_at = ?

                    WHERE id = ?
                    """,
                    (
                        synced_at,
                        int(row["id"]),
                    ),
                )

            # =================================================
            # FILE HASIL SCAN
            # =================================================

            for item in scan.files:
                existing = existing_by_path.get(item.file_path)

                # ---------------------------------
                # FILE BARU
                # ---------------------------------

                if existing is None:
                    report.added += 1

                    imported_at = synced_at

                # ---------------------------------
                # FILE BERUBAH
                # ---------------------------------

                elif str(existing["fingerprint"] or "") != item.fingerprint:
                    report.changed += 1

                    imported_at = synced_at

                # ---------------------------------
                # FILE TIDAK BERUBAH
                # ---------------------------------

                else:
                    report.unchanged += 1

                    imported_at = None

                # =================================================
                # INSERT SOURCE FILE
                # =================================================

                if existing is None:
                    cursor = connection.execute(
                        """
                            INSERT INTO source_files(
                                file_path,
                                file_name,
                                episode_number,
                                file_size,
                                modified_at,
                                fingerprint,
                                is_active,
                                imported_at,
                                last_seen_at
                            )

                            VALUES(
                                ?, ?, ?, ?, ?, ?,
                                1,
                                ?, ?
                            )
                            """,
                        (
                            item.file_path,
                            item.file_name,
                            item.episode_number,
                            item.file_size,
                            item.modified_at,
                            item.fingerprint,
                            imported_at,
                            synced_at,
                        ),
                    )

                    source_file_id = int(cursor.lastrowid)

                # =================================================
                # UPDATE SOURCE FILE
                # =================================================

                else:
                    source_file_id = int(existing["id"])

                    connection.execute(
                        """
                        UPDATE source_files

                        SET
                            file_name = ?,
                            episode_number = ?,
                            file_size = ?,
                            modified_at = ?,
                            fingerprint = ?,
                            is_active = 1,

                            imported_at =
                                CASE
                                    WHEN ? IS NULL
                                    THEN imported_at
                                    ELSE ?
                                END,

                            last_seen_at = ?

                        WHERE id = ?
                        """,
                        (
                            item.file_name,
                            item.episode_number,
                            item.file_size,
                            item.modified_at,
                            item.fingerprint,
                            imported_at,
                            imported_at,
                            synced_at,
                            source_file_id,
                        ),
                    )

                # =================================================
                # EPISODE
                # =================================================

                connection.execute(
                    """
                    INSERT INTO episodes(
                        episode_number,
                        source_file_id,
                        title,
                        is_active
                    )

                    VALUES(
                        ?, ?, ?, 1
                    )

                    ON CONFLICT(episode_number)
                    DO UPDATE SET

                        source_file_id =
                            excluded.source_file_id,

                        title =
                            excluded.title,

                        is_active = 1
                    """,
                    (
                        item.episode_number,
                        source_file_id,
                        Path(item.file_name).stem,
                    ),
                )

            # =================================================
            # NONAKTIFKAN EPISODE YANG SOURCE-NYA HILANG
            # =================================================

            connection.execute(
                """
                UPDATE episodes

                SET is_active = 0

                WHERE source_file_id IS NOT NULL

                AND source_file_id IN (

                    SELECT id

                    FROM source_files

                    WHERE is_active = 0
                )
                """
            )

            # =================================================
            # SIMPAN LAST REFRESH
            # =================================================

            connection.execute(
                """
                INSERT INTO app_meta(
                    key,
                    value
                )

                VALUES(
                    'last_source_sync_at',
                    ?
                )

                ON CONFLICT(key)
                DO UPDATE SET

                    value =
                        excluded.value
                """,
                (synced_at,),
            )
