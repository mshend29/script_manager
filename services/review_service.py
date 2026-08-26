from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.database import Database


NON_DIALOGUE = "NON_DIALOGUE"


@dataclass(frozen=True)
class ReviewedDialogueRow:
    dialogue_id: int
    episode_number: int
    dialogue: str
    source_file_name: str
    source_file_path: str
    reviewed_at: str
    note: str


class ReviewService:
    def __init__(self, database: Database):
        self.database = database

    def get_active_non_dialogue_ids(self) -> set[int]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT dr.dialogue_id
                FROM dialogue_review AS dr
                JOIN dialogues AS d ON d.id = dr.dialogue_id
                JOIN episodes AS e ON e.id = d.episode_id
                WHERE dr.classification = ?
                  AND d.is_active = 1
                  AND e.is_active = 1
                """,
                (NON_DIALOGUE,),
            ).fetchall()
        return {int(row["dialogue_id"]) for row in rows}

    def get_active_non_dialogue_count(self) -> int:
        return len(self.get_active_non_dialogue_ids())

    def get_non_dialogues(self) -> list[ReviewedDialogueRow]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    d.id AS dialogue_id,
                    e.episode_number,
                    d.dialog_text,
                    COALESCE(sf.file_name, '') AS source_file_name,
                    COALESCE(sf.file_path, '') AS source_file_path,
                    dr.reviewed_at,
                    COALESCE(dr.note, '') AS note
                FROM dialogue_review AS dr
                JOIN dialogues AS d ON d.id = dr.dialogue_id
                JOIN episodes AS e ON e.id = d.episode_id
                LEFT JOIN source_files AS sf ON sf.id = d.source_file_id
                WHERE dr.classification = ?
                  AND d.is_active = 1
                  AND e.is_active = 1
                ORDER BY e.episode_number, d.source_row, d.id
                """,
                (NON_DIALOGUE,),
            ).fetchall()

        return [
            ReviewedDialogueRow(
                dialogue_id=int(row["dialogue_id"]),
                episode_number=int(row["episode_number"]),
                dialogue=str(row["dialog_text"]),
                source_file_name=str(row["source_file_name"] or ""),
                source_file_path=str(row["source_file_path"] or ""),
                reviewed_at=str(row["reviewed_at"] or ""),
                note=str(row["note"] or ""),
            )
            for row in rows
        ]

    def mark_non_dialogue(self, dialogue_id: int, note: str = "") -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self.database.connect() as connection:
            dialogue = connection.execute(
                """
                SELECT d.id
                FROM dialogues AS d
                JOIN episodes AS e ON e.id = d.episode_id
                WHERE d.id = ?
                  AND d.is_active = 1
                  AND e.is_active = 1
                """,
                (int(dialogue_id),),
            ).fetchone()
            if dialogue is None:
                raise ValueError("Dialog tidak ditemukan atau sudah inactive.")

            existing_cast = connection.execute(
                "SELECT 1 FROM dialog_cast WHERE dialogue_id = ? LIMIT 1",
                (int(dialogue_id),),
            ).fetchone()
            if existing_cast is not None:
                raise ValueError(
                    "Hanya row tanpa character/cast yang dapat ditandai sebagai Narration / Non-Dialogue."
                )

            connection.execute(
                """
                INSERT INTO dialogue_review(
                    dialogue_id, classification, note, reviewed_at
                ) VALUES(?, ?, ?, ?)
                ON CONFLICT(dialogue_id)
                DO UPDATE SET
                    classification = excluded.classification,
                    note = excluded.note,
                    reviewed_at = excluded.reviewed_at
                """,
                (int(dialogue_id), NON_DIALOGUE, note.strip(), now),
            )

    def restore_to_review(self, dialogue_id: int) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                DELETE FROM dialogue_review
                WHERE dialogue_id = ? AND classification = ?
                """,
                (int(dialogue_id), NON_DIALOGUE),
            )
