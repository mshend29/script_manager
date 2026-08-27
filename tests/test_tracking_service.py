from __future__ import annotations

import sqlite3

import pytest

from core.database import Database, SCHEMA_VERSION
from services.tracking_service import (
    AUTO_FILE_STATUS_NOTE,
    DELIVERED,
    IN_PROGRESS,
    NOT_READY,
    READY_TO_STEM,
    RECORDED,
    REVISION,
    STEMMED,
    TrackingService,
)


def _seed_tracking_database(database: Database) -> dict[str, int]:
    database.initialize()

    with database.connect() as connection:
        source_1 = connection.execute(
            """
            INSERT INTO source_files(
                file_path, file_name, episode_number, is_active
            ) VALUES('ep1.xlsx', 'ep1.xlsx', 1, 1)
            """
        ).lastrowid
        source_2 = connection.execute(
            """
            INSERT INTO source_files(
                file_path, file_name, episode_number, is_active
            ) VALUES('ep2.xlsx', 'ep2.xlsx', 2, 1)
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

        # EP1 multi-cast dialogue: recorded for both characters.
        multi = connection.execute(
            """
            INSERT INTO dialogues(
                dialog_uid, episode_id, source_file_id,
                time_in, time_out, dialog_text, is_active
            )
            VALUES('multi', ?, ?, '00:00:01,000', '00:00:03,000', 'Multi', 1)
            """,
            (episode_1, source_1),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO dialog_cast(dialogue_id, character_id, talent_id, position)
            VALUES(?, ?, ?, 0)
            """,
            (multi, hendra, brama),
        )
        connection.execute(
            """
            INSERT INTO dialog_cast(dialogue_id, character_id, talent_id, position)
            VALUES(?, ?, ?, 1)
            """,
            (multi, joko, brama),
        )
        connection.execute(
            """
            INSERT INTO recording_status(dialogue_id, is_recorded)
            VALUES(?, 1)
            """,
            (multi,),
        )

        # EP1 Hendra-only dialogue: not recorded, so Hendra is In Progress
        # while Joko is already Recorded for the same talent/episode.
        hendra_only = connection.execute(
            """
            INSERT INTO dialogues(
                dialog_uid, episode_id, source_file_id,
                time_in, time_out, dialog_text, is_active
            )
            VALUES('hendra-only', ?, ?, '00:00:04,000', '00:00:06,000', 'Hendra', 1)
            """,
            (episode_1, source_1),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO dialog_cast(dialogue_id, character_id, talent_id, position)
            VALUES(?, ?, ?, 0)
            """,
            (hendra_only, hendra, brama),
        )
        connection.execute(
            """
            INSERT INTO recording_status(dialogue_id, is_recorded)
            VALUES(?, 0)
            """,
            (hendra_only,),
        )

        # EP2 Hendra is fully recorded.
        ep2_dialogue = connection.execute(
            """
            INSERT INTO dialogues(
                dialog_uid, episode_id, source_file_id,
                time_in, time_out, dialog_text, is_active
            )
            VALUES('ep2-hendra', ?, ?, '00:00:01,000', '00:00:02,000', 'EP2', 1)
            """,
            (episode_2, source_2),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO dialog_cast(dialogue_id, character_id, talent_id, position)
            VALUES(?, ?, ?, 0)
            """,
            (ep2_dialogue, hendra, brama),
        )
        connection.execute(
            """
            INSERT INTO recording_status(dialogue_id, is_recorded)
            VALUES(?, 1)
            """,
            (ep2_dialogue,),
        )

    return {
        "episode_1": int(episode_1),
        "episode_2": int(episode_2),
        "hendra": int(hendra),
        "joko": int(joko),
        "brama": int(brama),
        "hendra_only": int(hendra_only),
    }


def _chips_by_character(service: TrackingService, talent_id: int):
    result = {}
    for row in service.get_character_rows(talent_id):
        result[row.character_name] = {
            chip.episode_number: chip
            for chip in row.chips
        }
    return result


