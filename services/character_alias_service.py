from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.database import Database
from import_engine.normalizer import normalize_key
from services.audit_service import AuditService
from services.backup_service import BackupService
from services.validation_service import ERROR, SYSTEM, ValidationIssue


@dataclass(frozen=True)
class CharacterAliasRow:
    id: int
    alias_name: str
    normalized_alias: str
    canonical_character_id: int
    canonical_character_name: str
    source_character_id: int | None


class CharacterAliasService:
    """Manual, reversible aliases from source character labels to a canonical character."""

    def __init__(self, database: Database):
        self.database = database

    def get_aliases(self, canonical_character_id: int | None = None) -> list[CharacterAliasRow]:
        where = ""
        params: tuple[object, ...] = ()
        if canonical_character_id is not None:
            where = "WHERE ca.canonical_character_id = ?"
            params = (int(canonical_character_id),)

        with self.database.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    ca.id,
                    ca.alias_name,
                    ca.normalized_alias,
                    ca.canonical_character_id,
                    c.name AS canonical_character_name,
                    ca.source_character_id
                FROM character_alias AS ca
                JOIN characters AS c ON c.id = ca.canonical_character_id
                {where}
                ORDER BY ca.alias_name COLLATE NOCASE, ca.id
                """,
                params,
            ).fetchall()

        return [
            CharacterAliasRow(
                id=int(row["id"]),
                alias_name=str(row["alias_name"]),
                normalized_alias=str(row["normalized_alias"]),
                canonical_character_id=int(row["canonical_character_id"]),
                canonical_character_name=str(row["canonical_character_name"]),
                source_character_id=(
                    int(row["source_character_id"])
                    if row["source_character_id"] is not None
                    else None
                ),
            )
            for row in rows
        ]

    def aliases_by_canonical(self) -> dict[int, list[CharacterAliasRow]]:
        result: dict[int, list[CharacterAliasRow]] = {}
        for alias in self.get_aliases():
            result.setdefault(alias.canonical_character_id, []).append(alias)
        return result

    def get_canonical_characters(self) -> list[tuple[int, str]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT c.id, c.name
                FROM characters AS c
                WHERE c.is_active = 1
                  AND NOT EXISTS (
                      SELECT 1
                      FROM character_alias AS ca
                      WHERE ca.source_character_id = c.id
                  )
                ORDER BY c.name COLLATE NOCASE, c.id
                """
            ).fetchall()
        return [(int(row["id"]), str(row["name"])) for row in rows]

    def add_alias_name(self, canonical_character_id: int, alias_name: str) -> int:
        clean = alias_name.strip()
        normalized = normalize_key(clean)
        if not normalized:
            raise ValueError("Nama alias tidak boleh kosong.")

        now = datetime.now().isoformat(timespec="seconds")
        with self.database.connect() as connection:
            canonical = self._require_canonical(connection, canonical_character_id)
            existing_alias = connection.execute(
                "SELECT id FROM character_alias WHERE normalized_alias = ?",
                (normalized,),
            ).fetchone()
            if existing_alias is not None:
                raise ValueError("Nama tersebut sudah terdaftar sebagai alias.")

            existing_character = connection.execute(
                """
                SELECT id, name
                FROM characters
                WHERE COALESCE(
                    NULLIF(base_normalized_name, ''),
                    normalized_name
                ) = ?
                  AND is_active = 1
                ORDER BY id
                LIMIT 1
                """,
                (normalized,),
            ).fetchone()
            if existing_character is not None:
                existing_id = int(existing_character["id"])
                if existing_id == int(canonical_character_id):
                    raise ValueError("Alias tidak boleh sama dengan nama canonical character.")
                raise ValueError(
                    f"'{existing_character['name']}' sudah ada sebagai character. "
                    "Pilih row character tersebut lalu gunakan Set as Alias of."
                )

            cursor = connection.execute(
                """
                INSERT INTO character_alias(
                    alias_name,
                    normalized_alias,
                    canonical_character_id,
                    source_character_id,
                    source_locked_talent_id,
                    created_at,
                    updated_at
                ) VALUES(?, ?, ?, NULL, NULL, ?, ?)
                """,
                (clean, normalized, int(canonical["id"]), now, now),
            )
            alias_id = int(cursor.lastrowid)
            canonical_name = str(canonical["name"])

        AuditService(self.database).record(
            event_type="ALIAS",
            action="ADD_ALIAS_NAME",
            entity_type="character",
            entity_id=canonical_character_id,
            summary=f"Alias '{clean}' added to {canonical_name}.",
            details={"alias_id": alias_id},
            created_at=now,
        )
        return alias_id

    def set_character_alias(self, source_character_id: int, canonical_character_id: int) -> int:
        source_id = int(source_character_id)
        canonical_id = int(canonical_character_id)
        if source_id == canonical_id:
            raise ValueError("Character tidak dapat menjadi alias dirinya sendiri.")

        now = datetime.now().isoformat(timespec="seconds")
        backup = BackupService(self.database).create("before-alias-merge")
        with self.database.connect() as connection:
            source = self._require_active_character(connection, source_id)
            canonical = self._require_canonical(connection, canonical_id)

            if connection.execute(
                "SELECT 1 FROM character_alias WHERE source_character_id = ?",
                (source_id,),
            ).fetchone():
                raise ValueError("Character ini sudah menjadi alias.")

            if connection.execute(
                "SELECT 1 FROM character_alias WHERE canonical_character_id = ?",
                (source_id,),
            ).fetchone():
                raise ValueError(
                    "Character ini sudah memiliki alias. Hapus/pindahkan alias tersebut sebelum menjadikannya alias character lain."
                )

            normalized = str(
                source["base_normalized_name"]
                or source["normalized_name"]
            )
            if connection.execute(
                "SELECT 1 FROM character_alias WHERE normalized_alias = ?",
                (normalized,),
            ).fetchone():
                raise ValueError("Nama character ini sudah terdaftar sebagai alias.")

            source_lock = self._locked_talent(connection, source_id)
            canonical_lock = self._locked_talent(connection, canonical_id)
            if (
                source_lock is not None
                and canonical_lock is not None
                and int(source_lock["talent_id"]) != int(canonical_lock["talent_id"])
            ):
                raise ValueError(
                    "Alias tidak dapat dibuat karena source character dan canonical character "
                    "memiliki locked talent yang berbeda. Selesaikan Cast Mapping terlebih dahulu."
                )

            cursor = connection.execute(
                """
                INSERT INTO character_alias(
                    alias_name,
                    normalized_alias,
                    canonical_character_id,
                    source_character_id,
                    source_locked_talent_id,
                    created_at,
                    updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(source["name"]),
                    normalized,
                    canonical_id,
                    source_id,
                    int(source_lock["talent_id"]) if source_lock is not None else None,
                    now,
                    now,
                ),
            )
            alias_id = int(cursor.lastrowid)

            cast_rows = connection.execute(
                """
                SELECT dc.id, dc.dialogue_id, dc.talent_id, dc.position, d.episode_id
                FROM dialog_cast AS dc
                JOIN dialogues AS d ON d.id = dc.dialogue_id
                WHERE dc.character_id = ?
                ORDER BY dc.dialogue_id, dc.position, dc.id
                """,
                (source_id,),
            ).fetchall()

            affected_episodes: set[int] = set()
            for cast in cast_rows:
                dialogue_id = int(cast["dialogue_id"])
                talent_id = (
                    int(cast["talent_id"]) if cast["talent_id"] is not None else None
                )
                position = int(cast["position"] or 0)
                affected_episodes.add(int(cast["episode_id"]))

                existing = self._find_cast(
                    connection,
                    dialogue_id=dialogue_id,
                    character_id=canonical_id,
                    talent_id=talent_id,
                )
                created_canonical = existing is None
                if created_canonical:
                    connection.execute(
                        """
                        INSERT INTO dialog_cast(dialogue_id, character_id, talent_id, position)
                        VALUES(?, ?, ?, ?)
                        """,
                        (dialogue_id, canonical_id, talent_id, position),
                    )

                connection.execute(
                    """
                    INSERT INTO character_alias_dialogue(
                        alias_id,
                        dialogue_id,
                        talent_id,
                        position,
                        created_canonical
                    ) VALUES(?, ?, ?, ?, ?)
                    """,
                    (
                        alias_id,
                        dialogue_id,
                        talent_id,
                        position,
                        1 if created_canonical else 0,
                    ),
                )
                connection.execute("DELETE FROM dialog_cast WHERE id = ?", (int(cast["id"]),))

            if source_lock is not None:
                source_talent = int(source_lock["talent_id"])
                if canonical_lock is None:
                    existing_pair = connection.execute(
                        """
                        SELECT id FROM character_talent
                        WHERE character_id = ? AND talent_id = ?
                        """,
                        (canonical_id, source_talent),
                    ).fetchone()
                    if existing_pair:
                        connection.execute(
                            """
                            UPDATE character_talent
                            SET is_locked = 1, source = ?, updated_at = ?
                            WHERE id = ?
                            """,
                            (f"alias:{alias_id}", now, int(existing_pair["id"])),
                        )
                    else:
                        connection.execute(
                            """
                            INSERT INTO character_talent(
                                character_id, talent_id, is_locked, source, created_at, updated_at
                            ) VALUES(?, ?, 1, ?, ?, ?)
                            """,
                            (canonical_id, source_talent, f"alias:{alias_id}", now, now),
                        )

                connection.execute(
                    """
                    UPDATE character_talent
                    SET is_locked = 0, source = 'alias-source', updated_at = ?
                    WHERE character_id = ? AND is_locked = 1
                    """,
                    (now, source_id),
                )

            connection.execute(
                "UPDATE characters SET is_active = 0, updated_at = ? WHERE id = ?",
                (now, source_id),
            )
            self._reset_tracking_scopes(
                connection,
                affected_episodes,
                source_id=source_id,
                canonical_id=canonical_id,
            )
            source_name = str(source["name"])
            canonical_name = str(canonical["name"])

        AuditService(self.database).record(
            event_type="ALIAS",
            action="SET_CHARACTER_ALIAS",
            entity_type="character",
            entity_id=source_id,
            summary=f"{source_name} set as alias of {canonical_name}.",
            details={
                "alias_id": alias_id,
                "canonical_character_id": canonical_id,
                "affected_episodes": sorted(affected_episodes),
                "backup_path": str(backup),
            },
            created_at=now,
        )
        return alias_id

    def remove_alias(self, alias_id: int) -> None:
        alias_id = int(alias_id)
        now = datetime.now().isoformat(timespec="seconds")
        backup = BackupService(self.database).create("before-alias-restore")
        with self.database.connect() as connection:
            alias = connection.execute(
                "SELECT * FROM character_alias WHERE id = ?",
                (alias_id,),
            ).fetchone()
            if alias is None:
                raise ValueError("Alias tidak ditemukan.")

            source_id = (
                int(alias["source_character_id"])
                if alias["source_character_id"] is not None
                else None
            )
            canonical_id = int(alias["canonical_character_id"])

            provenance = connection.execute(
                """
                SELECT cad.*, d.episode_id
                FROM character_alias_dialogue AS cad
                JOIN dialogues AS d ON d.id = cad.dialogue_id
                WHERE cad.alias_id = ?
                ORDER BY cad.dialogue_id, cad.position, cad.id
                """,
                (alias_id,),
            ).fetchall()

            if source_id is None:
                existing_source = connection.execute(
                    """
                    SELECT id
                    FROM characters
                    WHERE COALESCE(
                        NULLIF(base_normalized_name, ''),
                        normalized_name
                    ) = ?
                    ORDER BY
                        CASE
                            WHEN identity_talent_id = ? THEN 0
                            WHEN identity_talent_id IS NULL THEN 1
                            ELSE 2
                        END,
                        id
                    LIMIT 1
                    """,
                    (
                        str(alias["normalized_alias"]),
                        alias["source_locked_talent_id"],
                    ),
                ).fetchone()
                if existing_source is not None:
                    source_id = int(existing_source["id"])
                elif provenance:
                    base_normalized = str(alias["normalized_alias"])
                    storage_key = base_normalized
                    if connection.execute(
                        "SELECT 1 FROM characters WHERE normalized_name = ?",
                        (storage_key,),
                    ).fetchone():
                        suffix = (
                            f"talent:{int(alias['source_locked_talent_id'])}"
                            if alias["source_locked_talent_id"] is not None
                            else "unbound"
                        )
                        storage_key = f"{base_normalized}||{suffix}"
                        serial = 2
                        while connection.execute(
                            "SELECT 1 FROM characters WHERE normalized_name = ?",
                            (storage_key,),
                        ).fetchone():
                            storage_key = (
                                f"{base_normalized}||{suffix}:{serial}"
                            )
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
                        ) VALUES(?, ?, ?, ?, 1, ?, ?)
                        """,
                        (
                            str(alias["alias_name"]),
                            storage_key,
                            base_normalized,
                            (
                                int(alias["source_locked_talent_id"])
                                if alias["source_locked_talent_id"] is not None
                                else None
                            ),
                            now,
                            now,
                        ),
                    )
                    source_id = int(cursor.lastrowid)
                else:
                    connection.execute(
                        "DELETE FROM character_alias WHERE id = ?", (alias_id,)
                    )
                    return

            affected_episodes: set[int] = set()
            for item in provenance:
                dialogue_id = int(item["dialogue_id"])
                talent_id = (
                    int(item["talent_id"]) if item["talent_id"] is not None else None
                )
                position = int(item["position"] or 0)
                affected_episodes.add(int(item["episode_id"]))

                if self._find_cast(
                    connection,
                    dialogue_id=dialogue_id,
                    character_id=source_id,
                    talent_id=talent_id,
                ) is None:
                    connection.execute(
                        """
                        INSERT INTO dialog_cast(dialogue_id, character_id, talent_id, position)
                        VALUES(?, ?, ?, ?)
                        """,
                        (dialogue_id, source_id, talent_id, position),
                    )

                if int(item["created_canonical"] or 0) == 1:
                    other = connection.execute(
                        """
                        SELECT 1
                        FROM character_alias_dialogue AS other_cad
                        JOIN character_alias AS other_alias
                          ON other_alias.id = other_cad.alias_id
                        WHERE other_cad.alias_id != ?
                          AND other_alias.canonical_character_id = ?
                          AND other_cad.dialogue_id = ?
                          AND other_cad.position = ?
                          AND (
                              other_cad.talent_id = ?
                              OR (other_cad.talent_id IS NULL AND ? IS NULL)
                          )
                        LIMIT 1
                        """,
                        (
                            alias_id,
                            canonical_id,
                            dialogue_id,
                            position,
                            talent_id,
                            talent_id,
                        ),
                    ).fetchone()
                    if other is None:
                        self._delete_cast(
                            connection,
                            dialogue_id=dialogue_id,
                            character_id=canonical_id,
                            talent_id=talent_id,
                        )

            connection.execute(
                "UPDATE characters SET is_active = 1, updated_at = ? WHERE id = ?",
                (now, source_id),
            )

            source_locked_talent = alias["source_locked_talent_id"]
            if source_locked_talent is not None:
                talent_id = int(source_locked_talent)
                connection.execute(
                    "UPDATE character_talent SET is_locked = 0, updated_at = ? WHERE character_id = ?",
                    (now, source_id),
                )
                pair = connection.execute(
                    "SELECT id FROM character_talent WHERE character_id = ? AND talent_id = ?",
                    (source_id, talent_id),
                ).fetchone()
                if pair:
                    connection.execute(
                        """
                        UPDATE character_talent
                        SET is_locked = 1, source = 'alias-restored', updated_at = ?
                        WHERE id = ?
                        """,
                        (now, int(pair["id"])),
                    )
                else:
                    connection.execute(
                        """
                        INSERT INTO character_talent(
                            character_id, talent_id, is_locked, source, created_at, updated_at
                        ) VALUES(?, ?, 1, 'alias-restored', ?, ?)
                        """,
                        (source_id, talent_id, now, now),
                    )

                copied = connection.execute(
                    """
                    SELECT id FROM character_talent
                    WHERE character_id = ? AND talent_id = ? AND source = ?
                    """,
                    (canonical_id, talent_id, f"alias:{alias_id}"),
                ).fetchone()
                if copied:
                    connection.execute(
                        """
                        UPDATE character_talent
                        SET is_locked = 0, source = 'alias-removed', updated_at = ?
                        WHERE id = ?
                        """,
                        (now, int(copied["id"])),
                    )

            alias_name = str(alias["alias_name"])
            connection.execute("DELETE FROM character_alias WHERE id = ?", (alias_id,))
            self._reset_tracking_scopes(
                connection,
                affected_episodes,
                source_id=source_id,
                canonical_id=canonical_id,
            )

        AuditService(self.database).record(
            event_type="ALIAS",
            action="REMOVE_ALIAS",
            entity_type="character",
            entity_id=source_id,
            summary=f"Alias '{alias_name}' restored as character.",
            details={
                "alias_id": alias_id,
                "canonical_character_id": canonical_id,
                "affected_episodes": sorted(affected_episodes),
                "backup_path": str(backup),
            },
            created_at=now,
        )

    def validation_issues(self) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        with self.database.connect() as connection:
            inactive_targets = connection.execute(
                """
                SELECT ca.id, ca.alias_name, ca.canonical_character_id
                FROM character_alias AS ca
                JOIN characters AS c ON c.id = ca.canonical_character_id
                WHERE c.is_active = 0
                ORDER BY ca.alias_name COLLATE NOCASE
                """
            ).fetchall()
            for row in inactive_targets:
                issues.append(
                    ValidationIssue(
                        severity=ERROR,
                        category=SYSTEM,
                        code="ALIAS_CANONICAL_INACTIVE",
                        message=(
                            f"Alias '{row['alias_name']}' menunjuk canonical character inactive."
                        ),
                        entity=str(row["alias_name"]),
                    )
                )

            chains = connection.execute(
                """
                SELECT child.alias_name, parent.alias_name AS parent_alias
                FROM character_alias AS child
                JOIN character_alias AS parent
                  ON parent.source_character_id = child.canonical_character_id
                """
            ).fetchall()
            for row in chains:
                issues.append(
                    ValidationIssue(
                        severity=ERROR,
                        category=SYSTEM,
                        code="CHARACTER_ALIAS_CHAIN",
                        message=(
                            f"Alias '{row['alias_name']}' menunjuk character yang juga merupakan alias "
                            f"('{row['parent_alias']}')."
                        ),
                        entity=str(row["alias_name"]),
                    )
                )
        return issues

    @staticmethod
    def _require_active_character(connection, character_id: int):
        row = connection.execute(
            """
            SELECT
                id,
                name,
                normalized_name,
                base_normalized_name,
                identity_talent_id
            FROM characters
            WHERE id = ? AND is_active = 1
            """,
            (int(character_id),),
        ).fetchone()
        if row is None:
            raise ValueError("Character tidak ditemukan atau sudah inactive.")
        return row

    def _require_canonical(self, connection, character_id: int):
        row = self._require_active_character(connection, character_id)
        if connection.execute(
            "SELECT 1 FROM character_alias WHERE source_character_id = ?",
            (int(character_id),),
        ).fetchone():
            raise ValueError("Target canonical tidak boleh merupakan alias character lain.")
        return row

    @staticmethod
    def _locked_talent(connection, character_id: int):
        return connection.execute(
            """
            SELECT talent_id
            FROM character_talent
            WHERE character_id = ? AND is_locked = 1
            ORDER BY id LIMIT 1
            """,
            (int(character_id),),
        ).fetchone()

    @staticmethod
    def _find_cast(connection, *, dialogue_id: int, character_id: int, talent_id: int | None):
        return connection.execute(
            """
            SELECT id FROM dialog_cast
            WHERE dialogue_id = ? AND character_id = ?
              AND (talent_id = ? OR (talent_id IS NULL AND ? IS NULL))
            LIMIT 1
            """,
            (int(dialogue_id), int(character_id), talent_id, talent_id),
        ).fetchone()

    @staticmethod
    def _delete_cast(connection, *, dialogue_id: int, character_id: int, talent_id: int | None) -> None:
        connection.execute(
            """
            DELETE FROM dialog_cast
            WHERE dialogue_id = ? AND character_id = ?
              AND (talent_id = ? OR (talent_id IS NULL AND ? IS NULL))
            """,
            (int(dialogue_id), int(character_id), talent_id, talent_id),
        )

    @staticmethod
    def _reset_tracking_scopes(
        connection,
        episode_ids: set[int],
        *,
        source_id: int,
        canonical_id: int,
    ) -> None:
        if not episode_ids:
            return
        placeholders = ",".join("?" for _ in episode_ids)
        connection.execute(
            f"""
            DELETE FROM stem_status
            WHERE episode_id IN ({placeholders})
              AND character_id IN (?, ?)
            """,
            (*sorted(episode_ids), int(source_id), int(canonical_id)),
        )


class AliasAwareValidationService:
    """ValidationService plus alias integrity checks."""

    def __init__(self, database: Database, base_validation_service_cls):
        self.database = database
        self._base = base_validation_service_cls(database)
        self._alias = CharacterAliasService(database)

    def validate(self):
        return [*self._base.validate(), *self._alias.validation_issues()]

    def summarize(self, issues):
        return self._base.summarize(issues)
