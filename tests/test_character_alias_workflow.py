from __future__ import annotations

from core.database import Database, SCHEMA_VERSION
from import_engine.parser import CastPair, ColumnLayout, ParsedDialogueRow, ScriptParseResult
from import_engine.resolver import CharacterTalentResolver
from services.alias_service import CharacterAliasService
from services.data_service import DataService
from services.dialogue_service import DialogueService
from services.recording_service import RecordingService
from services.tracking_service import TrackingService


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

        andi = connection.execute(
            "INSERT INTO characters(name, normalized_name, is_active) VALUES('Andi', 'andi', 1)"
        ).lastrowid
        navy = connection.execute(
            "INSERT INTO characters(name, normalized_name, is_active) VALUES('Bapak jas navy', 'bapak jas navy', 1)"
        ).lastrowid
        brama = connection.execute(
            "INSERT INTO talents(name, normalized_name, is_active) VALUES('Brama', 'brama', 1)"
        ).lastrowid
        vega = connection.execute(
            "INSERT INTO talents(name, normalized_name, is_active) VALUES('Vega', 'vega', 1)"
        ).lastrowid

        d1 = connection.execute(
            """
            INSERT INTO dialogues(
                dialog_uid, episode_id, source_file_id, time_in, time_out,
                dialog_text, source_row, is_active
            ) VALUES('alias-d1', ?, ?, '00:00:01,000', '00:00:02,000', 'Andi source', 3, 1)
            """,
            (ep1, source1),
        ).lastrowid
        d2 = connection.execute(
            """
            INSERT INTO dialogues(
                dialog_uid, episode_id, source_file_id, time_in, time_out,
                dialog_text, source_row, is_active
            ) VALUES('alias-d2', ?, ?, '00:00:03,000', '00:00:04,000', 'Navy source', 3, 1)
            """,
            (ep2, source2),
        ).lastrowid
        connection.executemany(
            "INSERT INTO dialog_cast(dialogue_id, character_id, talent_id, position) VALUES(?, ?, ?, 0)",
            [(d1, andi, brama), (d2, navy, brama)],
        )
        connection.execute(
            "INSERT INTO recording_status(dialogue_id, is_recorded) VALUES(?, 1)",
            (d2,),
        )
        connection.execute(
            "INSERT INTO stem_status(episode_id, talent_id, character_id, status) VALUES(?, ?, ?, 'STEMMED')",
            (ep1, brama, andi),
        )
        connection.execute(
            "INSERT INTO stem_status(episode_id, talent_id, character_id, status) VALUES(?, ?, ?, 'DELIVERED')",
            (ep2, brama, navy),
        )

    return {
        "ep1": int(ep1),
        "ep2": int(ep2),
        "andi": int(andi),
        "navy": int(navy),
        "brama": int(brama),
        "vega": int(vega),
        "d1": int(d1),
        "d2": int(d2),
    }


