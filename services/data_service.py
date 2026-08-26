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
    aliases: tuple[str, ...] = ()
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

    def get_overview(self) -> DataOverview:
        with self.database.connect() as connection:
            def count(sql: str, params: tuple[object, ...] = ()) -> int:
                row = connection.execute(sql, params).fetchone()
                return int(row[0] if row else 0)

            return DataOverview(
                active_sources=count("SELECT COUNT(*) FROM source_files WHERE is_active = 1"),
                inactive_sources=count("SELECT COUNT(*) FROM source_files WHERE is_active = 0"),
                active_dialogues=count("SELECT COUNT(*) FROM dialogues WHERE is_active = 1"),
                active_characters=count(
                    """
                    SELECT COUNT(*) FROM characters AS c
                    WHERE c.is_active = 1
                      AND NOT EXISTS (
                          SELECT 1 FROM character_alias AS ca
                          WHERE ca.source_character_id = c.id
                      )
                    """
                ),
                active_talents=count("SELECT COUNT(*) FROM talents WHERE is_active = 1"),
                locked_mappings=count(
                    """
                    SELECT COUNT(*) FROM character_talent AS ct
                    WHERE ct.is_locked = 1
                      AND NOT EXISTS (
                          SELECT 1 FROM character_alias AS ca
                          WHERE ca.source_character_id = ct.character_id
                      )
                    """
                ),
                unresolved_cast=count(
                    """
                    SELECT COUNT(*)
                    FROM dialogues AS d
                    WHERE d.is_active = 1
                      AND (
                          NOT EXISTS (SELECT 1 FROM dialog_cast AS dc WHERE dc.dialogue_id = d.id)
                          OR EXISTS (
                              SELECT 1 FROM dialog_cast AS dc
                              WHERE dc.dialogue_id = d.id AND dc.talent_id IS NULL
                          )
                      )
                    """
                ),
            )

    def get_characters(self) -> list[CharacterAdminRow]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                WITH canonical_cast AS (
                    SELECT
                        dc.dialogue_id,
                        COALESCE(ca.canonical_character_id, dc.character_id) AS character_id,
                        dc.talent_id
                    FROM dialog_cast AS dc
                    LEFT JOIN character_alias AS ca
                      ON ca.source_character_id = dc.character_id
                )
                SELECT
                    c.id,
                    c.name,
                    lm.talent_id AS locked_talent_id,
                    t.name AS locked_talent_name,
                    COALESCE(lm.source, '') AS mapping_source,
                    COUNT(DISTINCT CASE WHEN d.is_active = 1 THEN cc.dialogue_id END)
                        AS active_dialogues,
                    COUNT(DISTINCT CASE
                        WHEN d.is_active = 1 AND cc.talent_id IS NULL THEN cc.dialogue_id
                    END) AS unresolved_dialogues,
                    COALESCE((
                        SELECT GROUP_CONCAT(alias_name, ' / ')
                        FROM (
                            SELECT alias_name
                            FROM character_alias AS aliases
                            WHERE aliases.canonical_character_id = c.id
                            ORDER BY aliases.normalized_alias, aliases.alias_name
                        )
                    ), '') AS aliases
                FROM characters AS c
                LEFT JOIN canonical_cast AS cc ON cc.character_id = c.id
                LEFT JOIN dialogues AS d ON d.id = cc.dialogue_id
                LEFT JOIN character_talent AS lm
                  ON lm.character_id = c.id AND lm.is_locked = 1
                LEFT JOIN talents AS t ON t.id = lm.talent_id
                WHERE c.is_active = 1
                  AND NOT EXISTS (
                      SELECT 1 FROM character_alias AS source_alias
                      WHERE source_alias.source_character_id = c.id
                  )
                GROUP BY c.id, c.name, lm.talent_id, t.name, lm.source
                ORDER BY unresolved_dialogues DESC, c.name COLLATE NOCASE
                """
            ).fetchall()

            missing_character_row = connection.execute(
                """
                SELECT COUNT(DISTINCT d.id) AS total
                FROM dialogues AS d
                JOIN episodes AS e ON e.id = d.episode_id
                WHERE d.is_active = 1 AND e.is_active = 1
                  AND NOT EXISTS (
                      SELECT 1 FROM dialog_cast AS dc WHERE dc.dialogue_id = d.id
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM dialogue_review AS dr
                      WHERE dr.dialogue_id = d.id AND dr.classification = 'NON_DIALOGUE'
                  )
                """
            ).fetchone()

        result = []
        for row in rows:
            alias_text = str(row["aliases"] or "")
            result.append(
                CharacterAdminRow(
                    id=int(row["id"]),
                    name=str(row["name"]),
                    locked_talent_id=(
                        int(row["locked_talent_id"])
                        if row["locked_talent_id"] is not None else None
                    ),
                    locked_talent_name=str(row["locked_talent_name"] or ""),
                    mapping_source=str(row["mapping_source"] or ""),
                    active_dialogues=int(row["active_dialogues"] or 0),
                    unresolved_dialogues=int(row["unresolved_dialogues"] or 0),
                    aliases=tuple(value.strip() for value in alias_text.split(" / ") if value.strip()),
                )
            )

        missing_count = int(missing_character_row["total"] if missing_character_row else 0)
        if missing_count:
            result.insert(
                0,
                CharacterAdminRow(
                    id=None,
                    name="⚠ Character Unknown",
                    locked_talent_id=None,
                    locked_talent_name="⚠ Talent Unknown",
                    mapping_source="Unresolved",
                    active_dialogues=missing_count,
                    unresolved_dialogues=missing_count,
                    aliases=(),
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
                        WHEN d.is_active = 1
                        THEN COALESCE(ca.canonical_character_id, dc.character_id)
                    END) AS character_count,
                    COUNT(DISTINCT CASE WHEN d.is_active = 1 THEN dc.dialogue_id END)
                        AS active_dialogues
                FROM talents AS t
                LEFT JOIN dialog_cast AS dc ON dc.talent_id = t.id
                LEFT JOIN character_alias AS ca ON ca.source_character_id = dc.character_id
                LEFT JOIN dialogues AS d ON d.id = dc.dialogue_id
                WHERE t.is_active = 1
                GROUP BY t.id, t.name
                ORDER BY t.name COLLATE NOCASE
                """
            ).fetchall()
        return [
            TalentAdminRow(
                id=int(r["id"]), name=str(r["name"]),
                character_count=int(r["character_count"] or 0),
                active_dialogues=int(r["active_dialogues"] or 0),
            )
            for r in rows
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
                    CASE
                        WHEN dc.id IS NULL THEN NULL
                        ELSE COALESCE(ca.canonical_character_id, dc.character_id)
                    END AS character_id,
                    CASE
                        WHEN dc.id IS NULL THEN '⚠ Missing Character'
                        ELSE canonical.name
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
                LEFT JOIN character_alias AS ca ON ca.source_character_id = dc.character_id
                LEFT JOIN characters AS canonical
                  ON canonical.id = COALESCE(ca.canonical_character_id, dc.character_id)
                LEFT JOIN talents AS t ON t.id = dc.talent_id
                LEFT JOIN source_files AS sf ON sf.id = d.source_file_id
                WHERE d.is_active = 1 AND e.is_active = 1
                  AND (
                      dc.id IS NULL
                      OR (dc.talent_id IS NULL AND canonical.is_active = 1)
                  )
                ORDER BY
                    CASE WHEN dc.id IS NULL THEN 0 ELSE 1 END,
                    e.episode_number, d.source_row, d.id, COALESCE(dc.position, 0)
                """
            ).fetchall()
        return [
            UnresolvedCastRow(
                dialogue_id=int(r["dialogue_id"]),
                episode_number=int(r["episode_number"]),
                character_id=int(r["character_id"]) if r["character_id"] is not None else None,
                character_name=str(r["character_name"]),
                talent_id=int(r["talent_id"]) if r["talent_id"] is not None else None,
                talent_name=str(r["talent_name"]),
                dialogue=str(r["dialog_text"]),
                source_file_name=str(r["source_file_name"] or ""),
                source_file_path=str(r["source_file_path"] or ""),
            )
            for r in rows
        ]

    def get_sources(self) -> list[SourceAdminRow]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, episode_number, file_name, file_path,
                       fingerprint, modified_at, imported_at, last_seen_at, is_active
                FROM source_files
                ORDER BY is_active DESC, episode_number, file_name COLLATE NOCASE
                """
            ).fetchall()
        return [
            SourceAdminRow(
                id=int(r["id"]),
                episode_number=int(r["episode_number"]) if r["episode_number"] is not None else None,
                file_name=str(r["file_name"]),
                file_path=str(r["file_path"]),
                fingerprint=str(r["fingerprint"] or ""),
                modified_at=str(r["modified_at"] or ""),
                imported_at=str(r["imported_at"] or ""),
                last_seen_at=str(r["last_seen_at"] or ""),
                is_active=bool(r["is_active"]),
            )
            for r in rows
        ]

    def ensure_character(self, name: str) -> int:
        clean_name = name.strip()
        normalized = normalize_key(clean_name)
        if not normalized:
            raise ValueError("Nama character tidak boleh kosong.")
        now = datetime.now().isoformat(timespec="seconds")
        with self.database.connect() as connection:
            alias = connection.execute(
                "SELECT canonical_character_id FROM character_alias WHERE normalized_alias = ?",
                (normalized,),
            ).fetchone()
            if alias:
                return int(alias["canonical_character_id"])
            existing = connection.execute(
                "SELECT id FROM characters WHERE normalized_name = ?",
                (normalized,),
            ).fetchone()
            if existing:
                character_id = int(existing["id"])
                connection.execute(
                    "UPDATE characters SET name = ?, is_active = 1, updated_at = ? WHERE id = ?",
                    (clean_name, now, character_id),
                )
                return character_id
            cursor = connection.execute(
                """
                INSERT INTO characters(name, normalized_name, is_active, created_at, updated_at)
                VALUES(?, ?, 1, ?, ?)
                """,
                (clean_name, normalized, now, now),
            )
            return int(cursor.lastrowid)

    def assign_missing_character(self, dialogue_id: int, character_id: int) -> None:
        with self.database.connect() as connection:
            dialogue = connection.execute(
                "SELECT id FROM dialogues WHERE id = ? AND is_active = 1",
                (int(dialogue_id),),
            ).fetchone()
            character = connection.execute(
                "SELECT id FROM characters WHERE id = ? AND is_active = 1",
                (int(character_id),),
            ).fetchone()
            if dialogue is None:
                raise ValueError("Dialog tidak ditemukan atau sudah inactive.")
            if character is None:
                raise ValueError("Character tidak ditemukan atau sudah inactive.")
            if connection.execute(
                "SELECT 1 FROM dialog_cast WHERE dialogue_id = ? LIMIT 1",
                (int(dialogue_id),),
            ).fetchone():
                raise ValueError(
                    "Dialog ini sudah memiliki character/cast. Gunakan Character Mapping untuk perubahan mapping."
                )
            connection.execute(
                "INSERT INTO dialog_cast(dialogue_id, character_id, talent_id, position) VALUES(?, ?, NULL, 0)",
                (int(dialogue_id), int(character_id)),
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
                    "UPDATE talents SET name = ?, is_active = 1, updated_at = ? WHERE id = ?",
                    (clean_name, now, talent_id),
                )
                return talent_id
            cursor = connection.execute(
                """
                INSERT INTO talents(name, normalized_name, is_active, created_at, updated_at)
                VALUES(?, ?, 1, ?, ?)
                """,
                (clean_name, normalized, now, now),
            )
            return int(cursor.lastrowid)

    def set_locked_mapping(self, character_id: int, talent_id: int) -> None:
        character_id = int(character_id)
        talent_id = int(talent_id)
        now = datetime.now().isoformat(timespec="seconds")
        with self.database.connect() as connection:
            if connection.execute(
                "SELECT 1 FROM characters WHERE id = ? AND is_active = 1",
                (character_id,),
            ).fetchone() is None:
                raise ValueError("Character tidak ditemukan atau sudah inactive.")
            if connection.execute(
                "SELECT 1 FROM talents WHERE id = ? AND is_active = 1",
                (talent_id,),
            ).fetchone() is None:
                raise ValueError("Talent tidak ditemukan atau sudah inactive.")

            affected_cast = connection.execute(
                """
                SELECT dc.dialogue_id, d.episode_id, dc.character_id, dc.position
                FROM dialog_cast AS dc
                JOIN dialogues AS d ON d.id = dc.dialogue_id
                LEFT JOIN character_alias AS ca ON ca.source_character_id = dc.character_id
                WHERE COALESCE(ca.canonical_character_id, dc.character_id) = ?
                  AND d.is_active = 1
                ORDER BY dc.dialogue_id, dc.position, dc.id
                """,
                (character_id,),
            ).fetchall()

            connection.execute(
                "UPDATE character_talent SET is_locked = 0, updated_at = ? WHERE character_id = ? AND is_locked = 1",
                (now, character_id),
            )
            existing = connection.execute(
                "SELECT id FROM character_talent WHERE character_id = ? AND talent_id = ?",
                (character_id, talent_id),
            ).fetchone()
            if existing:
                connection.execute(
                    "UPDATE character_talent SET is_locked = 1, source = 'manual', updated_at = ? WHERE id = ?",
                    (now, int(existing["id"])),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO character_talent(
                        character_id, talent_id, is_locked, source, created_at, updated_at
                    ) VALUES(?, ?, 1, 'manual', ?, ?)
                    """,
                    (character_id, talent_id, now, now),
                )

            source_ids = sorted({int(row["character_id"]) for row in affected_cast})
            if source_ids:
                placeholders = ",".join("?" for _ in source_ids)
                connection.execute(
                    f"""
                    DELETE FROM dialog_cast
                    WHERE character_id IN ({placeholders})
                      AND dialogue_id IN (SELECT id FROM dialogues WHERE is_active = 1)
                    """,
                    source_ids,
                )
                connection.executemany(
                    """
                    INSERT OR IGNORE INTO dialog_cast(
                        dialogue_id, character_id, talent_id, position
                    ) VALUES(?, ?, ?, ?)
                    """,
                    [
                        (
                            int(row["dialogue_id"]),
                            int(row["character_id"]),
                            talent_id,
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
                    WHERE character_id = ? AND episode_id IN ({placeholders})
                    """,
                    (character_id, *episode_ids),
                )

    def unlock_mapping(self, character_id: int) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE character_talent
                SET is_locked = 0,
                    source = CASE WHEN source = 'manual' THEN 'manual-unlocked' ELSE source END,
                    updated_at = ?
                WHERE character_id = ? AND is_locked = 1
                """,
                (now, int(character_id)),
            )

    def validate(self) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        with self.database.connect() as connection:
            schema_row = connection.execute(
                "SELECT value FROM app_meta WHERE key = 'schema_version'"
            ).fetchone()
            schema_value = str(schema_row["value"] if schema_row else "")
            if schema_value != str(SCHEMA_VERSION):
                issues.append(ValidationIssue("ERROR", "SCHEMA_VERSION", f"Database schema {schema_value or '?'} != aplikasi {SCHEMA_VERSION}."))
            for row in connection.execute("PRAGMA foreign_key_check").fetchall():
                issues.append(ValidationIssue("ERROR", "FOREIGN_KEY", f"Foreign key invalid pada tabel {row[0]}, rowid {row[1]}."))
            unresolved = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM dialog_cast AS dc
                JOIN dialogues AS d ON d.id = dc.dialogue_id
                WHERE d.is_active = 1 AND dc.talent_id IS NULL
                """
            ).fetchone()
            if int(unresolved["total"] or 0):
                issues.append(ValidationIssue("WARNING", "UNRESOLVED_CAST", f"{int(unresolved['total'])} cast dialog aktif belum memiliki talent."))
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
