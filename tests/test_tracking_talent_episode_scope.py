from __future__ import annotations

from core.database import Database
from services.tracking_service import TrackingService


def test_episode_options_only_include_episodes_played_by_selected_talent(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()

    with database.connect() as connection:
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
        source_3 = connection.execute(
            """
            INSERT INTO source_files(file_path, file_name, episode_number, is_active)
            VALUES('ep3.xlsx', 'ep3.xlsx', 3, 1)
            """
        ).lastrowid

        episode_ids = []
        for number, source_id in ((1, source_1), (2, source_2), (3, source_3)):
            episode_ids.append(
                connection.execute(
                    """
                    INSERT INTO episodes(episode_number, source_file_id, is_active)
                    VALUES(?, ?, 1)
                    """,
                    (number, source_id),
                ).lastrowid
            )

        character = connection.execute(
            """
            INSERT INTO characters(name, normalized_name, is_active)
            VALUES('Hendra', 'hendra', 1)
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

        for index, (episode_id, source_id, talent_id) in enumerate(
            (
                (episode_ids[0], source_1, brama),
                (episode_ids[1], source_2, dika),
                (episode_ids[2], source_3, brama),
            ),
            start=1,
        ):
            dialogue_id = connection.execute(
                """
                INSERT INTO dialogues(
                    dialog_uid, episode_id, source_file_id,
                    time_in, time_out, dialog_text, is_active
                )
                VALUES(?, ?, ?, '00:00:01,000', '00:00:02,000', ?, 1)
                """,
                (f'uid-{index}', episode_id, source_id, f'Dialog {index}'),
            ).lastrowid
            connection.execute(
                """
                INSERT INTO dialog_cast(dialogue_id, character_id, talent_id, position)
                VALUES(?, ?, ?, 0)
                """,
                (dialogue_id, character, talent_id),
            )

    service = TrackingService(database)

    assert service.get_episodes_for_talent(int(brama)) == [1, 3]
    assert service.get_episodes_for_talent(int(dika)) == [2]
