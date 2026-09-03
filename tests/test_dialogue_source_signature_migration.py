from __future__ import annotations

import sqlite3

from core.database import Database, SCHEMA_VERSION


def test_schema_v10_adds_source_signature_column_and_index(tmp_path) -> None:
    database = Database(tmp_path / "project.db")
    database.initialize()

    assert SCHEMA_VERSION >= 10

    with database.connect() as connection:
        columns = {
            str(row["name"])
            for row in connection.execute(
                "PRAGMA table_info(dialogues)"
            ).fetchall()
        }
        indexes = {
            str(row["name"])
            for row in connection.execute(
                "PRAGMA index_list(dialogues)"
            ).fetchall()
        }

    assert "source_signature" in columns
    assert "idx_dialogues_source_signature" in indexes


def test_schema_v10_backfills_legacy_dialog_uid_as_source_signature(tmp_path) -> None:
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            INSERT INTO app_meta(key, value)
            VALUES('schema_version', '9');

            CREATE TABLE smproj_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE dialogues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dialog_uid TEXT NOT NULL UNIQUE,
                episode_id INTEGER NOT NULL,
                source_file_id INTEGER,
                time_in TEXT,
                time_out TEXT,
                dialog_text TEXT NOT NULL,
                source_row INTEGER,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            );

            INSERT INTO dialogues(
                dialog_uid,
                episode_id,
                source_file_id,
                time_in,
                time_out,
                dialog_text,
                source_row,
                is_active
            )
            VALUES(
                'legacy-content-hash',
                1,
                NULL,
                '00:00:01,000',
                '00:00:02,000',
                'Halo',
                3,
                1
            );
            """
        )
        connection.commit()
    finally:
        connection.close()

    database = Database(path)
    database.initialize()

    with database.connect() as connection:
        row = connection.execute(
            """
            SELECT dialog_uid, source_signature
            FROM dialogues
            WHERE id = 1
            """
        ).fetchone()
        version = connection.execute(
            "SELECT value FROM app_meta WHERE key = 'schema_version'"
        ).fetchone()["value"]

    assert str(version) == str(SCHEMA_VERSION)
    assert str(row["dialog_uid"]) == "legacy-content-hash"
    assert str(row["source_signature"]) == "legacy-content-hash"
