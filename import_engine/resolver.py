from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from import_engine.normalizer import normalize_key
from import_engine.parser import ParsedDialogueRow, ScriptParseResult


@dataclass(frozen=True)
class ResolvedCastMember:
    character_id: int
    character_name: str
    talent_id: int | None
    talent_name: str
    source: str
    alias_ids: tuple[int, ...] = ()


@dataclass
class ResolverReport:
    auto_locked: int = 0
    unresolved_cast: int = 0
    warnings: list[str] = field(default_factory=list)


class CharacterTalentResolver:
    """Resolve source cast labels against canonical characters and talents.

    Stable talent mappings are learned only from unambiguous single-character /
    single-talent rows. Manual character aliases are authoritative and are
    resolved before creating a new character entity.
    """

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def ensure_entities(
        self,
        parse_results: Iterable[ScriptParseResult],
        *,
        timestamp: str,
    ) -> None:
        for parse_result in parse_results:
            for row in parse_result.rows:
                for character in row.characters:
                    self.ensure_character(character, timestamp=timestamp)
                for talent in row.talents:
                    self.ensure_talent(talent, timestamp=timestamp)

    def ensure_character(self, name: str, *, timestamp: str) -> int:
        character_id, _, _ = self._resolve_character_identity(
            name,
            timestamp=timestamp,
        )
        return character_id

    def _resolve_character_identity(
        self,
        name: str,
        *,
        timestamp: str,
    ) -> tuple[int, str, tuple[int, ...]]:
        normalized = normalize_key(name)
        if not normalized:
            raise ValueError("Character name cannot be empty.")

        alias = self.connection.execute(
            """
            SELECT
                ca.id AS alias_id,
                ca.canonical_character_id,
                c.name AS canonical_name
            FROM character_alias AS ca
            JOIN characters AS c ON c.id = ca.canonical_character_id
            WHERE ca.normalized_alias = ?
            LIMIT 1
            """,
            (normalized,),
        ).fetchone()
        if alias is not None:
            character_id = int(alias["canonical_character_id"])
            self.connection.execute(
                """
                UPDATE characters
                SET is_active = 1, updated_at = ?
                WHERE id = ?
                """,
                (timestamp, character_id),
            )
            return (
                character_id,
                str(alias["canonical_name"]),
                (int(alias["alias_id"]),),
            )

        row = self.connection.execute(
            """
            SELECT id, name
            FROM characters
            WHERE normalized_name = ?
            """,
            (normalized,),
        ).fetchone()

        if row:
            character_id = int(row["id"])
            self.connection.execute(
                """
                UPDATE characters
                SET is_active = 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (timestamp, character_id),
            )
            return character_id, str(row["name"]), ()

        cursor = self.connection.execute(
            """
            INSERT INTO characters(
                name,
                normalized_name,
                is_active,
                created_at,
                updated_at
            )
            VALUES(?, ?, 1, ?, ?)
            """,
            (name.strip(), normalized, timestamp, timestamp),
        )
        return int(cursor.lastrowid), name.strip(), ()

    def ensure_talent(self, name: str, *, timestamp: str) -> int:
        normalized = normalize_key(name)
        if not normalized:
            raise ValueError("Talent name cannot be empty.")

        row = self.connection.execute(
            """
            SELECT id
            FROM talents
            WHERE normalized_name = ?
            """,
            (normalized,),
        ).fetchone()

        if row:
            talent_id = int(row["id"])
            self.connection.execute(
                """
                UPDATE talents
                SET is_active = 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (timestamp, talent_id),
            )
            return talent_id

        cursor = self.connection.execute(
            """
            INSERT INTO talents(
                name,
                normalized_name,
                is_active,
                created_at,
                updated_at
            )
            VALUES(?, ?, 1, ?, ?)
            """,
            (name.strip(), normalized, timestamp, timestamp),
        )
        return int(cursor.lastrowid)

    def learn_from_single_rows(
        self,
        parse_results: Iterable[ScriptParseResult],
        *,
        timestamp: str,
    ) -> ResolverReport:
        report = ResolverReport()
        evidence: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)

        for parse_result in parse_results:
            for row in parse_result.rows:
                if len(row.characters) != 1 or len(row.talents) != 1:
                    continue
                character_name = row.characters[0]
                talent_name = row.talents[0]
                character_key = normalize_key(character_name)
                talent_key = normalize_key(talent_name)
                if not character_key or not talent_key:
                    continue
                evidence[character_key][talent_key] = (
                    character_name,
                    talent_name,
                )

        for character_key, talent_variants in sorted(evidence.items()):
            sample_character = next(iter(talent_variants.values()))[0]
            character_id = self.ensure_character(sample_character, timestamp=timestamp)
            locked = self._get_locked_mapping(character_id)

            if locked is not None:
                locked_talent_key = str(locked["normalized_name"])
                if locked_talent_key not in talent_variants:
                    source_talents = ", ".join(
                        sorted(value[1] for value in talent_variants.values())
                    )
                    report.warnings.append(
                        f"Tokoh '{sample_character}' sudah terkunci ke talent "
                        f"'{locked['name']}', tetapi source menemukan: {source_talents}."
                    )
                continue

            if len(talent_variants) != 1:
                source_talents = ", ".join(
                    sorted(value[1] for value in talent_variants.values())
                )
                report.warnings.append(
                    f"Tokoh '{sample_character}' memiliki lebih dari satu talent "
                    f"pada baris single: {source_talents}. Mapping tidak dikunci otomatis."
                )
                continue

            character_name, talent_name = next(iter(talent_variants.values()))
            talent_id = self.ensure_talent(talent_name, timestamp=timestamp)
            existing_pair = self.connection.execute(
                """
                SELECT id
                FROM character_talent
                WHERE character_id = ? AND talent_id = ?
                """,
                (character_id, talent_id),
            ).fetchone()

            if existing_pair:
                self.connection.execute(
                    """
                    UPDATE character_talent
                    SET is_locked = 1,
                        source = 'auto-single',
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (timestamp, int(existing_pair["id"])),
                )
            else:
                self.connection.execute(
                    """
                    INSERT INTO character_talent(
                        character_id,
                        talent_id,
                        is_locked,
                        source,
                        created_at,
                        updated_at
                    )
                    VALUES(?, ?, 1, 'auto-single', ?, ?)
                    """,
                    (character_id, talent_id, timestamp, timestamp),
                )
            report.auto_locked += 1

        return report

    def resolve_row(
        self,
        row: ParsedDialogueRow,
        *,
        timestamp: str,
    ) -> tuple[list[ResolvedCastMember], list[str]]:
        warnings: list[str] = []
        candidates: list[ResolvedCastMember] = []

        provided_by_character: dict[str, list[str]] = defaultdict(list)
        for pair in row.cast_pairs:
            character_key = normalize_key(pair.character)
            talent_key = normalize_key(pair.talent)
            if not character_key or not talent_key:
                continue
            existing_keys = {
                normalize_key(name)
                for name in provided_by_character[character_key]
            }
            if talent_key not in existing_keys:
                provided_by_character[character_key].append(pair.talent)

        processed_source_keys: set[str] = set()
        for source_character_name in row.characters:
            character_key = normalize_key(source_character_name)
            if not character_key or character_key in processed_source_keys:
                continue
            processed_source_keys.add(character_key)

            character_id, canonical_name, alias_ids = self._resolve_character_identity(
                source_character_name,
                timestamp=timestamp,
            )
            locked = self._get_locked_mapping(character_id)
            provided_talents = provided_by_character.get(character_key, [])

            if locked is not None:
                talent_id = int(locked["talent_id"])
                talent_name = str(locked["name"])
                locked_talent_key = str(locked["normalized_name"])
                provided_keys = {
                    normalize_key(name) for name in provided_talents
                }
                if provided_keys and locked_talent_key not in provided_keys:
                    warnings.append(
                        f"Tokoh '{source_character_name}' menggunakan talent terkunci "
                        f"'{talent_name}', bukan "
                        f"'{', '.join(provided_talents)}' dari source."
                    )
                candidates.append(
                    ResolvedCastMember(
                        character_id=character_id,
                        character_name=canonical_name,
                        talent_id=talent_id,
                        talent_name=talent_name,
                        source="alias-locked" if alias_ids else "locked",
                        alias_ids=alias_ids,
                    )
                )
                continue

            if provided_talents:
                source_label = (
                    "source-multi" if len(provided_talents) > 1 else "source-pair"
                )
                if alias_ids:
                    source_label = "alias-" + source_label
                for provided_talent in provided_talents:
                    talent_id = self.ensure_talent(provided_talent, timestamp=timestamp)
                    candidates.append(
                        ResolvedCastMember(
                            character_id=character_id,
                            character_name=canonical_name,
                            talent_id=talent_id,
                            talent_name=provided_talent,
                            source=source_label,
                            alias_ids=alias_ids,
                        )
                    )
                continue

            candidates.append(
                ResolvedCastMember(
                    character_id=character_id,
                    character_name=canonical_name,
                    talent_id=None,
                    talent_name="",
                    source="alias-unresolved" if alias_ids else "unresolved",
                    alias_ids=alias_ids,
                )
            )
            warnings.append(
                f"Tokoh '{source_character_name}' belum memiliki talent yang dapat di-resolve."
            )

        return self._deduplicate_candidates(candidates), warnings

    @staticmethod
    def _deduplicate_candidates(
        candidates: list[ResolvedCastMember],
    ) -> list[ResolvedCastMember]:
        grouped: dict[tuple[int, int | None], ResolvedCastMember] = {}
        order: list[tuple[int, int | None]] = []

        for member in candidates:
            key = (member.character_id, member.talent_id)
            existing = grouped.get(key)
            if existing is None:
                grouped[key] = member
                order.append(key)
                continue

            if not existing.alias_ids or not member.alias_ids:
                alias_ids: tuple[int, ...] = ()
                source = member.source if not member.alias_ids else existing.source
            else:
                alias_ids = tuple(sorted(set(existing.alias_ids + member.alias_ids)))
                source = existing.source

            grouped[key] = ResolvedCastMember(
                character_id=existing.character_id,
                character_name=existing.character_name,
                talent_id=existing.talent_id,
                talent_name=existing.talent_name or member.talent_name,
                source=source,
                alias_ids=alias_ids,
            )

        return [grouped[key] for key in order]

    def _get_locked_mapping(self, character_id: int):
        return self.connection.execute(
            """
            SELECT
                ct.talent_id,
                t.name,
                t.normalized_name
            FROM character_talent AS ct
            JOIN talents AS t
              ON t.id = ct.talent_id
            WHERE ct.character_id = ?
              AND ct.is_locked = 1
            ORDER BY ct.id
            LIMIT 1
            """,
            (character_id,),
        ).fetchone()