def test_alias_keeps_source_identity_but_canonicalizes_dialog_and_tracking(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed(database)

    alias_service = CharacterAliasService(database)
    alias_id = alias_service.set_alias(
        source_character_id=ids["navy"],
        canonical_character_id=ids["andi"],
    )

    with database.connect() as connection:
        cast = connection.execute(
            "SELECT dialogue_id, character_id FROM dialog_cast ORDER BY dialogue_id"
        ).fetchall()
        recording = connection.execute(
            "SELECT is_recorded FROM recording_status WHERE dialogue_id = ?",
            (ids["d2"],),
        ).fetchone()
        stems = connection.execute("SELECT COUNT(*) AS total FROM stem_status").fetchone()

    assert [(int(row["dialogue_id"]), int(row["character_id"])) for row in cast] == [
        (ids["d1"], ids["andi"]),
        (ids["d2"], ids["navy"]),
    ]
    assert int(recording["is_recorded"]) == 1
    assert int(stems["total"]) == 0

    # SCRIPT remains a faithful view of the labels actually supplied by client.
    script_rows = DialogueService(database).get_script_rows()
    assert script_rows[0].characters == ("Andi",)
    assert script_rows[1].characters == ("Bapak jas navy",)

    # DIALOG presents one canonical character and combines both source labels.
    recording_service = RecordingService(database)
    assert [
        (item.id, item.name)
        for item in recording_service.get_characters_for_talent(ids["brama"])
    ] == [(ids["andi"], "Andi")]
    assert [
        item.episode_number
        for item in recording_service.get_episodes_for_cast(
            talent_id=ids["brama"],
            character_id=ids["andi"],
        )
    ] == [1, 2]
    assert [
        row.dialogue
        for episode in (1, 2)
        for row in recording_service.get_dialogues(
            talent_id=ids["brama"],
            character_id=ids["andi"],
            episode_number=episode,
        )
    ] == ["Andi source", "Navy source"]

    # TRACKING also collapses both labels under canonical Andi.
    tracking_rows = TrackingService(database).get_character_rows(ids["brama"])
    assert len(tracking_rows) == 1
    assert tracking_rows[0].character_id == ids["andi"]
    assert tracking_rows[0].character_name == "Andi"
    assert [chip.episode_number for chip in tracking_rows[0].chips] == [1, 2]

    # DATA master list shows canonical once and exposes the source alias.
    admin_rows = [row for row in DataService(database).get_characters() if row.id is not None]
    assert [(row.name, row.aliases, row.active_dialogues) for row in admin_rows] == [
        ("Andi", ("Bapak jas navy",), 2)
    ]

    alias_service.restore_alias(alias_id)
    restored = [row.name for row in DataService(database).get_characters() if row.id is not None]
    assert restored == ["Andi", "Bapak jas navy"]
    with database.connect() as connection:
        recording = connection.execute(
            "SELECT is_recorded FROM recording_status WHERE dialogue_id = ?",
            (ids["d2"],),
        ).fetchone()
    assert int(recording["is_recorded"]) == 1


def _parsed_row(character: str, talent: str, uid: str) -> ParsedDialogueRow:
    return ParsedDialogueRow(
        source_row=3,
        time_in="00:00:01,000",
        time_out="00:00:02,000",
        dialogue=uid,
        raw_character=character,
        raw_talent=talent,
        characters=(character,),
        talents=(talent,),
        cast_pairs=(CastPair(character=character, talent=talent),),
        dialog_uid=uid,
        status="OK",
    )


def _parse_result(rows: list[ParsedDialogueRow]) -> ScriptParseResult:
    return ScriptParseResult(
        file_path="ep1.xlsx",
        file_name="ep1.xlsx",
        episode_number=1,
        layout=ColumnLayout(
            sheet_name="Sheet1",
            header_row=2,
            start_row=3,
            in_column=1,
            out_column=2,
            dialogue_column=3,
            character_column=4,
            talent_column=5,
        ),
        rows=rows,
    )


def test_resolver_uses_canonical_lock_but_preserves_source_character_id(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed(database)
    alias_service = CharacterAliasService(database)
    alias_service.set_alias(
        source_character_id=ids["navy"],
        canonical_character_id=ids["andi"],
    )

    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO character_talent(character_id, talent_id, is_locked, source)
            VALUES(?, ?, 1, 'manual')
            """,
            (ids["andi"], ids["brama"]),
        )
        resolver = CharacterTalentResolver(connection)
        members, warnings = resolver.resolve_row(
            _parsed_row("Bapak jas navy", "Vega", "resolver-alias"),
            timestamp="2026-08-26T12:00:00",
        )

    assert len(members) == 1
    assert members[0].character_id == ids["navy"]
    assert members[0].character_name == "Bapak jas navy"
    assert members[0].talent_id == ids["brama"]
    assert members[0].talent_name == "Brama"
    assert members[0].source == "locked"
    assert warnings


def test_alias_conflicting_single_row_evidence_does_not_auto_lock(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed(database)
    CharacterAliasService(database).set_alias(
        source_character_id=ids["navy"],
        canonical_character_id=ids["andi"],
    )

    result = _parse_result(
        [
            _parsed_row("Andi", "Brama", "learn-1"),
            _parsed_row("Bapak jas navy", "Vega", "learn-2"),
        ]
    )
    with database.connect() as connection:
        resolver = CharacterTalentResolver(connection)
        report = resolver.learn_from_single_rows(
            [result], timestamp="2026-08-26T12:00:00"
        )
        locked = connection.execute(
            "SELECT COUNT(*) AS total FROM character_talent WHERE character_id = ? AND is_locked = 1",
            (ids["andi"],),
        ).fetchone()

    assert report.auto_locked == 0
    assert int(locked["total"]) == 0
    assert any("lebih dari satu talent" in warning for warning in report.warnings)


def test_schema_v5_migrates_existing_v4_database_without_losing_data(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed(database)
    with database.connect() as connection:
        connection.execute("DROP TABLE character_alias")
        connection.execute(
            "UPDATE app_meta SET value = '4' WHERE key = 'schema_version'"
        )

    database.initialize()
    with database.connect() as connection:
        version = connection.execute(
            "SELECT value FROM app_meta WHERE key = 'schema_version'"
        ).fetchone()
        alias_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'character_alias'"
        ).fetchone()
        dialogue_count = connection.execute(
            "SELECT COUNT(*) AS total FROM dialogues"
        ).fetchone()

    assert SCHEMA_VERSION == 5
    assert str(version["value"]) == "5"
    assert alias_table is not None
    assert int(dialogue_count["total"]) == 2
    assert ids["d1"] > 0
