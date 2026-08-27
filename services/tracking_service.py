from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from core.database import Database


NOT_STARTED = "NOT_STARTED"
IN_PROGRESS = "IN_PROGRESS"
RECORDED = "RECORDED"
READY_TO_STEM = "READY_TO_STEM"
STEMMED = "STEMMED"
DELIVERED = "DELIVERED"
REVISION = "REVISION"
NOT_READY = "NOT_READY"
AUTO_FILE_STATUS_NOTE = "auto:file-inventory"

# Only Revision remains a manual downstream state. STEMMED/DELIVERED are
# derived from filesystem inventory; READY_TO_STEM is retained only for
# compatibility with historical rows and is no longer an active workflow state.
DOWNSTREAM_STATUSES = {
    NOT_READY,
    REVISION,
}

STATUS_LABELS = {
    NOT_STARTED: "Not Started",
    IN_PROGRESS: "In Progress",
    RECORDED: "Recorded",
    READY_TO_STEM: "Ready to Stem",
    STEMMED: "Stemmed",
    DELIVERED: "Delivered",
    REVISION: "Revision",
}


@dataclass(frozen=True)
class TrackingOption:
    id: int
    label: str


@dataclass(frozen=True)
class TrackingChip:
    episode_id: int
    episode_number: int
    character_id: int
    character_name: str
    talent_id: int
    talent_name: str
    total_dialogues: int
    recorded_dialogues: int
    recording_status: str
    downstream_status: str
    downstream_note: str
    display_status: str

    @property
    def progress_text(self) -> str:
        return f"{self.recorded_dialogues}/{self.total_dialogues}"

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.display_status, self.display_status)


@dataclass
class TrackingCharacterRow:
    character_id: int
    character_name: str
    chips: list[TrackingChip] = field(default_factory=list)


