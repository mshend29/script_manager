from __future__ import annotations

from dataclasses import dataclass

from core.database import Database


@dataclass(frozen=True)
class TrackingTalentSummary:
    character_count: int
    episode_count: int
    dialogue_count: int


class TrackingSummaryService:
    """Aggregate compact totals for one talent across active tracking data."""

    def __init__(self, database: Database):
        self.database = database

    def get_talent_summary(self, talent_id: int) -> TrackingTalentSummary:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(DISTINCT dc.character_id) AS character_count,
                    COUNT(DISTINCT d.episode_id) AS episode_count,
                    COUNT(DISTINCT d.id) AS dialogue_count
                FROM dialog_cast AS dc
                JOIN dialogues AS d
                  ON d.id = dc.dialogue_id
                 AND d.is_active = 1
                JOIN episodes AS e
                  ON e.id = d.episode_id
                 AND e.is_active = 1
                JOIN characters AS c
                  ON c.id = dc.character_id
                 AND c.is_active = 1
                JOIN talents AS t
                  ON t.id = dc.talent_id
                 AND t.is_active = 1
                WHERE dc.talent_id = ?
                """,
                (int(talent_id),),
            ).fetchone()

        if row is None:
            return TrackingTalentSummary(0, 0, 0)

        return TrackingTalentSummary(
            character_count=int(row["character_count"] or 0),
            episode_count=int(row["episode_count"] or 0),
            dialogue_count=int(row["dialogue_count"] or 0),
        )
