from __future__ import annotations

import sqlite3
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


def _source(
    path: Path,
    *,
    episode: int,
    fingerprint: str,
) -> ScannedSourceFile:
    return ScannedSourceFile(
        file_path=str(path),
        file_name=path.name,
        episode_number=episode,
        episode_raw=str(episode),
        file_size=100,
        modified_at="2026-08-27T10:00:00",
        fingerprint=fingerprint,
    )


def _row(
    *,
    uid: str,
    character: str,
    talent: str,
    source_row: int = 2,
) -> ParsedDialogueRow:
    return ParsedDialogueRow(
        source_row=source_row,
        time_in="00:00:01,000",
        time_out="00:00:02,000",
        dialogue=f"Dialog {uid}",
        raw_character=character,
        raw_talent=talent,
        characters=(character,),
        talents=(talent,),
        cast_pairs=(CastPair(character, talent),),
        dialog_uid=uid,
        status="OK",
    )


def _parse(
    path: Path,
    *,
    episode: int,
    character: str,
    talent: str,
    uid: str,
) -> ScriptParseResult:
    return ScriptParseResult(
        file_path=str(path),
        file_name=path.name,
        episode_number=episode,
        layout=_layout(),
        rows=[
            _row(
                uid=uid,
                character=character,
                talent=talent,
            )
        ],
    )


def _initial_sync(database: Database, tmp_path: Path):
    ep16 = tmp_path / "AA23-第16集_中文.xlsx"
    ep87 = tmp_path / "AA23-第87集_中文.xlsx"

    scan = SourceScanResult(
        source_folder=str(tmp_path),
        files=[
            _source(ep16, episode=16, fingerprint="fp16"),
            _source(ep87, episode=87, fingerprint="fp87"),
        ],
    )
    parses = {
        str(ep16): _parse(
            ep16,
            episode=16,
            character="Bapak Kemeja Biru",
            talent="Brama",
            uid="ep16-blue-shirt",
        ),
        str(ep87): _parse(
            ep87,
            episode=87,
            character="Bapak kemeja biru",
            talent="Vega",
            uid="ep87-blue-shirt",
        ),
    }
    DialogueSynchronizer().synchronize(
        database=database,
        scan=scan,
        parse_results=parses,
        synced_at="2026-08-27T10:00:00",
    )
    return ep16, ep87


