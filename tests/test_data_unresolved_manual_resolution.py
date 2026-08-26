from __future__ import annotations

from core.database import Database
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
                'ep53.xlsx', 'ep53.xlsx', 53,
                'ep53', 1, '2026-08-26T08:00:00', '2026-08-26T08:00:00'
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

        hendra = connection.execute(
            """
            INSERT INTO characters(name, normalized_name, is_active)
            VALUES('Hendra', 'hendra', 1)
            """
        ).lastrowid

        narration = connection.execute(
            """
            INSERT INTO dialogues(
                dialog_uid, episode_id, source_file_id,
                time_in, time_out, dialog_text, source_row, is_active
            ) VALUES(
                'uid-narration', ?, ?, '00:00:01,000', '00:00:03,000',
                'Setengah bulan kemudian', 16, 1
            )
            """,
            (episode_id, source_id),
        ).lastrowid

        unresolved_talent = connection.execute(
            """
            INSERT INTO dialogues(
                dialog_uid, episode_id, source_file_id,
                time_in, time_out, dialog_text, source_row, is_active
            ) VALUES(
                'uid-hendra', ?, ?, '00:00:04,000', '00:00:05,000',
                'Dialog Hendra', 17, 1
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
            (unresolved_talent, hendra),
        )

    return {
        "narration": int(narration),
        "hendra": int(hendra),
    }


def test_missing_character_is_visible_and_kept_manual(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed(database)
    service = DataService(database)

    rows = service.get_unresolved_cast()
    assert len(rows) == 2
    assert rows[0].dialogue_id == ids["narration"]
    assert rows[0].character_id is None
    assert rows[0].character_name == "⚠ Missing Character"
    assert rows[0].talent_id is None
    assert rows[0].talent_name == "⚠ Missing Talent"
    assert rows[0].dialogue == "Setengah bulan kemudian"
    assert rows[0].source_file_name == "ep53.xlsx"
    assert rows[0].source_file_path == "ep53.xlsx"

    characters = service.get_characters()
    assert characters[0].id is None
    assert characters[0].missing_character is True
    assert characters[0].name == "⚠ Character Unknown"
    assert characters[0].locked_talent_name == "⚠ Talent Unknown"
    assert characters[0].unresolved_dialogues == 1

    codes = {issue.code for issue in service.validate()}
    assert "ACTIVE_DIALOGUE_NO_CAST" in codes
    assert "UNRESOLVED_CAST" in codes


def test_manual_character_then_talent_resolution_updates_health_and_sorting(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed(database)
    service = DataService(database)

    narrator_id = service.ensure_character("Narator")
    service.assign_missing_character(ids["narration"], narrator_id)

    unresolved = service.get_unresolved_cast()
    narration = next(row for row in unresolved if row.dialogue_id == ids["narration"])
    assert narration.character_id == narrator_id
    assert narration.character_name == "Narator"
    assert narration.talent_id is None

    characters = service.get_characters()
    assert not any(row.missing_character for row in characters)
    unresolved_names = [
        row.name for row in characters if row.unresolved_dialogues
    ]
    assert unresolved_names == ["Hendra", "Narator"]

    codes = {issue.code for issue in service.validate()}
    assert "ACTIVE_DIALOGUE_NO_CAST" not in codes
    assert "UNRESOLVED_CAST" in codes

    talent_id = service.ensure_talent("Brama")
    service.set_locked_mapping(narrator_id, talent_id)
    service.set_locked_mapping(ids["hendra"], talent_id)

    assert service.get_overview().unresolved_cast == 0
    assert service.get_unresolved_cast() == []

    characters = service.get_characters()
    assert [row.name for row in characters] == ["Hendra", "Narator"]
    assert all(row.unresolved_dialogues == 0 for row in characters)

    codes = {issue.code for issue in service.validate()}
    assert "ACTIVE_DIALOGUE_NO_CAST" not in codes
    assert "UNRESOLVED_CAST" not in codes


def test_assign_missing_character_refuses_dialogue_that_already_has_cast(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed(database)
    service = DataService(database)

    other_character = service.ensure_character("Andi")

    try:
        with database.connect() as connection:
            dialogue_id = int(
                connection.execute(
                    "SELECT dialogue_id FROM dialog_cast WHERE character_id = ?",
                    (ids["hendra"],),
                ).fetchone()["dialogue_id"]
            )
        service.assign_missing_character(dialogue_id, other_character)
    except ValueError as exc:
        assert "sudah memiliki character/cast" in str(exc)
    else:
        raise AssertionError("assign_missing_character must not duplicate an existing cast")
