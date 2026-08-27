from __future__ import annotations

from pathlib import Path

from core.database import Database, SCHEMA_VERSION
from import_engine.parser import (
    CastPair,
    ColumnLayout,
    ParsedDialogueRow,
    ScriptParseResult,
)
from import_engine.scanner import ScannedSourceFile, SourceScanResult
from import_engine.synchronizer import DialogueSynchronizer
from services.data_service import DataService
from services.tracking_service import TrackingService


def _layout() -> ColumnLayout:
    return ColumnLayout(
        sheet_name="Script",
        header_row=1,
        start_row=2,
        in_column=1,
        out_column=2,
        dialogue_column=3,
        character_column=4,
        talent_column=5,
        detection="test",
    )


def _row(
    *,
    uid: str,
    character: str,
    talents: tuple[str, ...] = (),
) -> ParsedDialogueRow:
    pairs = tuple(
        CastPair(character, talent)
        for talent in talents
    )
    return ParsedDialogueRow(
        source_row=2,
        time_in="00:00:01,000",
        time_out="00:00:02,000",
        dialogue="Test dialogue",
        raw_character=character,
        raw_talent=", ".join(talents),
        characters=(character,),
        talents=talents,
        cast_pairs=pairs,
        dialog_uid=uid,
        status="OK",
    )


def _sync(
    database: Database,
    tmp_path: Path,
    *,
    episode: int,
    row: ParsedDialogueRow,
    fingerprint: str = "fp",
) -> None:
    source_path = tmp_path / f"EP{episode}.xlsx"
    scan = SourceScanResult(
        source_folder=str(tmp_path),
        files=[
            ScannedSourceFile(
                file_path=str(source_path),
                file_name=source_path.name,
                episode_number=episode,
                episode_raw=str(episode),
                file_size=100,
                modified_at="2026-08-27T14:00:00",
                fingerprint=fingerprint,
            )
        ],
    )
    parse = ScriptParseResult(
        file_path=str(source_path),
        file_name=source_path.name,
        episode_number=episode,
        layout=_layout(),
        rows=[row],
    )
    DialogueSynchronizer().synchronize(
        database=database,
        scan=scan,
        parse_results={str(source_path): parse},
        synced_at="2026-08-27T14:00:00",
    )


def _cast_rows(database: Database) -> list[tuple[str, str | None]]:
    with database.connect() as connection:
        rows = connection.execute(
            """
            SELECT
                c.name AS character_name,
                t.name AS talent_name
            FROM dialog_cast AS dc
            JOIN characters AS c ON c.id = dc.character_id
            LEFT JOIN talents AS t ON t.id = dc.talent_id
            ORDER BY dc.position, dc.id
            """
        ).fetchall()
    return [
        (
            str(row["character_name"]),
            str(row["talent_name"]) if row["talent_name"] is not None else None,
        )
        for row in rows
    ]


def _character_id(database: Database, name: str) -> int:
    with database.connect() as connection:
        row = connection.execute(
            """
            SELECT id
            FROM characters
            WHERE LOWER(name) = LOWER(?)
            ORDER BY id
            LIMIT 1
            """,
            (name,),
        ).fetchone()
    assert row is not None
    return int(row["id"])


def test_schema_v8_contains_source_cast_provenance_table(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()

    with database.connect() as connection:
        table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'dialog_source_cast'
            """
        ).fetchone()
        version = connection.execute(
            "SELECT value FROM app_meta WHERE key = 'schema_version'"
        ).fetchone()["value"]

    assert SCHEMA_VERSION >= 8
    assert table is not None
    assert str(version) == str(SCHEMA_VERSION)


def test_unlock_crowded_restores_unresolved_and_removes_brama_tracking(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    _sync(
        database,
        tmp_path,
        episode=46,
        row=_row(
            uid="crowded-unresolved",
            character="Crowded",
            talents=(),
        ),
    )

    character_id = _character_id(database, "Crowded")
    data = DataService(database)
    brama_id = data.ensure_talent("Brama")

    with database.connect() as connection:
        source = connection.execute(
            """
            SELECT talent_id
            FROM dialog_source_cast
            WHERE character_id = ?
            """,
            (character_id,),
        ).fetchone()
    assert source is not None
    assert source["talent_id"] is None

    data.set_locked_mapping(character_id, brama_id)
    assert _cast_rows(database) == [("Crowded", "Brama")]

    tracking = TrackingService(database)
    assert any(
        talent.id == brama_id
        for talent in tracking.get_talents()
    )

    data.unlock_mapping(character_id)

    assert _cast_rows(database) == [("Crowded", None)]
    assert not any(
        talent.id == brama_id
        for talent in TrackingService(database).get_talents()
    )

    unresolved = data.get_unresolved_cast()
    assert len(unresolved) == 1
    assert unresolved[0].character_id == character_id


def test_unlock_restores_explicit_source_talent(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    _sync(
        database,
        tmp_path,
        episode=87,
        row=_row(
            uid="blue-shirt",
            character="Bapak kemeja biru",
            talents=("Vega",),
        ),
    )

    character_id = _character_id(database, "Bapak kemeja biru")
    data = DataService(database)
    brama_id = data.ensure_talent("Brama")

    assert _cast_rows(database) == [("Bapak kemeja biru", "Vega")]

    data.set_locked_mapping(character_id, brama_id)
    assert _cast_rows(database) == [("Bapak kemeja biru", "Brama")]

    data.unlock_mapping(character_id)
    assert _cast_rows(database) == [("Bapak kemeja biru", "Vega")]


def test_unlock_restores_all_source_multitalent_rows(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    _sync(
        database,
        tmp_path,
        episode=44,
        row=_row(
            uid="crowded-multi",
            character="Crowded Anak kecil",
            talents=("Anisa", "Fitri", "Anggraini"),
        ),
    )

    character_id = _character_id(database, "Crowded Anak kecil")
    data = DataService(database)
    brama_id = data.ensure_talent("Brama")

    assert _cast_rows(database) == [
        ("Crowded Anak kecil", "Anisa"),
        ("Crowded Anak kecil", "Fitri"),
        ("Crowded Anak kecil", "Anggraini"),
    ]

    data.set_locked_mapping(character_id, brama_id)
    assert _cast_rows(database) == [
        ("Crowded Anak kecil", "Brama")
    ]

    data.unlock_mapping(character_id)
    assert _cast_rows(database) == [
        ("Crowded Anak kecil", "Anisa"),
        ("Crowded Anak kecil", "Fitri"),
        ("Crowded Anak kecil", "Anggraini"),
    ]


def test_unlock_without_v8_provenance_uses_conservative_identity_fallback(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    _sync(
        database,
        tmp_path,
        episode=53,
        row=_row(
            uid="fallback-unresolved",
            character="Crowded",
            talents=(),
        ),
    )

    character_id = _character_id(database, "Crowded")
    data = DataService(database)
    brama_id = data.ensure_talent("Brama")
    data.set_locked_mapping(character_id, brama_id)

    with database.connect() as connection:
        connection.execute(
            "DELETE FROM dialog_source_cast"
        )

    data.unlock_mapping(character_id)
    assert _cast_rows(database) == [("Crowded", None)]
