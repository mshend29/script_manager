from __future__ import annotations

import sqlite3

from core.app_paths import database_backups_dir
from core.database import Database, SCHEMA_VERSION


def test_schema_v10_recording_migrates_to_v11_with_baseline_and_backup(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "appdata"))

    path = tmp_path / "migration.smproj"
    database = Database(path)
    database.initialize()

    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO smproj_meta(key, value)
            VALUES('project_id', 'migration-project')
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """
        )
        source_id = connection.execute(
            """
            INSERT INTO source_files(
                file_path, file_name, episode_number, is_active
            ) VALUES('episode-1.xlsx', 'episode-1.xlsx', 1, 1)
            """
        ).lastrowid
        episode_id = connection.execute(
            """
            INSERT INTO episodes(
                episode_number, source_file_id, is_active
            ) VALUES(1, ?, 1)
            """,
            (source_id,),
        ).lastrowid
        dialogue_id = connection.execute(
            """
            INSERT INTO dialogues(
                dialog_uid,
                source_signature,
                episode_id,
                source_file_id,
                time_in,
                time_out,
                dialog_text,
                source_row,
                is_active
            ) VALUES(
                'persistent-uid',
                'source-signature-v10',
                ?,
                ?,
                '00:00:01,000',
                '00:00:02,000',
                'Recorded before upgrade',
                3,
                1
            )
            """,
            (episode_id, source_id),
        ).lastrowid

        # Recreate recording_status exactly as schema v10: no
        # source_signature_at_recording column yet.
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("ALTER TABLE recording_status RENAME TO recording_status_v11")
        connection.execute(
            """
            CREATE TABLE recording_status (
                dialogue_id INTEGER PRIMARY KEY,
                is_recorded INTEGER NOT NULL DEFAULT 0,
                recorded_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (dialogue_id)
                    REFERENCES dialogues(id)
                    ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            INSERT INTO recording_status(
                dialogue_id, is_recorded, recorded_at, updated_at
            ) VALUES(?, 1, '2026-08-01T10:00:00', '2026-08-01T10:00:00')
            """,
            (dialogue_id,),
        )
        connection.execute("DROP TABLE recording_status_v11")
        connection.execute(
            """
            INSERT INTO app_meta(key, value)
            VALUES('schema_version', '10')
            ON CONFLICT(key) DO UPDATE SET value = '10'
            """
        )
        connection.execute("PRAGMA foreign_keys = ON")

    database.initialize()

    with database.connect() as connection:
        schema = connection.execute(
            "SELECT value FROM app_meta WHERE key = 'schema_version'"
        ).fetchone()
        columns = {
            str(row["name"])
            for row in connection.execute(
                "PRAGMA table_info(recording_status)"
            ).fetchall()
        }
        recording = connection.execute(
            """
            SELECT is_recorded, source_signature_at_recording
            FROM recording_status
            WHERE dialogue_id = ?
            """,
            (dialogue_id,),
        ).fetchone()

    assert int(schema["value"]) == SCHEMA_VERSION
    assert "source_signature_at_recording" in columns
    assert int(recording["is_recorded"]) == 1
    assert recording["source_signature_at_recording"] == "source-signature-v10"

    migration_dir = (
        database_backups_dir(path, project_id="migration-project")
        / "Migrations"
    )
    backups = list(
        migration_dir.glob(
            f"migration_before_schema_v10_to_v{SCHEMA_VERSION}_*.smproj"
        )
    )
    assert backups
    assert backups[0].is_file()
