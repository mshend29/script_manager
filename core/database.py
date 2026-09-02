from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from core.app_paths import database_backups_dir


SCHEMA_VERSION = 10


class DatabaseCompatibilityError(RuntimeError):
    pass


class _ManagedConnection(sqlite3.Connection):
    """sqlite3 connection that closes when used as a context manager.

    sqlite3.Connection.__exit__ only commits/rolls back; it does not close the
    file handle. That behavior prevents directory rename/move on Windows while
    project.db is still open.
    """

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            factory=_ManagedConnection,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        existing_version = None
        if self.path.exists():
            existing_version = self._validate_existing_schema_version()
            if (
                existing_version is not None
                and existing_version < SCHEMA_VERSION
            ):
                self._backup_before_migration(existing_version)

        self.path.parent.mkdir(parents=True, exist_ok=True)

        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS app_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS smproj_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS project_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL
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
                    base_normalized_name TEXT,
                    identity_talent_id INTEGER,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (identity_talent_id)
                        REFERENCES talents(id)
                        ON DELETE SET NULL
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
                    source_signature TEXT,
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

                CREATE TABLE IF NOT EXISTS dialog_source_cast (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dialogue_id INTEGER NOT NULL,
                    character_id INTEGER NOT NULL,
                    talent_id INTEGER,
                    position INTEGER NOT NULL DEFAULT 0,
                    resolution_source TEXT,
                    UNIQUE(dialogue_id, position),
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

                CREATE TABLE IF NOT EXISTS character_alias (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias_name TEXT NOT NULL,
                    normalized_alias TEXT NOT NULL UNIQUE,
                    canonical_character_id INTEGER NOT NULL,
                    source_character_id INTEGER UNIQUE,
                    source_locked_talent_id INTEGER,
                    created_at TEXT,
                    updated_at TEXT,
                    CHECK(source_character_id IS NULL OR source_character_id != canonical_character_id),
                    FOREIGN KEY (canonical_character_id)
                        REFERENCES characters(id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (source_character_id)
                        REFERENCES characters(id)
                        ON DELETE SET NULL,
                    FOREIGN KEY (source_locked_talent_id)
                        REFERENCES talents(id)
                        ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS character_alias_dialogue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias_id INTEGER NOT NULL,
                    dialogue_id INTEGER NOT NULL,
                    talent_id INTEGER,
                    position INTEGER NOT NULL DEFAULT 0,
                    created_canonical INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(alias_id, dialogue_id, position),
                    FOREIGN KEY (alias_id)
                        REFERENCES character_alias(id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (dialogue_id)
                        REFERENCES dialogues(id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (talent_id)
                        REFERENCES talents(id)
                        ON DELETE SET NULL
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

                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entity_type TEXT,
                    entity_id TEXT,
                    summary TEXT NOT NULL,
                    details_json TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_source_files_episode
                    ON source_files(episode_number);

                CREATE INDEX IF NOT EXISTS idx_dialogues_episode
                    ON dialogues(episode_id);

                CREATE INDEX IF NOT EXISTS idx_dialogues_source_signature
                    ON dialogues(source_file_id, source_signature);

                CREATE INDEX IF NOT EXISTS idx_dialog_cast_dialogue
                    ON dialog_cast(dialogue_id);

                CREATE INDEX IF NOT EXISTS idx_dialog_cast_character
                    ON dialog_cast(character_id);

                CREATE INDEX IF NOT EXISTS idx_dialog_cast_talent
                    ON dialog_cast(talent_id);

                CREATE INDEX IF NOT EXISTS idx_dialog_source_cast_dialogue
                    ON dialog_source_cast(dialogue_id);

                CREATE INDEX IF NOT EXISTS idx_dialog_source_cast_character
                    ON dialog_source_cast(character_id);

                CREATE INDEX IF NOT EXISTS idx_dialog_source_cast_talent
                    ON dialog_source_cast(talent_id);

                CREATE INDEX IF NOT EXISTS idx_dialogue_review_classification
                    ON dialogue_review(classification);

                CREATE INDEX IF NOT EXISTS idx_character_alias_canonical
                    ON character_alias(canonical_character_id);

                CREATE INDEX IF NOT EXISTS idx_character_alias_source
                    ON character_alias(source_character_id);

                CREATE INDEX IF NOT EXISTS idx_character_alias_dialogue_alias
                    ON character_alias_dialogue(alias_id);

                CREATE INDEX IF NOT EXISTS idx_character_alias_dialogue_dialogue
                    ON character_alias_dialogue(dialogue_id);

                CREATE UNIQUE INDEX IF NOT EXISTS idx_character_talent_one_locked
                    ON character_talent(character_id)
                    WHERE is_locked = 1;

                CREATE INDEX IF NOT EXISTS idx_audit_log_created
                    ON audit_log(created_at DESC);

                CREATE INDEX IF NOT EXISTS idx_audit_log_event
                    ON audit_log(event_type);
                """
            )

            self._migrate_stem_status_v3(connection)
            self._migrate_character_identity_v6(connection)
            self._migrate_dialogue_source_signature_v10(connection)

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

    def _validate_existing_schema_version(self) -> int | None:
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
                return None

            row = connection.execute(
                "SELECT value FROM app_meta WHERE key = 'schema_version'"
            ).fetchone()
            if row is None:
                return None

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
            return version
        finally:
            connection.close()

    def _backup_before_migration(self, from_version: int) -> Path:
        project_id = self.get_smproj_meta("project_id", default="")
        backup_dir = database_backups_dir(
            self.path,
            project_id=project_id,
        ) / "Migrations"
        backup_dir.mkdir(parents=True, exist_ok=True)

        stamp = __import__("datetime").datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )
        extension = ".smproj" if self.path.suffix.casefold() == ".smproj" else ".db"
        target = backup_dir / (
            f"{self.path.stem}_before_schema_v{from_version}_to_v"
            f"{SCHEMA_VERSION}_{stamp}{extension}"
        )

        source = sqlite3.connect(self.path)
        destination = sqlite3.connect(target)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()

        return target

    @staticmethod
    def _migrate_dialogue_source_signature_v10(
        connection: sqlite3.Connection,
    ) -> None:
        columns = {
            str(row["name"])
            for row in connection.execute(
                "PRAGMA table_info(dialogues)"
            ).fetchall()
        }

        if "source_signature" not in columns:
            connection.execute(
                "ALTER TABLE dialogues "
                "ADD COLUMN source_signature TEXT"
            )

        # Before schema v10, dialog_uid itself was the parser's content-derived
        # signature. Preserve that value as the initial source signature while
        # allowing dialog_uid to become a persistent application identity.
        connection.execute(
            """
            UPDATE dialogues
            SET source_signature = dialog_uid
            WHERE source_signature IS NULL
               OR TRIM(source_signature) = ''
            """
        )

    @staticmethod
    def _migrate_character_identity_v6(
        connection: sqlite3.Connection,
    ) -> None:
        columns = {
            str(row["name"])
            for row in connection.execute(
                "PRAGMA table_info(characters)"
            ).fetchall()
        }

        if "base_normalized_name" not in columns:
            connection.execute(
                "ALTER TABLE characters "
                "ADD COLUMN base_normalized_name TEXT"
            )

        if "identity_talent_id" not in columns:
            connection.execute(
                "ALTER TABLE characters "
                "ADD COLUMN identity_talent_id INTEGER "
                "REFERENCES talents(id) ON DELETE SET NULL"
            )

        # Preserve the original normalized label as the source-name identity.
        # normalized_name remains UNIQUE for backward compatibility and is used
        # only as an internal storage key for newly split identities.
        connection.execute(
            """
            UPDATE characters
            SET base_normalized_name = normalized_name
            WHERE base_normalized_name IS NULL
               OR TRIM(base_normalized_name) = ''
            """
        )

        # Existing projects had one character row per normalized name. When a
        # character already has one authoritative locked talent, use it as the
        # best migration hint for its source identity. Multi-talent characters
        # intentionally remain unbound so crowd/multi-cast workflows are not
        # split automatically.
        connection.execute(
            """
            UPDATE characters AS c
            SET identity_talent_id = (
                SELECT ct.talent_id
                FROM character_talent AS ct
                WHERE ct.character_id = c.id
                  AND ct.is_locked = 1
                ORDER BY
                    CASE WHEN ct.source = 'manual' THEN 0 ELSE 1 END,
                    ct.id
                LIMIT 1
            )
            WHERE c.identity_talent_id IS NULL
              AND EXISTS (
                  SELECT 1
                  FROM character_talent AS ct
                  WHERE ct.character_id = c.id
                    AND ct.is_locked = 1
              )
            """
        )

        connection.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_characters_base_normalized
                ON characters(base_normalized_name);

            CREATE INDEX IF NOT EXISTS idx_characters_identity_talent
                ON characters(identity_talent_id);

            CREATE UNIQUE INDEX IF NOT EXISTS idx_characters_source_identity
                ON characters(base_normalized_name, identity_talent_id)
                WHERE identity_talent_id IS NOT NULL;

            CREATE UNIQUE INDEX IF NOT EXISTS idx_characters_unbound_identity
                ON characters(base_normalized_name)
                WHERE identity_talent_id IS NULL;
            """
        )

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

        # Old status rows were scoped only to Episode + Talent. Preserve them
        # only when that pair maps to exactly one character, otherwise there is
        # no safe way to decide which character owned the old downstream state.
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

    def get_smproj_meta(
        self,
        key: str,
        *,
        default: str = "",
    ) -> str:
        if not self.path.exists():
            return default

        try:
            with self.connect() as connection:
                table = connection.execute(
                    """
                    SELECT 1
                    FROM sqlite_master
                    WHERE type = 'table' AND name = 'smproj_meta'
                    """
                ).fetchone()
                if table is None:
                    return default

                row = connection.execute(
                    "SELECT value FROM smproj_meta WHERE key = ?",
                    (str(key),),
                ).fetchone()
        except sqlite3.DatabaseError:
            return default

        return str(row["value"] if row else default)

    def set_smproj_meta(self, values: dict[str, str]) -> None:
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO smproj_meta(key, value)
                VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                [
                    (str(key), str(value))
                    for key, value in values.items()
                ],
            )

    def load_project_settings(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}

        with self.connect() as connection:
            table = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table' AND name = 'project_settings'
                """
            ).fetchone()
            if table is None:
                return {}

            rows = connection.execute(
                "SELECT key, value_json FROM project_settings"
            ).fetchall()

        result: dict[str, Any] = {}
        for row in rows:
            key = str(row["key"])
            raw = str(row["value_json"])
            try:
                result[key] = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise DatabaseCompatibilityError(
                    f"Project setting {key!r} tidak valid."
                ) from exc
        return result

    def save_project_settings(self, values: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM project_settings")
            connection.executemany(
                """
                INSERT INTO project_settings(key, value_json)
                VALUES(?, ?)
                """,
                [
                    (
                        str(key),
                        json.dumps(value, ensure_ascii=False),
                    )
                    for key, value in values.items()
                ],
            )

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
