from __future__ import annotations

from pathlib import Path

from core.database import Database
from services.recording_service import RecordingService


ROOT = Path(__file__).resolve().parents[1]


def _seed(database: Database) -> dict[str, int]:
    database.initialize()
    with database.connect() as connection:
        source1 = connection.execute(
            "INSERT INTO source_files(file_path, file_name, episode_number, is_active) VALUES('ep1.xlsx', 'ep1.xlsx', 1, 1)"
        ).lastrowid
        source2 = connection.execute(
            "INSERT INTO source_files(file_path, file_name, episode_number, is_active) VALUES('ep2.xlsx', 'ep2.xlsx', 2, 1)"
        ).lastrowid
        ep1 = connection.execute(
            "INSERT INTO episodes(episode_number, source_file_id, is_active) VALUES(1, ?, 1)",
            (source1,),
        ).lastrowid
        ep2 = connection.execute(
            "INSERT INTO episodes(episode_number, source_file_id, is_active) VALUES(2, ?, 1)",
            (source2,),
        ).lastrowid
        hendra = connection.execute(
            "INSERT INTO characters(name, normalized_name, is_active) VALUES('Hendra', 'hendra', 1)"
        ).lastrowid
        joko = connection.execute(
            "INSERT INTO characters(name, normalized_name, is_active) VALUES('Joko', 'joko', 1)"
        ).lastrowid
        brama = connection.execute(
            "INSERT INTO talents(name, normalized_name, is_active) VALUES('Brama', 'brama', 1)"
        ).lastrowid
        vega = connection.execute(
            "INSERT INTO talents(name, normalized_name, is_active) VALUES('Vega', 'vega', 1)"
        ).lastrowid

        d1 = connection.execute(
            """
            INSERT INTO dialogues(dialog_uid, episode_id, source_file_id, time_in, time_out, dialog_text, source_row, is_active)
            VALUES('d1', ?, ?, '00:00:01,000', '00:00:02,000', 'Brama Hendra', 3, 1)
            """,
            (ep1, source1),
        ).lastrowid
        d2 = connection.execute(
            """
            INSERT INTO dialogues(dialog_uid, episode_id, source_file_id, time_in, time_out, dialog_text, source_row, is_active)
            VALUES('d2', ?, ?, '00:00:03,000', '00:00:04,000', 'Brama Joko', 4, 1)
            """,
            (ep1, source1),
        ).lastrowid
        d3 = connection.execute(
            """
            INSERT INTO dialogues(dialog_uid, episode_id, source_file_id, time_in, time_out, dialog_text, source_row, is_active)
            VALUES('d3', ?, ?, '00:00:01,000', '00:00:02,000', 'Vega Hendra', 3, 1)
            """,
            (ep2, source2),
        ).lastrowid

        connection.executemany(
            "INSERT INTO dialog_cast(dialogue_id, character_id, talent_id, position) VALUES(?, ?, ?, 0)",
            [
                (d1, hendra, brama),
                (d2, joko, brama),
                (d3, hendra, vega),
            ],
        )

    return {
        "hendra": int(hendra),
        "joko": int(joko),
        "brama": int(brama),
        "vega": int(vega),
    }


def test_talent_character_episode_chain_filters_real_cast_scope(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed(database)
    service = RecordingService(database)

    assert [(item.id, item.name) for item in service.get_talents()] == [
        (ids["brama"], "Brama"),
        (ids["vega"], "Vega"),
    ]

    assert [(item.id, item.name) for item in service.get_characters_for_talent(ids["brama"])] == [
        (ids["hendra"], "Hendra"),
        (ids["joko"], "Joko"),
    ]
    assert [(item.id, item.name) for item in service.get_characters_for_talent(ids["vega"])] == [
        (ids["hendra"], "Hendra"),
    ]

    assert [item.episode_number for item in service.get_episodes_for_cast(
        talent_id=ids["brama"], character_id=ids["hendra"]
    )] == [1]
    assert [item.episode_number for item in service.get_episodes_for_cast(
        talent_id=ids["vega"], character_id=ids["hendra"]
    )] == [2]

    assert [row.dialogue for row in service.get_dialogues(
        talent_id=ids["brama"], character_id=ids["hendra"], episode_number=1
    )] == ["Brama Hendra"]
    assert service.get_dialogues(
        talent_id=ids["brama"], character_id=ids["hendra"], episode_number=2
    ) == []


def test_dialog_page_declares_talent_first_cast_table_and_centered_checkbox():
    source = (ROOT / "pages" / "dialog_page.py").read_text(encoding="utf-8")

    assert source.index('QLabel("Talent")') < source.index('QLabel("Tokoh")')
    assert source.index('QLabel("Tokoh")') < source.index('QLabel("Episode")')
    assert 'setHorizontalHeaderLabels(["TOKOH", "TALENT"])' in source
    assert "QCheckBox" in source
    assert "holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)" in source
    assert "get_characters_for_talent" in source
    assert "get_episodes_for_cast" in source
