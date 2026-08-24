from __future__ import annotations

import sqlite3

from core.database import Database, SCHEMA_VERSION
from services.data_service import DataService


def _seed(database: Database) -> dict[str, int]:
    database.initialize()

    with database.connect() as connection:
        source_id = connection.execute(
            """
            INSERT INTO source_files(
                file_path, file_name, episode_number,
                fingerprint, is_active, imported_at, last_seen_at
            ) VALUES(
                'ep1.xlsx', 'ep1.xlsx', 1,
                'abc', 1, '2026-08-24T10:00:00', '2026-08-24T10:00:00'
            )
            """
        ).lastrowid

        episode_id = connection.execute(
            """
            INSERT INTO episodes(
                episode_number, source_file_id, title, is_active
            ) VALUES(1, ?, 'EP 1', 1)
            """,
            (source_id,),
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

        dialogue_1 = connection.execute(
            """
            INSERT INTO dialogues(
                dialog_uid, episode_id, source_file_id,
                time_in, time_out, dialog_text, source_row, is_active
            ) VALUES(
                'uid-1', ?, ?, '00:00:01,000', '00:00:03,000',
                'Dialog Hendra', 3, 1
            )
            """,
            (episode_id, source_id),
        ).lastrowid
        dialogue_2 = connection.execute(
            """
            INSERT INTO dialogues(
                dialog_uid, episode_id, source_file_id,
                time_in, time_out, dialog_text, source_row, is_active
            ) VALUES(
                'uid-2', ?, ?, '00:00:04,000', '00:00:06,000',
                'Dialog Joko', 4, 1
            )
            """,
            (episode_id, source_id),
        ).lastrowid

        connection.execute(
            """
            INSERT INTO dialog_cast(
                dialogue_id, character_id, talent_id, position
            ) VALUES(?, ?, NULL, 0)
            """,
            (dialogue_1, hendra),
        )
        connection.execute(
            """
            INSERT INTO dialog_cast(
                dialogue_id, character_id, talent_id, position
            ) VALUES(?, ?, ?, 0)
            """,
            (dialogue_2, joko, brama),
        )

        connection.execute(
            """
            INSERT INTO recording_status(
                dialogue_id, is_recorded, recorded_at, updated_at
            ) VALUES(?, 1, '2026-08-24T10:10:00', '2026-08-24T10:10:00')
            """,
            (dialogue_1,),
        )

    return {
        'source': int(source_id),
        'episode': int(episode_id),
        'hendra': int(hendra),
        'joko': int(joko),
        'brama': int(brama),
        'dialogue_1': int(dialogue_1),
        'dialogue_2': int(dialogue_2),
    }


def test_overview_and_unresolved_rows(tmp_path):
    database = Database(tmp_path / 'project.db')
    ids = _seed(database)
    service = DataService(database)

    overview = service.get_overview()
    assert overview.active_sources == 1
    assert overview.active_dialogues == 2
    assert overview.active_characters == 2
    assert overview.active_talents == 1
    assert overview.unresolved_cast == 1

    unresolved = service.get_unresolved_cast()
    assert len(unresolved) == 1
    assert unresolved[0].character_id == ids['hendra']
    assert unresolved[0].episode_number == 1


def test_manual_lock_updates_active_cast_and_preserves_recording(tmp_path):
    database = Database(tmp_path / 'project.db')
    ids = _seed(database)
    service = DataService(database)

    service.set_locked_mapping(ids['hendra'], ids['brama'])

    with database.connect() as connection:
        mapping = connection.execute(
            """
            SELECT talent_id, is_locked, source
            FROM character_talent
            WHERE character_id = ? AND is_locked = 1
            """,
            (ids['hendra'],),
        ).fetchone()
        cast = connection.execute(
            """
            SELECT talent_id
            FROM dialog_cast
            WHERE dialogue_id = ? AND character_id = ?
            """,
            (ids['dialogue_1'], ids['hendra']),
        ).fetchone()
        recording = connection.execute(
            """
            SELECT is_recorded
            FROM recording_status
            WHERE dialogue_id = ?
            """,
            (ids['dialogue_1'],),
        ).fetchone()

    assert int(mapping['talent_id']) == ids['brama']
    assert int(mapping['is_locked']) == 1
    assert mapping['source'] == 'manual'
    assert int(cast['talent_id']) == ids['brama']
    assert int(recording['is_recorded']) == 1
    assert service.get_overview().unresolved_cast == 0


def test_unlock_removes_lock_but_keeps_current_cast(tmp_path):
    database = Database(tmp_path / 'project.db')
    ids = _seed(database)
    service = DataService(database)

    service.set_locked_mapping(ids['hendra'], ids['brama'])
    service.unlock_mapping(ids['hendra'])

    with database.connect() as connection:
        locked = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM character_talent
            WHERE character_id = ? AND is_locked = 1
            """,
            (ids['hendra'],),
        ).fetchone()
        cast = connection.execute(
            """
            SELECT talent_id
            FROM dialog_cast
            WHERE dialogue_id = ? AND character_id = ?
            """,
            (ids['dialogue_1'], ids['hendra']),
        ).fetchone()

    assert int(locked['total']) == 0
    assert int(cast['talent_id']) == ids['brama']


def test_ensure_talent_reuses_normalized_name(tmp_path):
    database = Database(tmp_path / 'project.db')
    _seed(database)
    service = DataService(database)

    first = service.ensure_talent('Sari')
    second = service.ensure_talent('  SARI  ')

    assert first == second
    names = dict(service.get_talent_options())
    assert names[first] == 'SARI'


def test_validation_reports_unresolved_then_clears_after_mapping(tmp_path):
    database = Database(tmp_path / 'project.db')
    ids = _seed(database)
    service = DataService(database)

    issues = service.validate()
    assert any(issue.code == 'UNRESOLVED_CAST' for issue in issues)

    service.set_locked_mapping(ids['hendra'], ids['brama'])
    issues = service.validate()
    assert not any(issue.code == 'UNRESOLVED_CAST' for issue in issues)
    assert not any(issue.severity == 'ERROR' for issue in issues)


def test_backup_is_valid_sqlite_copy(tmp_path):
    database = Database(tmp_path / 'project.db')
    _seed(database)
    service = DataService(database)

    backup_path = service.backup_database()

    assert backup_path.exists()
    assert backup_path.parent.name == 'backups'

    connection = sqlite3.connect(backup_path)
    try:
        count = connection.execute('SELECT COUNT(*) FROM dialogues').fetchone()[0]
        schema = connection.execute(
            "SELECT value FROM app_meta WHERE key = 'schema_version'"
        ).fetchone()[0]
    finally:
        connection.close()

    assert count == 2
    assert schema == str(SCHEMA_VERSION)
