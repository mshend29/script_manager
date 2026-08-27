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
    """Resolve source cast labels using source-name + source-talent identity.

    A normalized character label may legitimately refer to different people when
    the source assigns different talents in unambiguous rows. Those identities
    are stored as separate character rows. Multi-talent rows intentionally stay
    on one unbound character identity so crowd/multi-cast workflows are not
    split into artificial characters.

    Manual Character Mapping remains authoritative *within* a source identity:
    identity_talent_id records which talent disambiguated the source character,
    while character_talent stores the current locked recording assignment.
    """

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    # ------------------------------------------------------------------
    # ENTITY PREPARATION
    # ------------------------------------------------------------------

    def ensure_entities(
        self,
        parse_results: Iterable[ScriptParseResult],
        *,
        timestamp: str,
    ) -> None:
        parse_values = list(parse_results)

        # Pass 1: talents first so source identity can reference stable talent IDs.
        for parse_result in parse_values:
            for row in parse_result.rows:
                for talent in row.talents:
                    self.ensure_talent(talent, timestamp=timestamp)

        # Pass 2: only truly unambiguous single-character/single-talent rows
        # create talent-bound source identities.
        single_identity_names: set[str] = set()
        for parse_result in parse_values:
            for row in parse_result.rows:
                if len(row.characters) != 1 or len(row.talents) != 1:
                    continue
                character = row.characters[0]
                talent = row.talents[0]
                character_key = normalize_key(character)
                if not character_key:
                    continue
                single_identity_names.add(character_key)
                self.ensure_character(
                    character,
                    timestamp=timestamp,
                    source_talent_name=talent,
                )

        # Pass 3: rows without unambiguous identity evidence remain unbound.
        # If a character already has single-row evidence, do not create a ghost
        # unbound row merely because it also appears in a multi-character row.
        for parse_result in parse_values:
            for row in parse_result.rows:
                processed: set[str] = set()
                for character in row.characters:
                    key = normalize_key(character)
                    if (
                        not key
                        or key in processed
                        or key in single_identity_names
                    ):
                        continue
                    processed.add(key)
                    self.ensure_character(
                        character,
                        timestamp=timestamp,
                    )

    def ensure_character(
        self,
        name: str,
        *,
        timestamp: str,
        source_talent_name: str | None = None,
    ) -> int:
        character_id, _, _ = self._resolve_character_identity(
            name,
            timestamp=timestamp,
            source_talent_name=source_talent_name,
        )
        return character_id

    def _resolve_character_identity(
        self,
        name: str,
        *,
        timestamp: str,
        source_talent_name: str | None = None,
        prefer_locked_variant: bool = False,
    ) -> tuple[int, str, tuple[int, ...]]:
        base_normalized = normalize_key(name)
        if not base_normalized:
            raise ValueError("Character name cannot be empty.")

        source_talent_id = (
            self.ensure_talent(source_talent_name, timestamp=timestamp)
            if source_talent_name
            else None
        )

        alias = self.connection.execute(
            """
            SELECT
                ca.id AS alias_id,
                ca.canonical_character_id,
                c.name AS canonical_name,
                c.identity_talent_id
            FROM character_alias AS ca
            JOIN characters AS c ON c.id = ca.canonical_character_id
            WHERE ca.normalized_alias = ?
            LIMIT 1
            """,
            (base_normalized,),
        ).fetchone()

        # Alias is authoritative only when it is compatible with the explicit
        # source-talent identity. This prevents a global alias/old lock from
        # collapsing two same-label characters voiced by different talents.
        if alias is not None and self._alias_matches_source_talent(
            alias,
            source_talent_id,
        ):
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

        if source_talent_id is not None:
            row = self.connection.execute(
                """
                SELECT id, name
                FROM characters
                WHERE COALESCE(
                    NULLIF(base_normalized_name, ''),
                    normalized_name
                ) = ?
                  AND identity_talent_id = ?
                ORDER BY id
                LIMIT 1
                """,
                (base_normalized, source_talent_id),
            ).fetchone()
        else:
            row = None

            if prefer_locked_variant:
                locked_variants = self.connection.execute(
                    """
                    SELECT c.id, c.name
                    FROM characters AS c
                    JOIN character_talent AS ct
                      ON ct.character_id = c.id
                     AND ct.is_locked = 1
                    WHERE COALESCE(
                        NULLIF(c.base_normalized_name, ''),
                        c.normalized_name
                    ) = ?
                      AND c.is_active = 1
                    ORDER BY
                        CASE WHEN ct.source = 'manual' THEN 0 ELSE 1 END,
                        c.id
                    """,
                    (base_normalized,),
                ).fetchall()
                if len(locked_variants) == 1:
                    row = locked_variants[0]

            if row is None:
                row = self.connection.execute(
                    """
                    SELECT id, name
                    FROM characters
                    WHERE COALESCE(
                        NULLIF(base_normalized_name, ''),
                        normalized_name
                    ) = ?
                      AND identity_talent_id IS NULL
                    ORDER BY id
                    LIMIT 1
                    """,
                    (base_normalized,),
                ).fetchone()

            if row is None:
                variants = self.connection.execute(
                    """
                    SELECT id, name
                    FROM characters
                    WHERE COALESCE(
                        NULLIF(base_normalized_name, ''),
                        normalized_name
                    ) = ?
                      AND is_active = 1
                    ORDER BY id
                    """,
                    (base_normalized,),
                ).fetchall()
                # With only one known identity it is safe to reuse it when the
                # source omits talent. With multiple identities we must not guess.
                if len(variants) == 1:
                    row = variants[0]

        if row is not None:
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

        storage_key = self._new_storage_normalized_name(
            base_normalized,
            source_talent_id,
        )
        cursor = self.connection.execute(
            """
            INSERT INTO characters(
                name,
                normalized_name,
                base_normalized_name,
                identity_talent_id,
                is_active,
                created_at,
                updated_at
            )
            VALUES(?, ?, ?, ?, 1, ?, ?)
            """,
            (
                name.strip(),
                storage_key,
                base_normalized,
                source_talent_id,
                timestamp,
                timestamp,
            ),
        )
        return int(cursor.lastrowid), name.strip(), ()

    def _new_storage_normalized_name(
        self,
        base_normalized: str,
        source_talent_id: int | None,
    ) -> str:
        preferred = base_normalized
        exists = self.connection.execute(
            "SELECT 1 FROM characters WHERE normalized_name = ?",
            (preferred,),
        ).fetchone()
        if exists is None:
            return preferred

        suffix = (
            f"talent:{int(source_talent_id)}"
            if source_talent_id is not None
            else "unbound"
        )
        candidate = f"{base_normalized}||{suffix}"
        serial = 2
        while self.connection.execute(
            "SELECT 1 FROM characters WHERE normalized_name = ?",
            (candidate,),
        ).fetchone():
            candidate = f"{base_normalized}||{suffix}:{serial}"
            serial += 1
        return candidate

    @staticmethod
    def _alias_matches_source_talent(
        alias,
        source_talent_id: int | None,
    ) -> bool:
        if source_talent_id is None:
            return True
        canonical_identity_talent = alias["identity_talent_id"]
        if canonical_identity_talent is None:
            return True
        return int(canonical_identity_talent) == int(source_talent_id)

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

    # ------------------------------------------------------------------
    # AUTO LOCK LEARNING
    # ------------------------------------------------------------------

    def learn_from_single_rows(
        self,
        parse_results: Iterable[ScriptParseResult],
        *,
        timestamp: str,
    ) -> ResolverReport:
        report = ResolverReport()
        evidence: dict[
            tuple[str, str],
            tuple[str, str],
        ] = {}

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
                evidence[(character_key, talent_key)] = (
                    character_name,
                    talent_name,
                )

        for (_character_key, _talent_key), (
            character_name,
            talent_name,
        ) in sorted(evidence.items()):
            talent_id = self.ensure_talent(
                talent_name,
                timestamp=timestamp,
            )
            character_id = self.ensure_character(
                character_name,
                timestamp=timestamp,
                source_talent_name=talent_name,
            )
            locked = self._get_locked_mapping(character_id)

            # A manual correction belongs to this source identity and must
            # survive Refresh even if it intentionally differs from source.
            if locked is not None and str(locked["source"] or "") == "manual":
                continue

            if (
                locked is not None
                and int(locked["talent_id"]) == talent_id
            ):
                continue

            self.connection.execute(
                """
                UPDATE character_talent
                SET is_locked = 0,
                    updated_at = ?
                WHERE character_id = ?
                  AND is_locked = 1
                """,
                (timestamp, character_id),
            )

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

    # ------------------------------------------------------------------
    # ROW RESOLUTION
    # ------------------------------------------------------------------

    def resolve_row(
        self,
        row: ParsedDialogueRow,
        *,
        timestamp: str,
        apply_manual_overrides: bool = True,
    ) -> tuple[list[ResolvedCastMember], list[str]]:
        warnings: list[str] = []
        candidates: list[ResolvedCastMember] = []

        provided_by_character = self._provided_talents_by_character(row)

        processed_source_keys: set[str] = set()
        for source_character_name in row.characters:
            character_key = normalize_key(source_character_name)
            if not character_key or character_key in processed_source_keys:
                continue
            processed_source_keys.add(character_key)

            provided_talents = provided_by_character.get(character_key, [])

            # Only a single-character/single-talent row is strong enough
            # evidence to create a separate source identity. Multi-character
            # rows may have talent order reversed, so their known single-row
            # locks must remain authoritative.
            unambiguous_identity_pair = (
                len(row.characters) == 1
                and len(row.talents) == 1
                and len(provided_talents) == 1
            )

            if unambiguous_identity_pair:
                provided_talent = provided_talents[0]
                character_id, canonical_name, alias_ids = (
                    self._resolve_character_identity(
                        source_character_name,
                        timestamp=timestamp,
                        source_talent_name=provided_talent,
                    )
                )
                locked = (
                    self._get_locked_mapping(character_id)
                    if apply_manual_overrides
                    else None
                )

                if locked is not None:
                    talent_id = int(locked["talent_id"])
                    talent_name = str(locked["name"])
                    if (
                        str(locked["source"] or "") == "manual"
                        and normalize_key(talent_name)
                        != normalize_key(provided_talent)
                    ):
                        warnings.append(
                            f"Tokoh '{source_character_name}' source talent "
                            f"'{provided_talent}' dioverride manual menjadi "
                            f"'{talent_name}'."
                        )
                    source_label = (
                        "alias-locked" if alias_ids else "locked"
                    )
                else:
                    talent_id = self.ensure_talent(
                        provided_talent,
                        timestamp=timestamp,
                    )
                    talent_name = provided_talent
                    source_label = (
                        "alias-source-pair"
                        if alias_ids
                        else "source-pair"
                    )

                candidates.append(
                    ResolvedCastMember(
                        character_id=character_id,
                        character_name=canonical_name,
                        talent_id=talent_id,
                        talent_name=talent_name,
                        source=source_label,
                        alias_ids=alias_ids,
                    )
                )
                continue

            # Multi-talent source row intentionally stays one character identity.
            character_id, canonical_name, alias_ids = (
                self._resolve_character_identity(
                    source_character_name,
                    timestamp=timestamp,
                    prefer_locked_variant=True,
                )
            )
            locked = (
                self._get_locked_mapping(character_id)
                if apply_manual_overrides
                else self._get_source_mapping(character_id)
            )

            if locked is not None:
                candidates.append(
                    ResolvedCastMember(
                        character_id=character_id,
                        character_name=canonical_name,
                        talent_id=int(locked["talent_id"]),
                        talent_name=str(locked["name"]),
                        source=(
                            "alias-locked" if alias_ids else "locked"
                        ),
                        alias_ids=alias_ids,
                    )
                )
                continue

            if provided_talents:
                source_label = (
                    "alias-source-multi"
                    if alias_ids
                    else "source-multi"
                )
                for provided_talent in provided_talents:
                    talent_id = self.ensure_talent(
                        provided_talent,
                        timestamp=timestamp,
                    )
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
                    source=(
                        "alias-unresolved"
                        if alias_ids
                        else "unresolved"
                    ),
                    alias_ids=alias_ids,
                )
            )
            warnings.append(
                f"Tokoh '{source_character_name}' belum memiliki talent yang dapat di-resolve."
            )

        return self._deduplicate_candidates(candidates), warnings

    @staticmethod
    def _provided_talents_by_character(
        row: ParsedDialogueRow,
    ) -> dict[str, list[str]]:
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
        return provided_by_character

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
                source = (
                    member.source
                    if not member.alias_ids
                    else existing.source
                )
            else:
                alias_ids = tuple(
                    sorted(set(existing.alias_ids + member.alias_ids))
                )
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

    def _get_source_mapping(self, character_id: int):
        """Return non-manual source evidence for ambiguous/multi-cast rows.

        Manual Character Mapping is an effective override only. Auto-single or
        alias-derived source evidence may still be used to correct ambiguous
        multi-character ordering when rebuilding source provenance.
        """
        return self.connection.execute(
            """
            SELECT
                ct.talent_id,
                ct.source,
                t.name,
                t.normalized_name
            FROM character_talent AS ct
            JOIN talents AS t
              ON t.id = ct.talent_id
            WHERE ct.character_id = ?
              AND COALESCE(ct.source, '') NOT IN (
                  'manual',
                  'manual-unlocked'
              )
            ORDER BY
                CASE
                    WHEN ct.source = 'auto-single' THEN 0
                    WHEN ct.source LIKE 'alias:%' THEN 1
                    WHEN ct.source = 'alias-restored' THEN 2
                    ELSE 3
                END,
                ct.is_locked DESC,
                ct.id
            LIMIT 1
            """,
            (character_id,),
        ).fetchone()

    def _get_locked_mapping(self, character_id: int):
        return self.connection.execute(
            """
            SELECT
                ct.talent_id,
                ct.source,
                t.name,
                t.normalized_name
            FROM character_talent AS ct
            JOIN talents AS t
              ON t.id = ct.talent_id
            WHERE ct.character_id = ?
              AND ct.is_locked = 1
            ORDER BY
                CASE WHEN ct.source = 'manual' THEN 0 ELSE 1 END,
                ct.id
            LIMIT 1
            """,
            (character_id,),
        ).fetchone()
