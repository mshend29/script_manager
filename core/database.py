from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_VERSION = 5


class DatabaseCompatibilityError(RuntimeError):
    pass


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        if self.path.exists():
            self._validate_existing_schema_version()

        self.path.parent.mkdir(parents=True, exist_ok=True)

        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS app_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS source_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL UNIQUE,
                    file_name TEXT NOT NULL,
                    episode_number INTEGER,
                    file_size INTEGER,
                    modified_at TEXT,
                    fingerprint TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    imported_at TEXT,
                    last_seen_at TEXT
                );

                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    episode_number INTEGER NOT NULL UNIQUE,
                    source_file_id INTEGER,
                    title TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (source_file_id)
                        REFERENCES source_files(id)
                        ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS characters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL UNIQUE,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS character_alias (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_character_id INTEGER NOT NULL UNIQUE,
                    canonical_character_id INTEGER NOT NULL,
                    alias_name TEXT NOT NULL,
                    normalized_alias TEXT NOT NULL UNIQUE,
                    created_at TEXT,
                    updated_at TEXT,
                    CHECK(source_character_id != canonical_character_id),
                    FOREIGN KEY (source_character_id)
                        REFERENCES characters(id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (canonical_character_id)
                        REFERENCES characters(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS talents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL UNIQUE,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS character_talent (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id INTEGER NOT NULL,
                    talent_id INTEGER NOT NULL,
                    is_locked INTEGER NOT NULL DEFAULT 0,
                    source TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    UNIQUE(character_id, talent_id),
                    FOREIGN KEY (character_id)
                        REFERENCES characters(id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (talent_id)
                        REFERENCES talents(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS dialogues (
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
                    updated_at TEXT,
                    FOREIGN KEY (episode_id)
                        REFERENCES episodes(id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (source_file_id)
                        REFERENCES source_files(id)
                        ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS dialog_cast (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dialogue_id INTEGER NOT NULL,
                    character_id INTEGER NOT NULL,
                    talent_id INTEGER,
                    position INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(dialogue_id, character_id, talent_id),
                    FOREIGN KEY (dialogue_id)
                        REFERENCES dialogues(id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (character_id)
                        REFERENCES characters(id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (talent_id)
                        REFERENCES talents(id)
                        ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS dialogue_review (
                    dialogue_id INTEGER PRIMARY KEY,
                    classification TEXT NOT NULL,
                    note TEXT,
                    reviewed_at TEXT NOT NULL,
                    CHECK(classification IN ('NON_DIALOGUE')),
                    FOREIGN KEY (dialogue_id)
                        REFERENCES dialogues(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS recording_status (
                    dialogue_id INTEGER PRIMARY KEY,
                    is_recorded INTEGER NOT NULL DEFAULT 0,
                    recorded_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (dialogue_id)
                        REFERENCES dialogues(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS stem_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    episode_id INTEGER NOT NULL,
                    talent_id INTEGER NOT NULL,
                    character_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'NOT_READY',
                    note TEXT,
                    updated_at TEXT,
                    UNIQUE(episode_id, talent_id, character_id),
                    FOREIGN KEY (episode_id)
                        REFERENCES episodes(id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (talent_id)
                        REFERENCES talents(id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (character_id)
                        REFERENCES characters(id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_source_files_episode
                    ON source_files(episode_number);

                CREATE INDEX IF NOT EXISTS idx_dialogues_episode
                    ON dialogues(episode_id);

                CREATE INDEX IF NOT EXISTS idx_dialog_cast_dialogue
                    ON dialog_cast(dialogue_id);

                CREATE INDEX IF NOT EXISTS idx_dialog_cast_character
                    ON dialog_cast(character_id);

                CREATE INDEX IF NOT EXISTS idx_dialog_cast_talent
                    ON dialog_cast(talent_id);

                CREATE INDEX IF NOT EXISTS idx_dialogue_review_classification
                    ON dialogue_review(classification);

                CREATE INDEX IF NOT EXISTS idx_character_alias_canonical
                    ON character_alias(canonical_character_id);

                CREATE UNIQUE INDEX IF NOT EXISTS idx_character_talent_one_locked
                    ON character_talent(character_id)
                    WHERE is_locked = 1;
                """
            )

            self._migrate_stem_status_v3(connection)

            connection.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_stem_status_episode
                    ON stem_status(episode_id);

                CREATE INDEX IF NOT EXISTS idx_stem_status_talent
                    ON stem_status(talent_id);

                CREATE INDEX IF NOT EXISTS idx_stem_status_character
                    ON stem_status(character_id);
                """
            )

            connection.execute(
                """
                INSERT INTO app_meta(key, value)
                VALUES('schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (str(SCHEMA_VERSION),),
            )

    def _validate_existing_schema_version(self) -> None:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            app_meta_exists = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table' AND name = 'app_meta'
                """
            ).fetchone()
            if app_meta_exists is None:
                return

            row = connection.execute(
                "SELECT value FROM app_meta WHERE key = 'schema_version'"
            ).fetchone()
            if row is None:
                return

            raw_value = str(row["value"] or "").strip()
            try:
                version = int(raw_value)
            except ValueError as exc:
                raise DatabaseCompatibilityError(
                    f"Database memiliki schema_version tidak valid: {raw_value!r}."
                ) from exc

            if version > SCHEMA_VERSION:
                raise DatabaseCompatibilityError(
                    "Database dibuat oleh versi aplikasi yang lebih baru "
                    f"(schema {version}); aplikasi ini hanya mendukung sampai "
                    f"schema {SCHEMA_VERSION}."
                )
        finally:
            connection.close()

    @staticmethod
    def _migrate_stem_status_v3(connection: sqlite3.Connection) -> None:
        columns = {
            str(row["name"])
            for row in connection.execute(
                "PRAGMA table_info(stem_status)"
            ).fetchall()
        }

        if "character_id" in columns:
            return

        connection.execute("ALTER TABLE stem_status RENAME TO stem_status_v2")

        connection.execute(
            """
            CREATE TABLE stem_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_id INTEGER NOT NULL,
                talent_id INTEGER NOT NULL,
                character_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'NOT_READY',
                note TEXT,
                updated_at TEXT,
                UNIQUE(episode_id, talent_id, character_id),
                FOREIGN KEY (episode_id)
                    REFERENCES episodes(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (talent_id)
                    REFERENCES talents(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (character_id)
                    REFERENCES characters(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            INSERT INTO stem_status(
                episode_id,
                talent_id,
                character_id,
                status,
                note,
                updated_at
            )
            SELECT
                legacy.episode_id,
                legacy.talent_id,
                MIN(dc.character_id),
                legacy.status,
                legacy.note,
                legacy.updated_at
            FROM stem_status_v2 AS legacy
            JOIN dialogues AS d
              ON d.episode_id = legacy.episode_id
             AND d.is_active = 1
            JOIN dialog_cast AS dc
              ON dc.dialogue_id = d.id
             AND dc.talent_id = legacy.talent_id
            GROUP BY legacy.id
            HAVING COUNT(DISTINCT dc.character_id) = 1
            """
        )

        connection.execute("DROP TABLE stem_status_v2")

    def get_counts(self) -> dict[str, int]:
        tables = {
            "episodes": "episodes",
            "characters": "characters",
            "talents": "talents",
            "dialogues": "dialogues",
        }

        result: dict[str, int] = {}

        with self.connect() as connection:
            for key, table in tables.items():
                row = connection.execute(
                    f"SELECT COUNT(*) AS total FROM {table} WHERE is_active = 1"
                ).fetchone()
                result[key] = int(row["total"] if row else 0)

        return result