class TrackingService:
    def __init__(self, database: Database):
        self.database = database

    # ------------------------------------------------------------------
    # FILTER OPTIONS
    # ------------------------------------------------------------------

    def get_talents(self) -> list[TrackingOption]:
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
                 AND d.is_active = 1
                JOIN episodes AS e
                  ON e.id = d.episode_id
                 AND e.is_active = 1
                WHERE t.is_active = 1
                ORDER BY t.name COLLATE NOCASE, t.id
                """
            ).fetchall()

        return [
            TrackingOption(id=int(row["id"]), label=str(row["name"]))
            for row in rows
        ]

    def get_episodes_for_talent(self, talent_id: int) -> list[int]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT e.episode_number
                FROM dialog_cast AS dc
                JOIN dialogues AS d
                  ON d.id = dc.dialogue_id
                 AND d.is_active = 1
                JOIN episodes AS e
                  ON e.id = d.episode_id
                 AND e.is_active = 1
                WHERE dc.talent_id = ?
                ORDER BY e.episode_number
                """,
                (int(talent_id),),
            ).fetchall()

        return [int(row["episode_number"]) for row in rows]

    # ------------------------------------------------------------------
    # TRACKING AGGREGATION
    # ------------------------------------------------------------------

    def get_character_rows(
        self,
        talent_id: int,
        *,
        episode_number: int | None = None,
    ) -> list[TrackingCharacterRow]:
        where = ["dc.talent_id = ?"]
        params: list[object] = [int(talent_id)]

        if episode_number is not None:
            where.append("e.episode_number = ?")
            params.append(int(episode_number))

        query = f"""
            SELECT
                e.id AS episode_id,
                e.episode_number,
                c.id AS character_id,
                c.name AS character_name,
                t.id AS talent_id,
                t.name AS talent_name,
                COUNT(DISTINCT d.id) AS total_dialogues,
                COUNT(
                    DISTINCT CASE
                        WHEN COALESCE(rs.is_recorded, 0) = 1
                        THEN d.id
                    END
                ) AS recorded_dialogues,
                COALESCE(ss.status, 'NOT_READY') AS downstream_status,
                COALESCE(ss.note, '') AS downstream_note
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
            LEFT JOIN recording_status AS rs
              ON rs.dialogue_id = d.id
            LEFT JOIN stem_status AS ss
              ON ss.episode_id = e.id
             AND ss.talent_id = t.id
             AND ss.character_id = c.id
            WHERE {' AND '.join(where)}
            GROUP BY
                e.id,
                e.episode_number,
                c.id,
                c.name,
                t.id,
                t.name,
                ss.status,
                ss.note
            ORDER BY
                c.name COLLATE NOCASE,
                c.id,
                e.episode_number
        """

        with self.database.connect() as connection:
            rows = connection.execute(query, params).fetchall()

        grouped: dict[int, TrackingCharacterRow] = {}

        for row in rows:
            total = int(row["total_dialogues"] or 0)
            recorded = int(row["recorded_dialogues"] or 0)
            downstream = str(row["downstream_status"] or NOT_READY)
            downstream_note = str(row["downstream_note"] or "")
            recording_status = derive_recording_status(recorded, total)
            display_status = derive_display_status(
                recorded_dialogues=recorded,
                total_dialogues=total,
                downstream_status=downstream,
                downstream_note=downstream_note,
            )

            chip = TrackingChip(
                episode_id=int(row["episode_id"]),
                episode_number=int(row["episode_number"]),
                character_id=int(row["character_id"]),
                character_name=str(row["character_name"]),
                talent_id=int(row["talent_id"]),
                talent_name=str(row["talent_name"]),
                total_dialogues=total,
                recorded_dialogues=recorded,
                recording_status=recording_status,
                downstream_status=downstream,
                downstream_note=downstream_note,
                display_status=display_status,
            )

            character_id = chip.character_id
            if character_id not in grouped:
                grouped[character_id] = TrackingCharacterRow(
                    character_id=character_id,
                    character_name=chip.character_name,
                )

            grouped[character_id].chips.append(chip)

        return list(grouped.values())

    def get_characters_to_stem(
        self,
        talent_id: int,
        episode_number: int,
    ) -> list[TrackingChip]:
        rows = self.get_character_rows(
            talent_id,
            episode_number=episode_number,
        )

        work_statuses = {RECORDED, REVISION}
        result: list[TrackingChip] = []

        for row in rows:
            for chip in row.chips:
                if chip.display_status in work_statuses:
                    result.append(chip)

        return result

    # ------------------------------------------------------------------
    # DOWNSTREAM STATUS
    # ------------------------------------------------------------------

    def set_downstream_status(
        self,
        *,
        episode_id: int,
        talent_id: int,
        character_id: int,
        status: str,
        note: str = "",
    ) -> None:
        normalized_status = str(status).strip().upper()

        if normalized_status not in DOWNSTREAM_STATUSES:
            raise ValueError(
                "Stemmed dan Delivered sekarang otomatis dari file. "
                "Tracking manual hanya mendukung Revision atau kembali ke Auto."
            )

        with self.database.connect() as connection:
            total, recorded = self._get_progress(
                connection,
                episode_id=int(episode_id),
                talent_id=int(talent_id),
                character_id=int(character_id),
            )

            if total < 1:
                raise ValueError(
                    "Kombinasi episode, talent, dan character tidak memiliki dialog aktif."
                )

            if normalized_status == NOT_READY:
                connection.execute(
                    """
                    DELETE FROM stem_status
                    WHERE episode_id = ?
                      AND talent_id = ?
                      AND character_id = ?
                    """,
                    (
                        int(episode_id),
                        int(talent_id),
                        int(character_id),
                    ),
                )
                return

            now = datetime.now().isoformat(timespec="seconds")

            connection.execute(
                """
                INSERT INTO stem_status(
                    episode_id,
                    talent_id,
                    character_id,
                    status,
                    note,
                    updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(episode_id, talent_id, character_id)
                DO UPDATE SET
                    status = excluded.status,
                    note = excluded.note,
                    updated_at = excluded.updated_at
                """,
                (
                    int(episode_id),
                    int(talent_id),
                    int(character_id),
                    normalized_status,
                    note.strip(),
                    now,
                ),
            )

    @staticmethod
    def _get_progress(
        connection,
        *,
        episode_id: int,
        talent_id: int,
        character_id: int,
    ) -> tuple[int, int]:
        row = connection.execute(
            """
            SELECT
                COUNT(DISTINCT d.id) AS total_dialogues,
                COUNT(
                    DISTINCT CASE
                        WHEN COALESCE(rs.is_recorded, 0) = 1
                        THEN d.id
                    END
                ) AS recorded_dialogues
            FROM dialog_cast AS dc
            JOIN dialogues AS d
              ON d.id = dc.dialogue_id
             AND d.is_active = 1
            JOIN episodes AS e
              ON e.id = d.episode_id
             AND e.is_active = 1
            LEFT JOIN recording_status AS rs
              ON rs.dialogue_id = d.id
            WHERE d.episode_id = ?
              AND dc.talent_id = ?
              AND dc.character_id = ?
            """,
            (episode_id, talent_id, character_id),
        ).fetchone()

        if row is None:
            return 0, 0

        return (
            int(row["total_dialogues"] or 0),
            int(row["recorded_dialogues"] or 0),
        )


def derive_recording_status(recorded_dialogues: int, total_dialogues: int) -> str:
    if total_dialogues < 1 or recorded_dialogues < 1:
        return NOT_STARTED

    if recorded_dialogues < total_dialogues:
        return IN_PROGRESS

    return RECORDED


def derive_display_status(
    *,
    recorded_dialogues: int,
    total_dialogues: int,
    downstream_status: str,
    downstream_note: str = "",
) -> str:
    downstream = str(downstream_status or NOT_READY).strip().upper()

    if downstream == REVISION:
        return REVISION

    recording = derive_recording_status(recorded_dialogues, total_dialogues)

    if recording != RECORDED:
        return recording

    if (
        downstream in {STEMMED, DELIVERED}
        and str(downstream_note or "").strip() == AUTO_FILE_STATUS_NOTE
    ):
        return downstream

    # Historical READY_TO_STEM/manual STEMMED/DELIVERED rows no longer drive
    # display state. Without a valid automatic file inventory the recorded
    # state is authoritative.
    return RECORDED
