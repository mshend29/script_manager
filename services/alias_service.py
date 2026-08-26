from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.database import Database


@dataclass(frozen=True)
class CharacterAliasRow:
    id: int
    source_character_id: int
    source_name: str
    canonical_character_id: int
    canonical_name: str


class CharacterAliasService:
    """Manual, reversible identity mapping for source character labels.

    Source character rows and dialog_cast links are deliberately preserved.
    Operational services canonicalize through character_alias, while SCRIPT can
    continue to show exactly the character label that came from the client.
    """

    def __init__(self, database: Database):
        self.database = database

    def get_aliases_for_character(self, canonical_character_id: int) -> list[CharacterAliasRow]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    ca.id,
                    ca.source_character_id,
                    source.name AS source_name,
                    ca.canonical_character_id,
                    canonical.name AS canonical_name
                FROM character_alias AS ca
                JOIN characters AS source ON source.id = ca.source_character_id
                JOIN characters AS canonical ON canonical.id = ca.canonical_character_id
                WHERE ca.canonical_character_id = ?
                ORDER BY source.normalized_name, source.name
                """,
                (int(canonical_character_id),),
            ).fetchall()
        return [
            CharacterAliasRow(
                id=int(row["id"]),
                source_character_id=int(row["source_character_id"]),
                source_name=str(row["source_name"]),
                canonical_character_id=int(row["canonical_character_id"]),
                canonical_name=str(row["canonical_name"]),
            )
            for row in rows
        ]

    def get_canonical_options(self, *, exclude_character_id: int | None = None) -> list[tuple[int, str]]:
        params: list[object] = []
        where = [
            "c.is_active = 1",
            "NOT EXISTS (SELECT 1 FROM character_alias a WHERE a.source_character_id = c.id)",
        ]
        if exclude_character_id is not None:
            where.append("c.id != ?")
            params.append(int(exclude_character_id))

        with self.database.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT c.id, c.name
                FROM characters AS c
                WHERE {' AND '.join(where)}
                ORDER BY c.normalized_name, c.name
                """,
                params,
            ).fetchall()
        return [(int(row["id"]), str(row["name"])) for row in rows]

    def set_alias(self, *, source_character_id: int, canonical_character_id: int) -> int:
        source_character_id = int(source_character_id)
        canonical_character_id = int(canonical_character_id)
        if source_character_id == canonical_character_id:
            raise ValueError("Character tidak dapat menjadi alias dari dirinya sendiri.")

        now = datetime.now().isoformat(timespec="seconds")
        with self.database.connect() as connection:
            source = connection.execute(
                "SELECT id, name, normalized_name, is_active FROM characters WHERE id = ?",
                (source_character_id,),
            ).fetchone()
            canonical = connection.execute(
                "SELECT id, name, is_active FROM characters WHERE id = ?",
                (canonical_character_id,),
            ).fetchone()
            if source is None or int(source["is_active"] or 0) != 1:
                raise ValueError("Character sumber tidak ditemukan atau inactive.")
            if canonical is None or int(canonical["is_active"] or 0) != 1:
                raise ValueError("Canonical character tidak ditemukan atau inactive.")

            if connection.execute(
                "SELECT 1 FROM character_alias WHERE source_character_id = ?",
                (source_character_id,),
            ).fetchone():
                raise ValueError("Character ini sudah merupakan alias.")

            # Keep the graph flat: alias may only point directly to a canonical
            # character, never to another alias.
            if connection.execute(
                "SELECT 1 FROM character_alias WHERE source_character_id = ?",
                (canonical_character_id,),
            ).fetchone():
                raise ValueError("Target merupakan alias. Pilih canonical character langsung.")

            # A canonical character that already owns aliases cannot itself be
            # demoted until its aliases are restored first. This keeps restore
            # semantics deterministic and prevents alias chains.
            if connection.execute(
                "SELECT 1 FROM character_alias WHERE canonical_character_id = ? LIMIT 1",
                (source_character_id,),
            ).fetchone():
                raise ValueError(
                    "Character sumber masih memiliki alias. Restore alias tersebut terlebih dahulu."
                )

            cursor = connection.execute(
                """
                INSERT INTO character_alias(
                    source_character_id,
                    canonical_character_id,
                    alias_name,
                    normalized_alias,
                    created_at,
                    updated_at
                ) VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    source_character_id,
                    canonical_character_id,
                    str(source["name"]),
                    str(source["normalized_name"]),
                    now,
                    now,
                ),
            )
            self._reset_tracking_for_identity_change(
                connection,
                source_character_id=source_character_id,
                canonical_character_id=canonical_character_id,
            )
            return int(cursor.lastrowid)

    def restore_alias(self, alias_id: int) -> None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT source_character_id, canonical_character_id
                FROM character_alias
                WHERE id = ?
                """,
                (int(alias_id),),
            ).fetchone()
            if row is None:
                raise ValueError("Alias tidak ditemukan.")

            source_character_id = int(row["source_character_id"])
            canonical_character_id = int(row["canonical_character_id"])
            self._reset_tracking_for_identity_change(
                connection,
                source_character_id=source_character_id,
                canonical_character_id=canonical_character_id,
            )
            connection.execute("DELETE FROM character_alias WHERE id = ?", (int(alias_id),))

    @staticmethod
    def _reset_tracking_for_identity_change(
        connection,
        *,
        source_character_id: int,
        canonical_character_id: int,
    ) -> None:
        episode_rows = connection.execute(
            """
            SELECT DISTINCT d.episode_id
            FROM dialog_cast AS dc
            JOIN dialogues AS d ON d.id = dc.dialogue_id
            WHERE d.is_active = 1
              AND dc.character_id IN (?, ?)
            """,
            (int(source_character_id), int(canonical_character_id)),
        ).fetchall()
        episode_ids = [int(row["episode_id"]) for row in episode_rows]
        if not episode_ids:
            return
        placeholders = ",".join("?" for _ in episode_ids)
        connection.execute(
            f"""
            DELETE FROM stem_status
            WHERE episode_id IN ({placeholders})
              AND character_id IN (?, ?)
            """,
            (*episode_ids, int(source_character_id), int(canonical_character_id)),
        )
