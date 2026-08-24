from __future__ import annotations

from core.database import Database
from services.dialogue_service import DialogueService


def _seed_database(database: Database) -> dict[str, int]:
    database.initialize()

    with database.connect() as connection:
        source_1 = connection.execute(
            """
            INSERT INTO source_files(
                file_path, file_name, episode_number, is_active
            )
            VALUES('ep1.xlsx', 'ep1.xlsx', 1, 1)
            """
        ).lastrowid
        source_2 = connection.execute(
            """
            INSERT INTO source_files(
                file_path, file_name, episode_number, is_active
            )
            VALUES('ep2.xlsx', 'ep2.xlsx', 2, 1)
            """
        ).lastrowid

        episode_1 = connection.execute(
            """
            INSERT INTO episodes(episode_number, source_file_id, is_active)
            VALUES(1, ?, 1)
            """,
            (source_1,),
        ).lastrowid
        episode_2 = connection.execute(
            """
            INSERT INTO episodes(episode_number, source_file_id, is_active)
            VALUES(2, ?, 1)
            """,
            (source_2,),
        ).lastrowid

        hendra = connection.execute(
            """
            INSERT INTO characters(name, normalized_name, is_active)
            VALUES('Hendra', 'hendra', 1)
            """
        ).lastrowid
        joko = connection.execute(
            """
            INSERT INTO characters(name, normalized_name, is_active)
            VALUES('Joko', 'joko', 1)
            """
        ).lastrowid

        brama = connection.execute(
            """
            INSERT INTO talents(name, normalized_name, is_active)
            VALUES('Brama', 'brama', 1)
            """
        ).lastrowid
        dika = connection.execute(
            """
            INSERT INTO talents(name, normalized_name, is_active)
            VALUES('Dika', 'dika', 1)
            """
        ).lastrowid

        dialogue_1 = connection.execute(
            """
            INSERT INTO dialogues(
                dialog_uid, episode_id, source_file_id,
                time_in, time_out, dialog_text, source_row, is_active
            )
            VALUES(
                'uid-1', ?, ?,
                '00:00:01,000', '00:00:03,000',
                'Dialog pertama', 3, 1
            )
            """,
            (episode_1, source_1),
        ).lastrowid

        connection.execute(
            """
            INSERT INTO dialog_cast(
                dialogue_id, character_id, talent_id, position
            )
            VALUES(?, ?, ?, 0)
            """,
            (dialogue_1, hendra, brama),
        )
        connection.execute(
            """
            INSERT INTO dialog_cast(
                dialogue_id, character_id, talent_id, position
            )
            VALUES(?, ?, ?, 1)
            """,
            (dialogue_1, joko, dika),
        )

        dialogue_2 = connection.execute(
            """
            INSERT INTO dialogues(
                dialog_uid, episode_id, source_file_id,
                time_in, time_out, dialog_text, source_row, is_active
            )
            VALUES(
                'uid-2', ?, ?,
                '00:00:04,000', '00:00:06,000',
                'Dialog kedua belum resolved', 4, 1
            )
            """,
            (episode_2, source_2),
        ).lastrowid

        connection.execute(
            """
            INSERT INTO dialog_cast(
                dialogue_id, character_id, talent_id, position
            )
            VALUES(?, ?, NULL, 0)
            """,
            (dialogue_2, hendra),
        )

    return {
        "hendra": int(hendra),
        "joko": int(joko),
        "brama": int(brama),
        "dika": int(dika),
    }


def test_filter_options_and_multicast_aggregation(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed_database(database)
    service = DialogueService(database)

    options = service.get_script_filter_options()

    assert options.episodes == (1, 2)
    assert [(item.id, item.label) for item in options.characters] == [
        (ids["hendra"], "Hendra"),
        (ids["joko"], "Joko"),
    ]
    assert [(item.id, item.label) for item in options.talents] == [
        (ids["brama"], "Brama"),
        (ids["dika"], "Dika"),
    ]

    rows = service.get_script_rows()
    assert len(rows) == 2
    assert rows[0].characters == ("Hendra", "Joko")
    assert rows[0].talents == ("Brama", "Dika")
    assert rows[0].has_unresolved_cast is False
    assert rows[1].characters == ("Hendra",)
    assert rows[1].talents == (None,)
    assert rows[1].has_unresolved_cast is True


def test_filters_keep_full_multicast_row(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed_database(database)
    service = DialogueService(database)

    rows = service.get_script_rows(character_id=ids["joko"])
    assert len(rows) == 1
    assert rows[0].characters == ("Hendra", "Joko")
    assert rows[0].talents == ("Brama", "Dika")

    rows = service.get_script_rows(talent_id=ids["dika"])
    assert len(rows) == 1
    assert rows[0].characters == ("Hendra", "Joko")

    rows = service.get_script_rows(episode_number=2)
    assert len(rows) == 1
    assert rows[0].dialogue == "Dialog kedua belum resolved"


def test_search_matches_dialogue_character_talent_and_literal_wildcards(tmp_path):
    database = Database(tmp_path / "project.db")
    _seed_database(database)
    service = DialogueService(database)

    assert [row.dialogue_id for row in service.get_script_rows(search="pertama")] == [1]
    assert [row.dialogue_id for row in service.get_script_rows(search="Joko")] == [1]
    assert [row.dialogue_id for row in service.get_script_rows(search="Brama")] == [1]
    assert service.get_script_rows(search="%") == []
