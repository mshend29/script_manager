from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.database import Database


@dataclass(frozen=True)
class RecordingTalentOption:
    id: int
    name: str


@dataclass(frozen=True)
class RecordingCharacterOption:
    id: int
    name: str


@dataclass(frozen=True)
class RecordingEpisodeOption:
    episode_number: int


@dataclass(frozen=True)
class EpisodeCastItem:
    character_id: int
    character_name: str
    talent_id: int | None
    talent_name: str

    @property
    def is_resolved(self) -> bool:
        return self.talent_id is not None and bool(self.talent_name)


@dataclass(frozen=True)
class RecordingDialogueRow:
    dialogue_id: int
    time_in: str
    time_out: str
    dialogue: str
    is_recorded: bool


class RecordingService:
    def __init__(self, database: Database):
        self.database = database

    def get_talents(self) -> list[RecordingTalentOption]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT
                    t.id,
                    t.name
                FROM talents AS t
                JOIN dialog_cast AS dc
                  ON dc.talent_id = t.id
                JOIN dialogues AS d
                  ON d.id = dc.dialogue_id
                JOIN episodes AS e
                  ON e.id = d.episode_id
                WHERE t.is_active = 1
                  AND d.is_active = 1
                  AND e.is_active = 1
                ORDER BY t.name COLLATE NOCASE, t.id
                """
            ).fetchall()

        return [
            RecordingTalentOption(
                id=int(row["id"]),
                name=str(row["name"]),
            )
            for row in rows
        ]

    def get_characters(self) -> list[RecordingCharacterOption]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT
                    c.id,
                    c.name
                FROM characters AS c
                JOIN dialog_cast AS dc
                  ON dc.character_id = c.id
                JOIN dialogues AS d
                  ON d.id = dc.dialogue_id
                JOIN episodes AS e
                  ON e.id = d.episode_id
                WHERE c.is_active = 1
                  AND d.is_active = 1
                  AND e.is_active = 1
                ORDER BY c.name COLLATE NOCASE, c.id
                """
            ).fetchall()

        return [
            RecordingCharacterOption(
                id=int(row["id"]),
                name=str(row["name"]),
            )
            for row in rows
        ]

    def get_characters_for_talent(
        self,
        talent_id: int,
    ) -> list[RecordingCharacterOption]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT
                    c.id,
                    c.name
                FROM dialog_cast AS dc
                JOIN characters AS c
                  ON c.id = dc.character_id
                JOIN dialogues AS d
                  ON d.id = dc.dialogue_id
                JOIN episodes AS e
                  ON e.id = d.episode_id
                WHERE dc.talent_id = ?
                  AND c.is_active = 1
                  AND d.is_active = 1
                  AND e.is_active = 1
                ORDER BY c.name COLLATE NOCASE, c.id
                """,
                (int(talent_id),),
            ).fetchall()

        return [
            RecordingCharacterOption(
                id=int(row["id"]),
                name=str(row["name"]),
            )
            for row in rows
        ]

    def get_episodes_for_character(
        self,
        character_id: int,
    ) -> list[RecordingEpisodeOption]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT
                    e.episode_number
                FROM episodes AS e
                JOIN dialogues AS d
                  ON d.episode_id = e.id
                JOIN dialog_cast AS dc
                  ON dc.dialogue_id = d.id
                WHERE e.is_active = 1
                  AND d.is_active = 1
                  AND dc.character_id = ?
                ORDER BY e.episode_number
                """,
                (int(character_id),),
            ).fetchall()

        return [
            RecordingEpisodeOption(
                episode_number=int(row["episode_number"]),
            )
            for row in rows
        ]

    def get_episodes_for_cast(
        self,
        *,
        talent_id: int,
        character_id: int,
    ) -> list[RecordingEpisodeOption]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT
                    e.episode_number
                FROM episodes AS e
                JOIN dialogues AS d
                  ON d.episode_id = e.id
                JOIN dialog_cast AS dc
                  ON dc.dialogue_id = d.id
                WHERE e.is_active = 1
                  AND d.is_active = 1
                  AND dc.character_id = ?
                  AND dc.talent_id = ?
                ORDER BY e.episode_number
                """,
                (
                    int(character_id),
                    int(talent_id),
                ),
            ).fetchall()

        return [
            RecordingEpisodeOption(
                episode_number=int(row["episode_number"]),
            )
            for row in rows
        ]

    def get_episode_cast(
        self,
        episode_number: int,
    ) -> list[EpisodeCastItem]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT
                    c.id AS character_id,
                    c.name AS character_name,
                    t.id AS talent_id,
                    t.name AS talent_name
                FROM episodes AS e
                JOIN dialogues AS d
                  ON d.episode_id = e.id
                JOIN dialog_cast AS dc
                  ON dc.dialogue_id = d.id
                JOIN characters AS c
                  ON c.id = dc.character_id
                LEFT JOIN talents AS t
                  ON t.id = dc.talent_id
                WHERE e.episode_number = ?
                  AND e.is_active = 1
                  AND d.is_active = 1
                  AND c.is_active = 1
                ORDER BY
                    c.name COLLATE NOCASE,
                    t.name COLLATE NOCASE
                """,
                (int(episode_number),),
            ).fetchall()

        return [
            EpisodeCastItem(
                character_id=int(row["character_id"]),
                character_name=str(row["character_name"]),
                talent_id=(
                    int(row["talent_id"])
                    if row["talent_id"] is not None
                    else None
                ),
                talent_name=str(row["talent_name"] or ""),
            )
            for row in rows
        ]

    def get_dialogues(
        self,
        *,
        character_id: int,
        episode_number: int,
        talent_id: int | None = None,
    ) -> list[RecordingDialogueRow]:
        cast_conditions = ["dc.character_id = ?"]
        params: list[object] = [
            int(episode_number),
            int(character_id),
        ]

        if talent_id is not None:
            cast_conditions.append("dc.talent_id = ?")
            params.append(int(talent_id))

        cast_where = " AND ".join(cast_conditions)

        with self.database.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    d.id AS dialogue_id,
                    COALESCE(d.time_in, '') AS time_in,
                    COALESCE(d.time_out, '') AS time_out,
                    d.dialog_text,
                    COALESCE(rs.is_recorded, 0) AS is_recorded
                FROM dialogues AS d
                JOIN episodes AS e
                  ON e.id = d.episode_id
                LEFT JOIN recording_status AS rs
                  ON rs.dialogue_id = d.id
                WHERE e.episode_number = ?
                  AND e.is_active = 1
                  AND d.is_active = 1
                  AND EXISTS (
                      SELECT 1
                      FROM dialog_cast AS dc
                      WHERE dc.dialogue_id = d.id
                        AND {cast_where}
                  )
                ORDER BY
                    d.time_in,
                    d.source_row,
                    d.id
                """,
                params,
            ).fetchall()

        return [
            RecordingDialogueRow(
                dialogue_id=int(row["dialogue_id"]),
                time_in=str(row["time_in"]),
                time_out=str(row["time_out"]),
                dialogue=str(row["dialog_text"]),
                is_recorded=bool(row["is_recorded"]),
            )
            for row in rows
        ]

    def get_source_file_path(
        self,
        episode_number: int,
    ) -> str:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT sf.file_path
                FROM episodes AS e
                JOIN source_files AS sf
                  ON sf.id = e.source_file_id
                WHERE e.episode_number = ?
                  AND e.is_active = 1
                  AND sf.is_active = 1
                LIMIT 1
                """,
                (int(episode_number),),
            ).fetchone()

        if row is None:
            return ""

        return str(row["file_path"] or "")

    def set_recorded(
        self,
        dialogue_id: int,
        recorded: bool,
    ) -> None:
        timestamp = datetime.now().isoformat(timespec="seconds")  # noqa: DTZ005

        with self.database.connect() as connection:
            exists = connection.execute(
                """
                SELECT 1
                FROM dialogues
                WHERE id = ?
                  AND is_active = 1
                """,
                (int(dialogue_id),),
            ).fetchone()

            if exists is None:
                raise ValueError(
                    f"Dialogue {dialogue_id} tidak ditemukan atau sudah inactive."
                )

            connection.execute(
                """
                INSERT INTO recording_status(
                    dialogue_id,
                    is_recorded,
                    recorded_at,
                    updated_at
                )
                VALUES(?, ?, ?, ?)
                ON CONFLICT(dialogue_id)
                DO UPDATE SET
                    is_recorded = excluded.is_recorded,
                    recorded_at = excluded.recorded_at,
                    updated_at = excluded.updated_at
                """,
                (
                    int(dialogue_id),
                    1 if recorded else 0,
                    timestamp if recorded else None,
                    timestamp,
                ),
            )

    def set_recorded_bulk(
        self,
        dialogue_ids: list[int] | tuple[int, ...],
        recorded: bool,
    ) -> int:
        ids = sorted({int(value) for value in dialogue_ids})

        if not ids:
            return 0

        timestamp = datetime.now().isoformat(timespec="seconds")  # noqa: DTZ005

        placeholders = ",".join("?" for _ in ids)

        with self.database.connect() as connection:
            active_rows = connection.execute(
                f"""
                SELECT id
                FROM dialogues
                WHERE is_active = 1
                  AND id IN ({placeholders})
                """,
                ids,
            ).fetchall()

            active_ids = {int(row["id"]) for row in active_rows}

            if active_ids != set(ids):
                missing = sorted(set(ids) - active_ids)
                raise ValueError(
                    "Dialogue tidak ditemukan atau sudah inactive: "
                    + ", ".join(str(value) for value in missing)
                )

            connection.executemany(
                """
                INSERT INTO recording_status(
                    dialogue_id,
                    is_recorded,
                    recorded_at,
                    updated_at
                )
                VALUES(?, ?, ?, ?)
                ON CONFLICT(dialogue_id)
                DO UPDATE SET
                    is_recorded = excluded.is_recorded,
                    recorded_at = excluded.recorded_at,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        dialogue_id,
                        1 if recorded else 0,
                        timestamp if recorded else None,
                        timestamp,
                    )
                    for dialogue_id in ids
                ],
            )

        return len(ids)

    @staticmethod
    def source_file_exists(path: str) -> bool:
        return bool(path) and Path(path).is_file()
