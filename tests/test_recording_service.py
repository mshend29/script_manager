from __future__ import annotations

from core.database import Database
from services.recording_service import RecordingService


def _seed_recording_database(database: Database, source_path: str) -> dict[str, int]:
    database.initialize()

    with database.connect() as connection:
        source_1 = connection.execute(
            """
            INSERT INTO source_files(
                file_path, file_name, episode_number, is_active
            )
            VALUES(?, 'ep1.xlsx', 1, 1)
            """,
            (source_path,),
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
                'rec-uid-1', ?, ?,
                '00:00:01,000', '00:00:03,000',
                'Dialog pertama', 3, 1
            )
            """,
            (episode_1, source_1),
        ).lastrowid

        dialogue_2 = connection.execute(
            """
            INSERT INTO dialogues(
                dialog_uid, episode_id, source_file_id,
                time_in, time_out, dialog_text, source_row, is_active
            )
            VALUES(
                'rec-uid-2', ?, ?,
                '00:00:04,000', '00:00:06,000',
                'Dialog kedua', 4, 1
            )
            """,
            (episode_1, source_1),
        ).lastrowid

        dialogue_3 = connection.execute(
            """
            INSERT INTO dialogues(
                dialog_uid, episode_id, source_file_id,
                time_in, time_out, dialog_text, source_row, is_active
            )
            VALUES(
                'rec-uid-3', ?, ?,
                '00:00:02,000', '00:00:05,000',
                'Episode dua', 3, 1
            )
            """,
            (episode_2, source_2),
        ).lastrowid

        connection.executemany(
            """
            INSERT INTO dialog_cast(
                dialogue_id, character_id, talent_id, position
            )
            VALUES(?, ?, ?, ?)
            """,
            [
                (dialogue_1, hendra, brama, 0),
                (dialogue_1, joko, dika, 1),
                (dialogue_2, hendra, brama, 0),
                (dialogue_3, hendra, None, 0),
            ],
        )

    return {
        "hendra": int(hendra),
        "joko": int(joko),
        "dialogue_1": int(dialogue_1),
        "dialogue_2": int(dialogue_2),
        "dialogue_3": int(dialogue_3),
    }


def test_character_episode_and_cast_queries(tmp_path):
    source_path = tmp_path / "ep1.xlsx"
    source_path.touch()

    database = Database(tmp_path / "project.db")
    ids = _seed_recording_database(database, str(source_path))
    service = RecordingService(database)

    characters = service.get_characters()
    assert [(item.id, item.name) for item in characters] == [
        (ids["hendra"], "Hendra"),
        (ids["joko"], "Joko"),
    ]

    assert [
        item.episode_number
        for item in service.get_episodes_for_character(ids["hendra"])
    ] == [1, 2]

    assert [
        item.episode_number
        for item in service.get_episodes_for_character(ids["joko"])
    ] == [1]

    cast = service.get_episode_cast(1)
    assert [(item.character_name, item.talent_name) for item in cast] == [
        ("Hendra", "Brama"),
        ("Joko", "Dika"),
    ]

    unresolved_cast = service.get_episode_cast(2)
    assert unresolved_cast[0].character_name == "Hendra"
    assert unresolved_cast[0].is_resolved is False

    assert service.get_source_file_path(1) == str(source_path)
    assert service.source_file_exists(str(source_path)) is True


def test_individual_and_bulk_recording_persistence(tmp_path):
    source_path = tmp_path / "ep1.xlsx"
    source_path.touch()

    database = Database(tmp_path / "project.db")
    ids = _seed_recording_database(database, str(source_path))
    service = RecordingService(database)

    rows = service.get_dialogues(
        character_id=ids["hendra"],
        episode_number=1,
    )
    assert [row.dialogue_id for row in rows] == [
        ids["dialogue_1"],
        ids["dialogue_2"],
    ]
    assert [row.is_recorded for row in rows] == [False, False]

    service.set_recorded(ids["dialogue_1"], True)

    rows = service.get_dialogues(
        character_id=ids["hendra"],
        episode_number=1,
    )
    assert [row.is_recorded for row in rows] == [True, False]

    with database.connect() as connection:
        status = connection.execute(
            """
            SELECT is_recorded, recorded_at, updated_at
            FROM recording_status
            WHERE dialogue_id = ?
            """,
            (ids["dialogue_1"],),
        ).fetchone()

    assert int(status["is_recorded"]) == 1
    assert status["recorded_at"]
    assert status["updated_at"]

    changed = service.set_recorded_bulk(
        [ids["dialogue_1"], ids["dialogue_2"]],
        True,
    )
    assert changed == 2

    rows = service.get_dialogues(
        character_id=ids["hendra"],
        episode_number=1,
    )
    assert [row.is_recorded for row in rows] == [True, True]

    service.set_recorded_bulk(
        [ids["dialogue_1"], ids["dialogue_2"]],
        False,
    )

    rows = service.get_dialogues(
        character_id=ids["hendra"],
        episode_number=1,
    )
    assert [row.is_recorded for row in rows] == [False, False]


def test_recording_service_rejects_inactive_dialogue(tmp_path):
    source_path = tmp_path / "ep1.xlsx"
    source_path.touch()

    database = Database(tmp_path / "project.db")
    ids = _seed_recording_database(database, str(source_path))
    service = RecordingService(database)

    with database.connect() as connection:
        connection.execute(
            "UPDATE dialogues SET is_active = 0 WHERE id = ?",
            (ids["dialogue_2"],),
        )

    rows = service.get_dialogues(
        character_id=ids["hendra"],
        episode_number=1,
    )
    assert [row.dialogue_id for row in rows] == [ids["dialogue_1"]]

    try:
        service.set_recorded(ids["dialogue_2"], True)
    except ValueError as exc:
        assert "inactive" in str(exc)
    else:
        raise AssertionError("Inactive dialogue should not be writable")