def test_same_normalized_character_with_different_source_talents_is_split(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    _initial_sync(database, tmp_path)

    with database.connect() as connection:
        characters = connection.execute(
            """
            SELECT
                c.id,
                c.name,
                c.base_normalized_name,
                c.identity_talent_id,
                t.name AS identity_talent_name,
                lm.talent_id AS locked_talent_id,
                lt.name AS locked_talent_name
            FROM characters AS c
            LEFT JOIN talents AS t
              ON t.id = c.identity_talent_id
            LEFT JOIN character_talent AS lm
              ON lm.character_id = c.id
             AND lm.is_locked = 1
            LEFT JOIN talents AS lt
              ON lt.id = lm.talent_id
            WHERE COALESCE(
                NULLIF(c.base_normalized_name, ''),
                c.normalized_name
            ) = 'bapak kemeja biru'
            ORDER BY c.id
            """
        ).fetchall()

        casts = connection.execute(
            """
            SELECT
                e.episode_number,
                dc.character_id,
                t.name AS talent_name
            FROM dialog_cast AS dc
            JOIN dialogues AS d ON d.id = dc.dialogue_id
            JOIN episodes AS e ON e.id = d.episode_id
            JOIN talents AS t ON t.id = dc.talent_id
            WHERE e.episode_number IN (16, 87)
            ORDER BY e.episode_number
            """
        ).fetchall()

    assert len(characters) == 2
    by_identity_talent = {
        str(row["identity_talent_name"]): row
        for row in characters
    }
    assert set(by_identity_talent) == {"Brama", "Vega"}
    assert str(by_identity_talent["Brama"]["locked_talent_name"]) == "Brama"
    assert str(by_identity_talent["Vega"]["locked_talent_name"]) == "Vega"

    assert len(casts) == 2
    assert int(casts[0]["episode_number"]) == 16
    assert str(casts[0]["talent_name"]) == "Brama"
    assert int(casts[0]["character_id"]) == int(
        by_identity_talent["Brama"]["id"]
    )

    assert int(casts[1]["episode_number"]) == 87
    assert str(casts[1]["talent_name"]) == "Vega"
    assert int(casts[1]["character_id"]) == int(
        by_identity_talent["Vega"]["id"]
    )


def test_source_talent_revision_moves_cast_to_existing_identity_on_refresh(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    ep16, ep87 = _initial_sync(database, tmp_path)

    with database.connect() as connection:
        ep87_dialogue = connection.execute(
            "SELECT id FROM dialogues WHERE dialog_uid = 'ep87-blue-shirt'"
        ).fetchone()
        connection.execute(
            """
            UPDATE recording_status
            SET is_recorded = 1,
                recorded_at = '2026-08-27T10:05:00',
                updated_at = '2026-08-27T10:05:00'
            WHERE dialogue_id = ?
            """,
            (int(ep87_dialogue["id"]),),
        )

        brama_character = connection.execute(
            """
            SELECT c.id
            FROM characters AS c
            JOIN talents AS t ON t.id = c.identity_talent_id
            WHERE COALESCE(
                NULLIF(c.base_normalized_name, ''),
                c.normalized_name
            ) = 'bapak kemeja biru'
              AND t.normalized_name = 'brama'
            """
        ).fetchone()

    scan = SourceScanResult(
        source_folder=str(tmp_path),
        files=[
            _source(ep16, episode=16, fingerprint="fp16"),
            _source(ep87, episode=87, fingerprint="fp87-revised"),
        ],
    )
    DialogueSynchronizer().synchronize(
        database=database,
        scan=scan,
        parse_results={
            str(ep87): _parse(
                ep87,
                episode=87,
                character="Bapak kemeja biru",
                talent="Brama",
                uid="ep87-blue-shirt",
            )
        },
        synced_at="2026-08-27T11:00:00",
    )

    with database.connect() as connection:
        cast = connection.execute(
            """
            SELECT dc.character_id, t.name AS talent_name
            FROM dialog_cast AS dc
            JOIN dialogues AS d ON d.id = dc.dialogue_id
            JOIN talents AS t ON t.id = dc.talent_id
            WHERE d.dialog_uid = 'ep87-blue-shirt'
            """
        ).fetchone()
        recording = connection.execute(
            """
            SELECT rs.is_recorded
            FROM recording_status AS rs
            JOIN dialogues AS d ON d.id = rs.dialogue_id
            WHERE d.dialog_uid = 'ep87-blue-shirt'
            """
        ).fetchone()

    assert int(cast["character_id"]) == int(brama_character["id"])
    assert str(cast["talent_name"]) == "Brama"
    assert int(recording["is_recorded"]) == 1


def test_manual_character_mapping_survives_refresh_for_same_source_identity(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    ep16, ep87 = _initial_sync(database, tmp_path)

    with database.connect() as connection:
        vega_character = connection.execute(
            """
            SELECT c.id
            FROM characters AS c
            JOIN talents AS t ON t.id = c.identity_talent_id
            WHERE COALESCE(
                NULLIF(c.base_normalized_name, ''),
                c.normalized_name
            ) = 'bapak kemeja biru'
              AND t.normalized_name = 'vega'
            """
        ).fetchone()
        brama = connection.execute(
            "SELECT id FROM talents WHERE normalized_name = 'brama'"
        ).fetchone()

    DataService(database).set_locked_mapping(
        int(vega_character["id"]),
        int(brama["id"]),
    )

    scan = SourceScanResult(
        source_folder=str(tmp_path),
        files=[
            _source(ep16, episode=16, fingerprint="fp16"),
            _source(ep87, episode=87, fingerprint="fp87-manual-refresh"),
        ],
    )
    report = DialogueSynchronizer().synchronize(
        database=database,
        scan=scan,
        parse_results={
            str(ep87): _parse(
                ep87,
                episode=87,
                character="Bapak kemeja biru",
                talent="Vega",
                uid="ep87-blue-shirt",
            )
        },
        synced_at="2026-08-27T12:00:00",
    )

    with database.connect() as connection:
        character = connection.execute(
            """
            SELECT identity_talent_id
            FROM characters
            WHERE id = ?
            """,
            (int(vega_character["id"]),),
        ).fetchone()
        identity_talent = connection.execute(
            "SELECT name FROM talents WHERE id = ?",
            (int(character["identity_talent_id"]),),
        ).fetchone()
        cast = connection.execute(
            """
            SELECT dc.character_id, t.name AS talent_name
            FROM dialog_cast AS dc
            JOIN dialogues AS d ON d.id = dc.dialogue_id
            JOIN talents AS t ON t.id = dc.talent_id
            WHERE d.dialog_uid = 'ep87-blue-shirt'
            """
        ).fetchone()

    # Source identity remains Vega, while the manual recording assignment stays
    # Brama and is explicitly reported as a manual override.
    assert str(identity_talent["name"]) == "Vega"
    assert int(cast["character_id"]) == int(vega_character["id"])
    assert str(cast["talent_name"]) == "Brama"
    assert any("dioverride manual" in warning for warning in report.warnings)


def test_v5_database_migrates_locked_character_to_source_identity_hint(tmp_path):
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE app_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        INSERT INTO app_meta(key, value) VALUES('schema_version', '5');

        CREATE TABLE characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE talents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE character_talent (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            talent_id INTEGER NOT NULL,
            is_locked INTEGER NOT NULL DEFAULT 0,
            source TEXT,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(character_id, talent_id)
        );

        INSERT INTO characters(
            id, name, normalized_name, is_active
        ) VALUES(1, 'Bapak Kemeja Biru', 'bapak kemeja biru', 1);

        INSERT INTO talents(
            id, name, normalized_name, is_active
        ) VALUES(1, 'Brama', 'brama', 1);

        INSERT INTO character_talent(
            character_id, talent_id, is_locked, source
        ) VALUES(1, 1, 1, 'auto-single');
        """
    )
    connection.commit()
    connection.close()

    database = Database(path)
    database.initialize()

    with database.connect() as migrated:
        row = migrated.execute(
            """
            SELECT
                c.base_normalized_name,
                c.identity_talent_id,
                t.name AS identity_talent_name
            FROM characters AS c
            LEFT JOIN talents AS t ON t.id = c.identity_talent_id
            WHERE c.id = 1
            """
        ).fetchone()
        version = migrated.execute(
            "SELECT value FROM app_meta WHERE key = 'schema_version'"
        ).fetchone()

    assert SCHEMA_VERSION == 6
    assert str(version["value"]) == "6"
    assert str(row["base_normalized_name"]) == "bapak kemeja biru"
    assert str(row["identity_talent_name"]) == "Brama"
