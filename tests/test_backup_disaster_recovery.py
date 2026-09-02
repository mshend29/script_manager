from __future__ import annotations

import sqlite3

from core.project_manager import ProjectManager
from core.project_settings import ProjectSettings
from services.backup_service import BackupService


def _talent_names(database) -> list[str]:
    with database.connect() as connection:
        return [
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM talents ORDER BY name COLLATE NOCASE"
            ).fetchall()
        ]


def test_restore_recovers_previous_state_and_preserves_pre_restore_safety_backup(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "appdata"))

    project = ProjectManager().create(
        ProjectSettings(project_name="Recovery Test"),
        tmp_path / "projects",
    )
    database = project.database

    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO talents(
                name, normalized_name, is_active, created_at, updated_at
            ) VALUES('Before Disaster', 'before disaster', 1, '', '')
            """
        )

    service = BackupService(database, keep=10)
    stable_backup = service.create("known-good")
    valid, message = service.validate_backup(stable_backup)
    assert valid, message

    with database.connect() as connection:
        connection.execute("DELETE FROM talents")
        connection.execute(
            """
            INSERT INTO talents(
                name, normalized_name, is_active, created_at, updated_at
            ) VALUES('Corrupted State', 'corrupted state', 1, '', '')
            """
        )

    assert _talent_names(database) == ["Corrupted State"]

    safety_backup, restored_schema = service.restore(stable_backup)

    assert safety_backup.is_file()
    assert restored_schema > 0
    assert _talent_names(database) == ["Before Disaster"]

    # The automatic safety backup must preserve the state that was about to be
    # overwritten, so a mistaken restore can itself be reversed.
    with sqlite3.connect(safety_backup) as connection:
        names = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM talents ORDER BY name COLLATE NOCASE"
            ).fetchall()
        ]
    assert names == ["Corrupted State"]

    with database.connect() as connection:
        audit = connection.execute(
            """
            SELECT action
            FROM audit_log
            WHERE action = 'RESTORE_BACKUP'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    assert audit is not None