def test_tracking_status_is_derived_per_character_episode(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed_tracking_database(database)
    service = TrackingService(database)

    talents = service.get_talents()
    assert [(item.id, item.label) for item in talents] == [
        (ids["brama"], "Brama")
    ]
    assert service.get_episodes_for_talent(ids["brama"]) == [1, 2]

    chips = _chips_by_character(service, ids["brama"])

    assert chips["Hendra"][1].recorded_dialogues == 1
    assert chips["Hendra"][1].total_dialogues == 2
    assert chips["Hendra"][1].display_status == IN_PROGRESS

    assert chips["Joko"][1].recorded_dialogues == 1
    assert chips["Joko"][1].total_dialogues == 1
    assert chips["Joko"][1].display_status == RECORDED

    assert chips["Hendra"][2].display_status == RECORDED


def test_revision_is_the_only_manual_downstream_status(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed_tracking_database(database)
    service = TrackingService(database)

    for automatic_status in (READY_TO_STEM, STEMMED, DELIVERED):
        with pytest.raises(ValueError, match="otomatis dari file"):
            service.set_downstream_status(
                episode_id=ids["episode_1"],
                talent_id=ids["brama"],
                character_id=ids["joko"],
                status=automatic_status,
            )

    service.set_downstream_status(
        episode_id=ids["episode_1"],
        talent_id=ids["brama"],
        character_id=ids["hendra"],
        status=REVISION,
    )
    chips = _chips_by_character(service, ids["brama"])
    assert chips["Hendra"][1].display_status == REVISION

    service.set_downstream_status(
        episode_id=ids["episode_1"],
        talent_id=ids["brama"],
        character_id=ids["hendra"],
        status=NOT_READY,
    )
    chips = _chips_by_character(service, ids["brama"])
    assert chips["Hendra"][1].display_status == IN_PROGRESS


def test_only_automatic_file_cache_can_show_stemmed_or_delivered(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed_tracking_database(database)
    service = TrackingService(database)

    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO stem_status(
                episode_id, talent_id, character_id, status, note
            ) VALUES(?, ?, ?, 'STEMMED', 'legacy-manual')
            """,
            (ids["episode_1"], ids["brama"], ids["joko"]),
        )

    chips = _chips_by_character(service, ids["brama"])
    assert chips["Joko"][1].display_status == RECORDED

    with database.connect() as connection:
        connection.execute(
            """
            UPDATE stem_status
            SET status = 'STEMMED', note = ?
            WHERE episode_id = ? AND talent_id = ? AND character_id = ?
            """,
            (
                AUTO_FILE_STATUS_NOTE,
                ids["episode_1"],
                ids["brama"],
                ids["joko"],
            ),
        )

    chips = _chips_by_character(service, ids["brama"])
    assert chips["Joko"][1].display_status == STEMMED

    with database.connect() as connection:
        connection.execute(
            """
            UPDATE stem_status
            SET status = 'DELIVERED', note = ?
            WHERE episode_id = ? AND talent_id = ? AND character_id = ?
            """,
            (
                AUTO_FILE_STATUS_NOTE,
                ids["episode_1"],
                ids["brama"],
                ids["joko"],
            ),
        )

    chips = _chips_by_character(service, ids["brama"])
    assert chips["Joko"][1].display_status == DELIVERED


def test_character_to_stem_queue_shows_recorded_or_revision_only(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed_tracking_database(database)
    service = TrackingService(database)

    queue = service.get_characters_to_stem(ids["brama"], 1)
    assert [(chip.character_name, chip.display_status) for chip in queue] == [
        ("Joko", RECORDED)
    ]

    service.set_downstream_status(
        episode_id=ids["episode_1"],
        talent_id=ids["brama"],
        character_id=ids["joko"],
        status=REVISION,
    )
    queue = service.get_characters_to_stem(ids["brama"], 1)
    assert [(chip.character_name, chip.display_status) for chip in queue] == [
        ("Joko", REVISION)
    ]


def test_schema_v3_allows_two_characters_for_same_talent_episode(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed_tracking_database(database)

    with database.connect() as connection:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(stem_status)")
        }
        assert "character_id" in columns

        connection.execute(
            """
            INSERT INTO stem_status(
                episode_id, talent_id, character_id, status
            ) VALUES(?, ?, ?, 'READY_TO_STEM')
            """,
            (ids["episode_1"], ids["brama"], ids["hendra"]),
        )
        connection.execute(
            """
            INSERT INTO stem_status(
                episode_id, talent_id, character_id, status
            ) VALUES(?, ?, ?, 'STEMMED')
            """,
            (ids["episode_1"], ids["brama"], ids["joko"]),
        )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO stem_status(
                    episode_id, talent_id, character_id, status
                ) VALUES(?, ?, ?, 'DELIVERED')
                """,
                (ids["episode_1"], ids["brama"], ids["joko"]),
            )

        version = connection.execute(
            "SELECT value FROM app_meta WHERE key = 'schema_version'"
        ).fetchone()["value"]
        assert version == str(SCHEMA_VERSION)
