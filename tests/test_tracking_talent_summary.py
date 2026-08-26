from __future__ import annotations

from pathlib import Path

from core.database import Database
from services.tracking_summary_service import TrackingSummaryService


ROOT = Path(__file__).resolve().parents[1]


def test_talent_summary_counts_distinct_dialogues_across_characters(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()

    with database.connect() as connection:
        talent_id = connection.execute(
            "INSERT INTO talents(name, normalized_name, is_active) VALUES('Brama', 'brama', 1)"
        ).lastrowid
        andi_id = connection.execute(
            "INSERT INTO characters(name, normalized_name, is_active) VALUES('Andi', 'andi', 1)"
        ).lastrowid
        bapak_id = connection.execute(
            "INSERT INTO characters(name, normalized_name, is_active) VALUES('Bapak', 'bapak', 1)"
        ).lastrowid

        source_1 = connection.execute(
            """
            INSERT INTO source_files(file_path, file_name, episode_number, is_active)
            VALUES('ep1.xlsx', 'ep1.xlsx', 1, 1)
            """
        ).lastrowid
        source_2 = connection.execute(
            """
            INSERT INTO source_files(file_path, file_name, episode_number, is_active)
            VALUES('ep2.xlsx', 'ep2.xlsx', 2, 1)
            """
        ).lastrowid
        episode_1 = connection.execute(
            "INSERT INTO episodes(episode_number, source_file_id, is_active) VALUES(1, ?, 1)",
            (source_1,),
        ).lastrowid
        episode_2 = connection.execute(
            "INSERT INTO episodes(episode_number, source_file_id, is_active) VALUES(2, ?, 1)",
            (source_2,),
        ).lastrowid

        shared_dialogue = connection.execute(
            """
            INSERT INTO dialogues(dialog_uid, episode_id, source_file_id, dialog_text, is_active)
            VALUES('uid-1', ?, ?, 'Dialog bersama', 1)
            """,
            (episode_1, source_1),
        ).lastrowid
        second_dialogue = connection.execute(
            """
            INSERT INTO dialogues(dialog_uid, episode_id, source_file_id, dialog_text, is_active)
            VALUES('uid-2', ?, ?, 'Dialog kedua', 1)
            """,
            (episode_2, source_2),
        ).lastrowid

        connection.execute(
            "INSERT INTO dialog_cast(dialogue_id, character_id, talent_id, position) VALUES(?, ?, ?, 0)",
            (shared_dialogue, andi_id, talent_id),
        )
        connection.execute(
            "INSERT INTO dialog_cast(dialogue_id, character_id, talent_id, position) VALUES(?, ?, ?, 1)",
            (shared_dialogue, bapak_id, talent_id),
        )
        connection.execute(
            "INSERT INTO dialog_cast(dialogue_id, character_id, talent_id, position) VALUES(?, ?, ?, 0)",
            (second_dialogue, andi_id, talent_id),
        )

    summary = TrackingSummaryService(database).get_talent_summary(int(talent_id))

    assert summary.character_count == 2
    assert summary.episode_count == 2
    assert summary.dialogue_count == 2


def test_tracking_summary_line_has_padding_and_three_totals():
    source = (ROOT / "pages" / "tracking_compact_page.py").read_text(encoding="utf-8")

    assert "self.summary_label.setContentsMargins(8, 2, 8, 2)" in source
    assert 'f"Tokoh: {self._format_count(summary.character_count)}' in source
    assert 'f"Episode: {self._format_count(summary.episode_count)}' in source
    assert 'f"Dialog: {self._format_count(summary.dialogue_count)}' in source
