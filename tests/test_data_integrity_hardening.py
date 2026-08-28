from datetime import datetime as real_datetime

from core.database import Database
from services import backup_service as backup_service_module
from services.data_service import DataService


def _seed_characterless_dialogue(database: Database) -> dict[str, int]:
    database.initialize()
    with database.connect() as connection:
        source_id = connection.execute(
            """
            INSERT INTO source_files(
                file_path, file_name, episode_number,
                fingerprint, is_active, imported_at, last_seen_at
            ) VALUES(
                'ep53.xlsx', 'ep53.xlsx', 53,
                'fingerprint-53', 1,
                '2026-08-24T10:00:00', '2026-08-24T10:00:00'
            )
            """
        ).lastrowid
        episode_id = connection.execute(
            """
            INSERT INTO episodes(
                episode_number, source_file_id, title, is_active
            ) VALUES(53, ?, 'EP 53', 1)
            """,
            (source_id,),
        ).lastrowid
        dialogue_id = connection.execute(
            """
            INSERT INTO dialogues(
                dialog_uid, episode_id, source_file_id,
                time_in, time_out, dialog_text, source_row, is_active
            ) VALUES(
                'ep53-no-cast', ?, ?,
                '00:00:10,000', '00:00:12,000',
                'Setengah bulan kemudian', 16, 1
            )
            """,
            (episode_id, source_id),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO recording_status(
                dialogue_id, is_recorded, recorded_at, updated_at
            ) VALUES(?, 0, NULL, '2026-08-24T10:00:00')
            """,
            (dialogue_id,),
        )

    return {
        "source": int(source_id),
        "episode": int(episode_id),
        "dialogue": int(dialogue_id),
    }


def test_characterless_active_dialogue_is_visible_and_validated(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed_characterless_dialogue(database)
    service = DataService(database)

    overview = service.get_overview()
    assert overview.unresolved_cast == 1

    unresolved = service.get_unresolved_cast()
    assert len(unresolved) == 1
    assert unresolved[0].dialogue_id == ids["dialogue"]
    assert unresolved[0].episode_number == 53
    assert unresolved[0].character_id is None
    assert unresolved[0].character_name == "⚠ Missing Character"

    issues = service.validate()
    issue = next(
        item for item in issues if item.code == "ACTIVE_DIALOGUE_NO_CAST"
    )
    assert issue.severity == "WARNING"


def test_active_episode_with_only_inactive_history_is_an_error(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed_characterless_dialogue(database)
    service = DataService(database)

    with database.connect() as connection:
        connection.execute(
            "UPDATE dialogues SET is_active = 0 WHERE id = ?",
            (ids["dialogue"],),
        )

    issues = service.validate()
    issue = next(
        item
        for item in issues
        if item.code == "ACTIVE_EPISODE_WITHOUT_ACTIVE_DIALOGUES"
    )
    assert issue.severity == "ERROR"


def test_two_backups_with_identical_timestamp_do_not_overwrite(tmp_path, monkeypatch):
    database = Database(tmp_path / "project.db")
    _seed_characterless_dialogue(database)
    service = DataService(database)

    fixed = real_datetime(2026, 8, 24, 16, 29, 38, 123456)

    class FixedDateTime:
        @classmethod
        def now(cls):
            return fixed

    monkeypatch.setattr(backup_service_module, "datetime", FixedDateTime)

    first = service.backup_database()
    second = service.backup_database()

    assert first != second
    assert first.exists()
    assert second.exists()
    assert first.name == "project_manual_20260824_162938_123456.smproj"
    assert second.name == "project_manual_20260824_162938_123456_1.smproj"
