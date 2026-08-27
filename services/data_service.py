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
    id: int | None
    name: str
    locked_talent_id: int | None
    locked_talent_name: str
    mapping_source: str
    active_dialogues: int
    unresolved_dialogues: int
    missing_character: bool = False


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
    character_id: int | None
    character_name: str
    talent_id: int | None
    talent_name: str
    dialogue: str
    source_file_name: str
    source_file_path: str


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
                    FROM dialogues AS d
                    WHERE d.is_active = 1
                      AND (
                          NOT EXISTS (
                              SELECT 1
                              FROM dialog_cast AS dc
                              WHERE dc.dialogue_id = d.id
                          )
                          OR EXISTS (
                              SELECT 1
                              FROM dialog_cast AS dc
                              WHERE dc.dialogue_id = d.id
                                AND dc.talent_id IS NULL
                          )
                      )
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
                ORDER BY
                    unresolved_dialogues DESC,
                    c.name COLLATE NOCASE,
                    t.name COLLATE NOCASE,
                    c.id
                """
            ).fetchall()

            missing_character_row = connection.execute(
                """
                SELECT COUNT(DISTINCT d.id) AS total
                FROM dialogues AS d
                JOIN episodes AS e ON e.id = d.episode_id
                WHERE d.is_active = 1
                  AND e.is_active = 1
                  AND NOT EXISTS (
                      SELECT 1
                      FROM dialog_cast AS dc
                      WHERE dc.dialogue_id = d.id
                  )
                """
            ).fetchone()

        result = [
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
                missing_character=False,
            )
            for row in rows
        ]

        missing_character_count = int(
            missing_character_row["total"] if missing_character_row else 0
        )
        if missing_character_count:
            result.insert(
                0,
                CharacterAdminRow(
                    id=None,
                    name="⚠ Character Unknown",
                    locked_talent_id=None,
                    locked_talent_name="⚠ Talent Unknown",
                    mapping_source="Unresolved",
                    active_dialogues=missing_character_count,
                    unresolved_dialogues=missing_character_count,
                    missing_character=True,
                ),
            )

        return result

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
                    dc.character_id,
                    CASE
                        WHEN dc.id IS NULL THEN '⚠ Missing Character'
                        ELSE c.name
                    END AS character_name,
                    dc.talent_id,
                    CASE
                        WHEN dc.id IS NULL OR dc.talent_id IS NULL
                        THEN '⚠ Missing Talent'
                        ELSE t.name
                    END AS talent_name,
                    d.dialog_text,
                    COALESCE(sf.file_name, '') AS source_file_name,
                    COALESCE(sf.file_path, '') AS source_file_path
                FROM dialogues AS d
                JOIN episodes AS e ON e.id = d.episode_id
                LEFT JOIN dialog_cast AS dc ON dc.dialogue_id = d.id
                LEFT JOIN characters AS c ON c.id = dc.character_id
                LEFT JOIN talents AS t ON t.id = dc.talent_id
                LEFT JOIN source_files AS sf ON sf.id = d.source_file_id
                WHERE d.is_active = 1
                  AND e.is_active = 1
                  AND (
                      dc.id IS NULL
                      OR (
                          dc.talent_id IS NULL
                          AND c.is_active = 1
                      )
                  )
                ORDER BY
                    CASE WHEN dc.id IS NULL THEN 0 ELSE 1 END,
                    e.episode_number,
                    d.source_row,
                    d.id,
                    COALESCE(dc.position, 0)
                """
            ).fetchall()

        return [
            UnresolvedCastRow(
                dialogue_id=int(row["dialogue_id"]),
                episode_number=int(row["episode_number"]),
                character_id=(
                    int(row["character_id"])
                    if row["character_id"] is not None
                    else None
                ),
                character_name=str(row["character_name"]),
                talent_id=(
                    int(row["talent_id"])
                    if row["talent_id"] is not None
                    else None
                ),
                talent_name=str(row["talent_name"]),
                dialogue=str(row["dialog_text"]),
                source_file_name=str(row["source_file_name"] or ""),
                source_file_path=str(row["source_file_path"] or ""),
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

    def ensure_character(self, name: str) -> int:
        clean_name = name.strip()
        normalized = normalize_key(clean_name)
        if not normalized:
            raise ValueError("Nama character tidak boleh kosong.")

        now = datetime.now().isoformat(timespec="seconds")
        with self.database.connect() as connection:
            existing = connection.execute(
                """
                SELECT id
                FROM characters
                WHERE COALESCE(
                    NULLIF(base_normalized_name, ''),
                    normalized_name
                ) = ?
                  AND identity_talent_id IS NULL
                ORDER BY id
                LIMIT 1
                """,
                (normalized,),
            ).fetchone()

            if existing is None:
                variants = connection.execute(
                    """
                    SELECT id
                    FROM characters
                    WHERE COALESCE(
                        NULLIF(base_normalized_name, ''),
                        normalized_name
                    ) = ?
                      AND is_active = 1
                    ORDER BY id
                    """,
                    (normalized,),
                ).fetchall()
                if len(variants) == 1:
                    existing = variants[0]

            if existing:
                character_id = int(existing["id"])
                connection.execute(
                    """
                    UPDATE characters
                    SET is_active = 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (now, character_id),
                )
                return character_id

            storage_key = normalized
            if connection.execute(
                "SELECT 1 FROM characters WHERE normalized_name = ?",
                (storage_key,),
            ).fetchone():
                storage_key = f"{normalized}||unbound"
                serial = 2
                while connection.execute(
                    "SELECT 1 FROM characters WHERE normalized_name = ?",
                    (storage_key,),
                ).fetchone():
                    storage_key = f"{normalized}||unbound:{serial}"
                    serial += 1

            cursor = connection.execute(
                """
                INSERT INTO characters(
                    name,
                    normalized_name,
                    base_normalized_name,
                    identity_talent_id,
                    is_active,
                    created_at,
                    updated_at
                ) VALUES(?, ?, ?, NULL, 1, ?, ?)
                """,
                (clean_name, storage_key, normalized, now, now),
            )
            return int(cursor.lastrowid)

    def assign_missing_character(self, dialogue_id: int, character_id: int) -> None:
        with self.database.connect() as connection:
            dialogue = connection.execute(
                "SELECT id FROM dialogues WHERE id = ? AND is_active = 1",
                (dialogue_id,),
            ).fetchone()
            character = connection.execute(
                "SELECT id FROM characters WHERE id = ? AND is_active = 1",
                (character_id,),
            ).fetchone()
            if dialogue is None:
                raise ValueError("Dialog tidak ditemukan atau sudah inactive.")
            if character is None:
                raise ValueError("Character tidak ditemukan atau sudah inactive.")

            existing_cast = connection.execute(
                "SELECT 1 FROM dialog_cast WHERE dialogue_id = ? LIMIT 1",
                (dialogue_id,),
            ).fetchone()
            if existing_cast is not None:
                raise ValueError(
                    "Dialog ini sudah memiliki character/cast. Gunakan Character Mapping untuk perubahan mapping."
                )

            connection.execute(
                """
                INSERT INTO dialog_cast(
                    dialogue_id, character_id, talent_id, position
                ) VALUES(?, ?, NULL, 0)
                """,
                (dialogue_id, character_id),
            )

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

            affected_cast = connection.execute(
                """
                SELECT
                    dc.dialogue_id,
                    d.episode_id,
                    MIN(dc.position) AS position
                FROM dialog_cast AS dc
                JOIN dialogues AS d ON d.id = dc.dialogue_id
                WHERE dc.character_id = ?
                  AND d.is_active = 1
                GROUP BY dc.dialogue_id, d.episode_id
                ORDER BY dc.dialogue_id
                """,
                (character_id,),
            ).fetchall()

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

            connection.execute(
                """
                DELETE FROM dialog_cast
                WHERE character_id = ?
                  AND dialogue_id IN (
                      SELECT id FROM dialogues WHERE is_active = 1
                  )
                """,
                (character_id,),
            )

            connection.executemany(
                """
                INSERT INTO dialog_cast(
                    dialogue_id,
                    character_id,
                    talent_id,
                    position
                )
                VALUES(?, ?, ?, ?)
                """,
                [
                    (
                        int(row["dialogue_id"]),
                        int(character_id),
                        int(talent_id),
                        int(row["position"] or 0),
                    )
                    for row in affected_cast
                ],
            )

            episode_ids = sorted({int(row["episode_id"]) for row in affected_cast})
            if episode_ids:
                placeholders = ",".join("?" for _ in episode_ids)
                connection.execute(
                    f"""
                    DELETE FROM stem_status
                    WHERE character_id = ?
                      AND episode_id IN ({placeholders})
                    """,
                    (int(character_id), *episode_ids),
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

            missing_cast = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM dialogues AS d
                WHERE d.is_active = 1
                  AND NOT EXISTS (
                      SELECT 1
                      FROM dialog_cast AS dc
                      WHERE dc.dialogue_id = d.id
                  )
                """
            ).fetchone()
            missing_cast_count = int(missing_cast["total"] or 0)
            if missing_cast_count:
                issues.append(
                    ValidationIssue(
                        "WARNING",
                        "ACTIVE_DIALOGUE_NO_CAST",
                        f"{missing_cast_count} dialog aktif tidak memiliki character/cast dan memerlukan keputusan manual.",
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

            empty_active_episodes = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM episodes AS e
                JOIN source_files AS sf ON sf.id = e.source_file_id
                WHERE e.is_active = 1
                  AND sf.is_active = 1
                  AND EXISTS (
                      SELECT 1
                      FROM dialogues AS history
                      WHERE history.episode_id = e.id
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM dialogues AS active_dialogue
                      WHERE active_dialogue.episode_id = e.id
                        AND active_dialogue.is_active = 1
                  )
                """
            ).fetchone()
            empty_active_episode_count = int(empty_active_episodes["total"] or 0)
            if empty_active_episode_count:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "ACTIVE_EPISODE_WITHOUT_ACTIVE_DIALOGUES",
                        f"{empty_active_episode_count} episode/source aktif hanya memiliki dialog inactive.",
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
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        target = backup_dir / f"project_{stamp}.db"
        suffix = 1
        while target.exists():
            target = backup_dir / f"project_{stamp}_{suffix}.db"
            suffix += 1

        with self.database.connect() as source:
            destination = sqlite3.connect(target)
            try:
                source.backup(destination)
            finally:
                destination.close()

        return target
