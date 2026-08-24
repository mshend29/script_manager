from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.database import Database, SCHEMA_VERSION
from import_engine.normalizer import normalize_key


@dataclass(frozen=True)
class DataOverview:
    active_sources: int
    inactive_sources: int
    active_dialogues: int
    active_characters: int
    active_talents: int
    locked_mappings: int
    unresolved_cast: int


@dataclass(frozen=True)
class CharacterAdminRow:
    id: int
    name: str
    locked_talent_id: int | None
    locked_talent_name: str
    mapping_source: str
    active_dialogues: int
    unresolved_dialogues: int


@dataclass(frozen=True)
class TalentAdminRow:
    id: int
    name: str
    character_count: int
    active_dialogues: int


@dataclass(frozen=True)
class UnresolvedCastRow:
    dialogue_id: int
    episode_number: int
    character_id: int
    character_name: str
    dialogue: str
    source_file_name: str


@dataclass(frozen=True)
class SourceAdminRow:
    id: int
    episode_number: int | None
    file_name: str
    file_path: str
    fingerprint: str
    modified_at: str
    imported_at: str
    last_seen_at: str
    is_active: bool


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str


class DataService:
    def __init__(self, database: Database):
        self.database = database

    # ------------------------------------------------------------------
    # READ MODELS
    # ------------------------------------------------------------------

    def get_overview(self) -> DataOverview:
        with self.database.connect() as connection:
            def count(sql: str, params: tuple[object, ...] = ()) -> int:
                row = connection.execute(sql, params).fetchone()
                return int(row[0] if row else 0)

            return DataOverview(
                active_sources=count("SELECT COUNT(*) FROM source_files WHERE is_active = 1"),
                inactive_sources=count("SELECT COUNT(*) FROM source_files WHERE is_active = 0"),
                active_dialogues=count("SELECT COUNT(*) FROM dialogues WHERE is_active = 1"),
                active_characters=count("SELECT COUNT(*) FROM characters WHERE is_active = 1"),
                active_talents=count("SELECT COUNT(*) FROM talents WHERE is_active = 1"),
                locked_mappings=count(
                    "SELECT COUNT(*) FROM character_talent WHERE is_locked = 1"
                ),
                unresolved_cast=count(
                    """
                    SELECT COUNT(*)
                    FROM dialog_cast AS dc
                    JOIN dialogues AS d ON d.id = dc.dialogue_id
                    WHERE d.is_active = 1
                      AND dc.talent_id IS NULL
                    """
                ),
            )

    def get_characters(self) -> list[CharacterAdminRow]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    c.id,
                    c.name,
                    lm.talent_id AS locked_talent_id,
                    t.name AS locked_talent_name,
                    COALESCE(lm.source, '') AS mapping_source,
                    COUNT(DISTINCT CASE WHEN d.is_active = 1 THEN dc.dialogue_id END)
                        AS active_dialogues,
                    COUNT(DISTINCT CASE
                        WHEN d.is_active = 1 AND dc.talent_id IS NULL
                        THEN dc.dialogue_id
                    END) AS unresolved_dialogues
                FROM characters AS c
                LEFT JOIN dialog_cast AS dc ON dc.character_id = c.id
                LEFT JOIN dialogues AS d ON d.id = dc.dialogue_id
                LEFT JOIN character_talent AS lm
                    ON lm.character_id = c.id AND lm.is_locked = 1
                LEFT JOIN talents AS t ON t.id = lm.talent_id
                WHERE c.is_active = 1
                GROUP BY
                    c.id, c.name,
                    lm.talent_id, t.name, lm.source
                ORDER BY c.name COLLATE NOCASE
                """
            ).fetchall()

        return [
            CharacterAdminRow(
                id=int(row["id"]),
                name=str(row["name"]),
                locked_talent_id=(
                    int(row["locked_talent_id"])
                    if row["locked_talent_id"] is not None
                    else None
                ),
                locked_talent_name=str(row["locked_talent_name"] or ""),
                mapping_source=str(row["mapping_source"] or ""),
                active_dialogues=int(row["active_dialogues"] or 0),
                unresolved_dialogues=int(row["unresolved_dialogues"] or 0),
            )
            for row in rows
        ]

    def get_talents(self) -> list[TalentAdminRow]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    t.id,
                    t.name,
                    COUNT(DISTINCT CASE
                        WHEN d.is_active = 1 THEN dc.character_id
                    END) AS character_count,
                    COUNT(DISTINCT CASE
                        WHEN d.is_active = 1 THEN dc.dialogue_id
                    END) AS active_dialogues
                FROM talents AS t
                LEFT JOIN dialog_cast AS dc ON dc.talent_id = t.id
                LEFT JOIN dialogues AS d ON d.id = dc.dialogue_id
                WHERE t.is_active = 1
                GROUP BY t.id, t.name
                ORDER BY t.name COLLATE NOCASE
                """
            ).fetchall()

        return [
            TalentAdminRow(
                id=int(row["id"]),
                name=str(row["name"]),
                character_count=int(row["character_count"] or 0),
                active_dialogues=int(row["active_dialogues"] or 0),
            )
            for row in rows
        ]

    def get_talent_options(self) -> list[tuple[int, str]]:
        return [(row.id, row.name) for row in self.get_talents()]

    def get_unresolved_cast(self) -> list[UnresolvedCastRow]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    d.id AS dialogue_id,
                    e.episode_number,
                    c.id AS character_id,
                    c.name AS character_name,
                    d.dialog_text,
                    COALESCE(sf.file_name, '') AS source_file_name
                FROM dialog_cast AS dc
                JOIN dialogues AS d ON d.id = dc.dialogue_id
                JOIN episodes AS e ON e.id = d.episode_id
                JOIN characters AS c ON c.id = dc.character_id
                LEFT JOIN source_files AS sf ON sf.id = d.source_file_id
                WHERE d.is_active = 1
                  AND e.is_active = 1
                  AND c.is_active = 1
                  AND dc.talent_id IS NULL
                ORDER BY e.episode_number, d.source_row, d.id, dc.position
                """
            ).fetchall()

        return [
            UnresolvedCastRow(
                dialogue_id=int(row["dialogue_id"]),
                episode_number=int(row["episode_number"]),
                character_id=int(row["character_id"]),
                character_name=str(row["character_name"]),
                dialogue=str(row["dialog_text"]),
                source_file_name=str(row["source_file_name"] or ""),
            )
            for row in rows
        ]

    def get_sources(self) -> list[SourceAdminRow]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id, episode_number, file_name, file_path,
                    fingerprint, modified_at, imported_at, last_seen_at,
                    is_active
                FROM source_files
                ORDER BY is_active DESC, episode_number, file_name COLLATE NOCASE
                """
            ).fetchall()

        return [
            SourceAdminRow(
                id=int(row["id"]),
                episode_number=(
                    int(row["episode_number"])
                    if row["episode_number"] is not None
                    else None
                ),
                file_name=str(row["file_name"]),
                file_path=str(row["file_path"]),
                fingerprint=str(row["fingerprint"] or ""),
                modified_at=str(row["modified_at"] or ""),
                imported_at=str(row["imported_at"] or ""),
                last_seen_at=str(row["last_seen_at"] or ""),
                is_active=bool(row["is_active"]),
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # CHARACTER / TALENT ADMIN
    # ------------------------------------------------------------------

    def ensure_talent(self, name: str) -> int:
        clean_name = name.strip()
        normalized = normalize_key(clean_name)
        if not normalized:
            raise ValueError("Nama talent tidak boleh kosong.")

        now = datetime.now().isoformat(timespec="seconds")
        with self.database.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM talents WHERE normalized_name = ?",
                (normalized,),
            ).fetchone()
            if existing:
                talent_id = int(existing["id"])
                connection.execute(
                    """
                    UPDATE talents
                    SET name = ?, is_active = 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (clean_name, now, talent_id),
                )
                return talent_id

            cursor = connection.execute(
                """
                INSERT INTO talents(
                    name, normalized_name, is_active, created_at, updated_at
                ) VALUES(?, ?, 1, ?, ?)
                """,
                (clean_name, normalized, now, now),
            )
            return int(cursor.lastrowid)

    def set_locked_mapping(self, character_id: int, talent_id: int) -> None:
        now = datetime.now().isoformat(timespec="seconds")

        with self.database.connect() as connection:
            character = connection.execute(
                "SELECT id FROM characters WHERE id = ? AND is_active = 1",
                (character_id,),
            ).fetchone()
            talent = connection.execute(
                "SELECT id FROM talents WHERE id = ? AND is_active = 1",
                (talent_id,),
            ).fetchone()
            if character is None:
                raise ValueError("Character tidak ditemukan atau sudah inactive.")
            if talent is None:
                raise ValueError("Talent tidak ditemukan atau sudah inactive.")

            connection.execute(
                """
                UPDATE character_talent
                SET is_locked = 0, updated_at = ?
                WHERE character_id = ? AND is_locked = 1
                """,
                (now, character_id),
            )

            existing = connection.execute(
                """
                SELECT id
                FROM character_talent
                WHERE character_id = ? AND talent_id = ?
                """,
                (character_id, talent_id),
            ).fetchone()

            if existing:
                connection.execute(
                    """
                    UPDATE character_talent
                    SET is_locked = 1,
                        source = 'manual',
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (now, int(existing["id"])),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO character_talent(
                        character_id, talent_id, is_locked,
                        source, created_at, updated_at
                    ) VALUES(?, ?, 1, 'manual', ?, ?)
                    """,
                    (character_id, talent_id, now, now),
                )

            # A manual lock is authoritative for the active cast.  This makes
            # SCRIPT, DIALOG and TRACKING consistent immediately.
            connection.execute(
                """
                UPDATE dialog_cast
                SET talent_id = ?
                WHERE character_id = ?
                  AND dialogue_id IN (
                      SELECT id FROM dialogues WHERE is_active = 1
                  )
                """,
                (talent_id, character_id),
            )

    def unlock_mapping(self, character_id: int) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE character_talent
                SET is_locked = 0,
                    source = CASE
                        WHEN source = 'manual' THEN 'manual-unlocked'
                        ELSE source
                    END,
                    updated_at = ?
                WHERE character_id = ? AND is_locked = 1
                """,
                (now, character_id),
            )

    # ------------------------------------------------------------------
    # VALIDATION / MAINTENANCE
    # ------------------------------------------------------------------

    def validate(self) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        with self.database.connect() as connection:
            schema_row = connection.execute(
                "SELECT value FROM app_meta WHERE key = 'schema_version'"
            ).fetchone()
            schema_value = str(schema_row["value"] if schema_row else "")
            if schema_value != str(SCHEMA_VERSION):
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "SCHEMA_VERSION",
                        f"Database schema {schema_value or '?'} != aplikasi {SCHEMA_VERSION}.",
                    )
                )

            foreign_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
            for row in foreign_rows:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "FOREIGN_KEY",
                        f"Foreign key invalid pada tabel {row[0]}, rowid {row[1]}.",
                    )
                )

            unresolved = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM dialog_cast AS dc
                JOIN dialogues AS d ON d.id = dc.dialogue_id
                WHERE d.is_active = 1 AND dc.talent_id IS NULL
                """
            ).fetchone()
            unresolved_count = int(unresolved["total"] or 0)
            if unresolved_count:
                issues.append(
                    ValidationIssue(
                        "WARNING",
                        "UNRESOLVED_CAST",
                        f"{unresolved_count} cast dialog aktif belum memiliki talent.",
                    )
                )

            duplicate_sources = connection.execute(
                """
                SELECT episode_number, COUNT(*) AS total
                FROM source_files
                WHERE is_active = 1 AND episode_number IS NOT NULL
                GROUP BY episode_number
                HAVING COUNT(*) > 1
                ORDER BY episode_number
                """
            ).fetchall()
            for row in duplicate_sources:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "DUPLICATE_SOURCE_EPISODE",
                        f"Episode {row['episode_number']} memiliki {row['total']} source aktif.",
                    )
                )

            invalid_dialogues = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM dialogues AS d
                JOIN episodes AS e ON e.id = d.episode_id
                WHERE d.is_active = 1 AND e.is_active = 0
                """
            ).fetchone()
            invalid_dialogue_count = int(invalid_dialogues["total"] or 0)
            if invalid_dialogue_count:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "ACTIVE_DIALOGUE_INACTIVE_EPISODE",
                        f"{invalid_dialogue_count} dialog aktif berada pada episode inactive.",
                    )
                )

            inactive_entity_cast = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM dialog_cast AS dc
                JOIN dialogues AS d ON d.id = dc.dialogue_id
                JOIN characters AS c ON c.id = dc.character_id
                LEFT JOIN talents AS t ON t.id = dc.talent_id
                WHERE d.is_active = 1
                  AND (c.is_active = 0 OR (dc.talent_id IS NOT NULL AND t.is_active = 0))
                """
            ).fetchone()
            inactive_entity_count = int(inactive_entity_cast["total"] or 0)
            if inactive_entity_count:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "INACTIVE_CAST_ENTITY",
                        f"{inactive_entity_count} cast aktif menunjuk character/talent inactive.",
                    )
                )

            invalid_downstream = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM stem_status AS ss
                WHERE ss.status IN ('READY_TO_STEM', 'STEMMED', 'DELIVERED')
                  AND EXISTS (
                      SELECT 1
                      FROM dialogues AS d
                      JOIN dialog_cast AS dc ON dc.dialogue_id = d.id
                      LEFT JOIN recording_status AS rs ON rs.dialogue_id = d.id
                      WHERE d.episode_id = ss.episode_id
                        AND dc.talent_id = ss.talent_id
                        AND dc.character_id = ss.character_id
                        AND d.is_active = 1
                        AND COALESCE(rs.is_recorded, 0) = 0
                  )
                """
            ).fetchone()
            invalid_downstream_count = int(invalid_downstream["total"] or 0)
            if invalid_downstream_count:
                issues.append(
                    ValidationIssue(
                        "WARNING",
                        "DOWNSTREAM_BEFORE_RECORDED",
                        f"{invalid_downstream_count} tracking downstream belum memiliki recording lengkap.",
                    )
                )

        return issues

    def rebuild_indexes(self) -> None:
        with self.database.connect() as connection:
            connection.execute("REINDEX")
            connection.execute("ANALYZE")

    def backup_database(self) -> Path:
        backup_dir = self.database.path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = backup_dir / f"project_{stamp}.db"

        with self.database.connect() as source:
            destination = sqlite3.connect(target)
            try:
                source.backup(destination)
            finally:
                destination.close()

        return target
