from __future__ import annotations

from dataclasses import dataclass

from core.database import Database


@dataclass(frozen=True)
class NamedOption:
    id: int
    label: str


@dataclass(frozen=True)
class ScriptFilterOptions:
    episodes: tuple[int, ...]
    characters: tuple[NamedOption, ...]
    talents: tuple[NamedOption, ...]


@dataclass(frozen=True)
class ScriptRow:
    dialogue_id: int
    episode_number: int
    time_in: str
    time_out: str
    dialogue: str
    characters: tuple[str, ...]
    talents: tuple[str | None, ...]
    source_file_name: str

    @property
    def has_unresolved_cast(self) -> bool:
        if not self.characters:
            return True
        return any(talent is None for talent in self.talents)


class DialogueService:
    """Read-only dialogue queries used by Script/Dialog UI pages."""

    def __init__(self, database: Database):
        self.database = database

    def get_script_filter_options(self) -> ScriptFilterOptions:
        with self.database.connect() as connection:
            episode_rows = connection.execute(
                """
                SELECT DISTINCT e.episode_number
                FROM dialogues AS d
                JOIN episodes AS e ON e.id = d.episode_id
                WHERE d.is_active = 1
                  AND e.is_active = 1
                ORDER BY e.episode_number
                """
            ).fetchall()

            character_rows = connection.execute(
                """
                SELECT DISTINCT c.id, c.name, c.normalized_name
                FROM dialogues AS d
                JOIN episodes AS e ON e.id = d.episode_id
                JOIN dialog_cast AS dc ON dc.dialogue_id = d.id
                JOIN characters AS c ON c.id = dc.character_id
                WHERE d.is_active = 1
                  AND e.is_active = 1
                  AND c.is_active = 1
                ORDER BY c.normalized_name, c.name
                """
            ).fetchall()

            talent_rows = connection.execute(
                """
                SELECT DISTINCT t.id, t.name, t.normalized_name
                FROM dialogues AS d
                JOIN episodes AS e ON e.id = d.episode_id
                JOIN dialog_cast AS dc ON dc.dialogue_id = d.id
                JOIN talents AS t ON t.id = dc.talent_id
                WHERE d.is_active = 1
                  AND e.is_active = 1
                  AND t.is_active = 1
                ORDER BY t.normalized_name, t.name
                """
            ).fetchall()

        return ScriptFilterOptions(
            episodes=tuple(int(row["episode_number"]) for row in episode_rows),
            characters=tuple(
                NamedOption(id=int(row["id"]), label=str(row["name"]))
                for row in character_rows
            ),
            talents=tuple(
                NamedOption(id=int(row["id"]), label=str(row["name"]))
                for row in talent_rows
            ),
        )

    def get_script_rows(
        self,
        *,
        episode_number: int | None = None,
        character_id: int | None = None,
        talent_id: int | None = None,
        search: str = "",
    ) -> list[ScriptRow]:
        conditions = [
            "d.is_active = 1",
            "e.is_active = 1",
        ]
        parameters: list[object] = []

        if episode_number is not None:
            conditions.append("e.episode_number = ?")
            parameters.append(int(episode_number))

        if character_id is not None:
            conditions.append(
                """
                EXISTS (
                    SELECT 1
                    FROM dialog_cast AS filter_dc
                    WHERE filter_dc.dialogue_id = d.id
                      AND filter_dc.character_id = ?
                )
                """
            )
            parameters.append(int(character_id))

        if talent_id is not None:
            conditions.append(
                """
                EXISTS (
                    SELECT 1
                    FROM dialog_cast AS filter_dc
                    WHERE filter_dc.dialogue_id = d.id
                      AND filter_dc.talent_id = ?
                )
                """
            )
            parameters.append(int(talent_id))

        normalized_search = search.strip()
        if normalized_search:
            pattern = self._like_pattern(normalized_search)
            conditions.append(
                """
                (
                    d.dialog_text LIKE ? ESCAPE '\\' COLLATE NOCASE
                    OR COALESCE(sf.file_name, '') LIKE ? ESCAPE '\\' COLLATE NOCASE
                    OR EXISTS (
                        SELECT 1
                        FROM dialog_cast AS search_dc
                        JOIN characters AS search_c
                          ON search_c.id = search_dc.character_id
                        LEFT JOIN talents AS search_t
                          ON search_t.id = search_dc.talent_id
                        WHERE search_dc.dialogue_id = d.id
                          AND (
                              search_c.name LIKE ? ESCAPE '\\' COLLATE NOCASE
                              OR COALESCE(search_t.name, '') LIKE ? ESCAPE '\\' COLLATE NOCASE
                          )
                    )
                )
                """
            )
            parameters.extend((pattern, pattern, pattern, pattern))

        where_clause = " AND ".join(f"({condition.strip()})" for condition in conditions)

        query = f"""
            SELECT
                d.id AS dialogue_id,
                e.episode_number,
                COALESCE(d.time_in, '') AS time_in,
                COALESCE(d.time_out, '') AS time_out,
                d.dialog_text,
                COALESCE(sf.file_name, '') AS source_file_name,
                dc.id AS dialog_cast_id,
                COALESCE(dc.position, 0) AS cast_position,
                c.id AS character_id,
                c.name AS character_name,
                t.id AS talent_id,
                t.name AS talent_name
            FROM dialogues AS d
            JOIN episodes AS e
              ON e.id = d.episode_id
            LEFT JOIN source_files AS sf
              ON sf.id = d.source_file_id
            LEFT JOIN dialog_cast AS dc
              ON dc.dialogue_id = d.id
            LEFT JOIN characters AS c
              ON c.id = dc.character_id
            LEFT JOIN talents AS t
              ON t.id = dc.talent_id
            WHERE {where_clause}
            ORDER BY
                e.episode_number,
                COALESCE(d.time_in, ''),
                COALESCE(d.source_row, 0),
                d.id,
                COALESCE(dc.position, 0),
                dc.id
        """

        with self.database.connect() as connection:
            rows = connection.execute(query, parameters).fetchall()

        return self._aggregate_script_rows(rows)

    @staticmethod
    def _like_pattern(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"

    @staticmethod
    def _aggregate_script_rows(rows) -> list[ScriptRow]:
        grouped: dict[int, dict[str, object]] = {}

        for row in rows:
            dialogue_id = int(row["dialogue_id"])

            item = grouped.get(dialogue_id)
            if item is None:
                item = {
                    "dialogue_id": dialogue_id,
                    "episode_number": int(row["episode_number"]),
                    "time_in": str(row["time_in"] or ""),
                    "time_out": str(row["time_out"] or ""),
                    "dialogue": str(row["dialog_text"] or ""),
                    "source_file_name": str(row["source_file_name"] or ""),
                    "characters": [],
                    "talents": [],
                    "seen_cast_ids": set(),
                }
                grouped[dialogue_id] = item

            cast_id = row["dialog_cast_id"]
            character_name = row["character_name"]

            if cast_id is None or character_name is None:
                continue

            seen_cast_ids = item["seen_cast_ids"]
            cast_key = int(cast_id)
            if cast_key in seen_cast_ids:
                continue

            seen_cast_ids.add(cast_key)
            item["characters"].append(str(character_name))
            talent_name = row["talent_name"]
            item["talents"].append(
                str(talent_name) if talent_name is not None else None
            )

        result: list[ScriptRow] = []
        for item in grouped.values():
            result.append(
                ScriptRow(
                    dialogue_id=int(item["dialogue_id"]),
                    episode_number=int(item["episode_number"]),
                    time_in=str(item["time_in"]),
                    time_out=str(item["time_out"]),
                    dialogue=str(item["dialogue"]),
                    characters=tuple(item["characters"]),
                    talents=tuple(item["talents"]),
                    source_file_name=str(item["source_file_name"]),
                )
            )

        return result
