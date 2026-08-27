from __future__ import annotations

from core.database import Database, SCHEMA_VERSION
from import_engine.parser import CastPair, ParsedDialogueRow
from import_engine.resolver import CharacterTalentResolver
from services.character_alias_service import CharacterAliasService


def _seed_character(connection, name: str, normalized: str) -> int:
    cursor = connection.execute(
        """
        INSERT INTO characters(name, normalized_name, is_active, created_at, updated_at)
        VALUES(?, ?, 1, 't', 't')
        """,
        (name, normalized),
    )
    return int(cursor.lastrowid)


def _seed_talent(connection, name: str, normalized: str) -> int:
    cursor = connection.execute(
        """
        INSERT INTO talents(name, normalized_name, is_active, created_at, updated_at)
        VALUES(?, ?, 1, 't', 't')
        """,
        (name, normalized),
    )
    return int(cursor.lastrowid)


def _seed_dialogue(connection, character_id: int, talent_id: int) -> tuple[int, int]:
    source = connection.execute(
        """
        INSERT INTO source_files(file_path, file_name, episode_number, is_active)
        VALUES('x.xlsx', 'x.xlsx', 1, 1)
        """
    )
    source_id = int(source.lastrowid)
    episode = connection.execute(
        """
        INSERT INTO episodes(episode_number, source_file_id, title, is_active)
        VALUES(1, ?, 'Episode 1', 1)
        """,
        (source_id,),
    )
    episode_id = int(episode.lastrowid)
    dialogue = connection.execute(
        """
        INSERT INTO dialogues(
            dialog_uid, episode_id, source_file_id, time_in, time_out,
            dialog_text, source_row, is_active, created_at, updated_at
        ) VALUES('uid-1', ?, ?, '00:00:01,000', '00:00:02,000', 'Halo', 3, 1, 't', 't')
        """,
        (episode_id, source_id),
    )
    dialogue_id = int(dialogue.lastrowid)
    connection.execute(
        """
        INSERT INTO dialog_cast(dialogue_id, character_id, talent_id, position)
        VALUES(?, ?, ?, 0)
        """,
        (dialogue_id, character_id, talent_id),
    )
    connection.execute(
        """
        INSERT INTO recording_status(dialogue_id, is_recorded, recorded_at, updated_at)
        VALUES(?, 1, 't', 't')
        """,
        (dialogue_id,),
    )
    connection.execute(
        """
        INSERT INTO stem_status(episode_id, talent_id, character_id, status, updated_at)
        VALUES(?, ?, ?, 'DELIVERED', 't')
        """,
        (episode_id, talent_id, character_id),
    )
    return dialogue_id, episode_id


def test_current_schema_contains_character_alias_tables(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()

    assert SCHEMA_VERSION >= 5
    with database.connect() as connection:
        names = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert "character_alias" in names
        assert "character_alias_dialogue" in names
        version = connection.execute(
            "SELECT value FROM app_meta WHERE key = 'schema_version'"
        ).fetchone()
        assert str(version["value"]) == str(SCHEMA_VERSION)


def test_existing_character_can_be_aliased_and_restored_without_losing_recording(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()

    with database.connect() as connection:
        andi_id = _seed_character(connection, "Andi", "andi")
        alias_character_id = _seed_character(
            connection, "Bapak jas navy", "bapak jas navy"
        )
        brama_id = _seed_talent(connection, "Brama", "brama")
        dialogue_id, _ = _seed_dialogue(connection, alias_character_id, brama_id)

    service = CharacterAliasService(database)
    alias_id = service.set_character_alias(alias_character_id, andi_id)

    with database.connect() as connection:
        source = connection.execute(
            "SELECT is_active FROM characters WHERE id = ?",
            (alias_character_id,),
        ).fetchone()
        assert int(source["is_active"]) == 0

        cast = connection.execute(
            "SELECT character_id, talent_id FROM dialog_cast WHERE dialogue_id = ?",
            (dialogue_id,),
        ).fetchone()
        assert int(cast["character_id"]) == andi_id
        assert int(cast["talent_id"]) == brama_id

        recorded = connection.execute(
            "SELECT is_recorded FROM recording_status WHERE dialogue_id = ?",
            (dialogue_id,),
        ).fetchone()
        assert int(recorded["is_recorded"]) == 1

        # Identity changes invalidate downstream tracking rather than guessing.
        assert connection.execute("SELECT COUNT(*) FROM stem_status").fetchone()[0] == 0

        provenance = connection.execute(
            "SELECT alias_id FROM character_alias_dialogue WHERE dialogue_id = ?",
            (dialogue_id,),
        ).fetchone()
        assert int(provenance["alias_id"]) == alias_id

    service.remove_alias(alias_id)

    with database.connect() as connection:
        source = connection.execute(
            "SELECT is_active FROM characters WHERE id = ?",
            (alias_character_id,),
        ).fetchone()
        assert int(source["is_active"]) == 1
        cast = connection.execute(
            "SELECT character_id FROM dialog_cast WHERE dialogue_id = ?",
            (dialogue_id,),
        ).fetchone()
        assert int(cast["character_id"]) == alias_character_id
        assert connection.execute("SELECT COUNT(*) FROM character_alias").fetchone()[0] == 0
        recorded = connection.execute(
            "SELECT is_recorded FROM recording_status WHERE dialogue_id = ?",
            (dialogue_id,),
        ).fetchone()
        assert int(recorded["is_recorded"]) == 1


def test_resolver_uses_alias_before_creating_character(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    with database.connect() as connection:
        andi_id = _seed_character(connection, "Andi", "andi")

    service = CharacterAliasService(database)
    alias_id = service.add_alias_name(andi_id, "Bapak jas navy")

    with database.connect() as connection:
        resolver = CharacterTalentResolver(connection)
        row = ParsedDialogueRow(
            source_row=3,
            time_in="00:00:01,000",
            time_out="00:00:02,000",
            dialogue="Halo",
            raw_character="Bapak jas navy",
            raw_talent="Brama",
            characters=("Bapak jas navy",),
            talents=("Brama",),
            cast_pairs=(CastPair("Bapak jas navy", "Brama"),),
            dialog_uid="uid-x",
            status="OK",
        )
        cast, warnings = resolver.resolve_row(row, timestamp="now")
        assert warnings == []
        assert len(cast) == 1
        assert cast[0].character_id == andi_id
        assert cast[0].character_name == "Andi"
        assert cast[0].alias_ids == (alias_id,)

        created = connection.execute(
            "SELECT COUNT(*) FROM characters WHERE normalized_name = 'bapak jas navy'"
        ).fetchone()[0]
        assert created == 0


def test_alias_rejects_conflicting_locked_talents(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    with database.connect() as connection:
        andi_id = _seed_character(connection, "Andi", "andi")
        navy_id = _seed_character(connection, "Bapak jas navy", "bapak jas navy")
        brama = _seed_talent(connection, "Brama", "brama")
        vega = _seed_talent(connection, "Vega", "vega")
        connection.execute(
            "INSERT INTO character_talent(character_id, talent_id, is_locked, source) VALUES(?, ?, 1, 'manual')",
            (andi_id, brama),
        )
        connection.execute(
            "INSERT INTO character_talent(character_id, talent_id, is_locked, source) VALUES(?, ?, 1, 'manual')",
            (navy_id, vega),
        )

    service = CharacterAliasService(database)
    try:
        service.set_character_alias(navy_id, andi_id)
    except ValueError as exc:
        assert "locked talent yang berbeda" in str(exc)
    else:
        raise AssertionError("conflicting locked talent should reject alias")
