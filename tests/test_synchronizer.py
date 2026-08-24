from pathlib import Path

from core.database import Database
from import_engine.parser import (
    CastPair,
    ColumnLayout,
    ParsedDialogueRow,
    ScriptParseResult,
)
from import_engine.scanner import ScannedSourceFile, SourceScanResult
from import_engine.synchronizer import DialogueSynchronizer


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
    source_row: int,
    dialogue: str,
    characters: tuple[str, ...],
    talents: tuple[str, ...],
    cast_pairs: tuple[CastPair, ...] = (),
) -> ParsedDialogueRow:
    return ParsedDialogueRow(
        source_row=source_row,
        time_in="00:00:01,000",
        time_out="00:00:02,000",
        dialogue=dialogue,
        raw_character=" - ".join(characters),
        raw_talent=" - ".join(talents),
        characters=characters,
        talents=talents,
        cast_pairs=cast_pairs,
        dialog_uid=uid,
        status="OK",
    )


def _parse_result(path: Path, rows: list[ParsedDialogueRow]) -> ScriptParseResult:
    return ScriptParseResult(
        file_path=str(path),
        file_name=path.name,
        episode_number=1,
        layout=_layout(),
        rows=rows,
    )


def _scan(path: Path, fingerprint: str) -> SourceScanResult:
    item = ScannedSourceFile(
        file_path=str(path),
        file_name=path.name,
        episode_number=1,
        episode_raw="1",
        file_size=100,
        modified_at="2026-08-24T10:00:00",
        fingerprint=fingerprint,
    )
    return SourceScanResult(
        source_folder=str(path.parent),
        files=[item],
    )


def test_recording_checkbox_survives_changed_source(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    source_path = tmp_path / "EP1.xlsx"

    synchronizer = DialogueSynchronizer()
    row = _row(
        uid="stable-uid",
        source_row=2,
        dialogue="Halo",
        characters=("Hendra",),
        talents=("Brama",),
        cast_pairs=(CastPair("Hendra", "Brama"),),
    )

    synchronizer.synchronize(
        database=database,
        scan=_scan(source_path, "fingerprint-1"),
        parse_results={str(source_path): _parse_result(source_path, [row])},
        synced_at="2026-08-24T10:00:00",
    )

    with database.connect() as connection:
        dialogue_id = connection.execute(
            "SELECT id FROM dialogues WHERE dialog_uid = 'stable-uid'"
        ).fetchone()["id"]
        connection.execute(
            "UPDATE recording_status SET is_recorded = 1 WHERE dialogue_id = ?",
            (dialogue_id,),
        )

    synchronizer.synchronize(
        database=database,
        scan=_scan(source_path, "fingerprint-2"),
        parse_results={str(source_path): _parse_result(source_path, [row])},
        synced_at="2026-08-24T11:00:00",
    )

    with database.connect() as connection:
        status = connection.execute(
            """
            SELECT rs.is_recorded
            FROM recording_status AS rs
            JOIN dialogues AS d ON d.id = rs.dialogue_id
            WHERE d.dialog_uid = 'stable-uid'
            """
        ).fetchone()

    assert status["is_recorded"] == 1


def test_removed_dialogue_becomes_inactive_without_losing_history(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    source_path = tmp_path / "EP1.xlsx"
    synchronizer = DialogueSynchronizer()

    row_a = _row(
        uid="uid-a",
        source_row=2,
        dialogue="A",
        characters=("Hendra",),
        talents=("Brama",),
        cast_pairs=(CastPair("Hendra", "Brama"),),
    )
    row_b = _row(
        uid="uid-b",
        source_row=3,
        dialogue="B",
        characters=("Joko",),
        talents=("Dika",),
        cast_pairs=(CastPair("Joko", "Dika"),),
    )

    synchronizer.synchronize(
        database=database,
        scan=_scan(source_path, "fingerprint-1"),
        parse_results={str(source_path): _parse_result(source_path, [row_a, row_b])},
        synced_at="2026-08-24T10:00:00",
    )

    report = synchronizer.synchronize(
        database=database,
        scan=_scan(source_path, "fingerprint-2"),
        parse_results={str(source_path): _parse_result(source_path, [row_a])},
        synced_at="2026-08-24T11:00:00",
    )

    with database.connect() as connection:
        removed = connection.execute(
            "SELECT id, is_active FROM dialogues WHERE dialog_uid = 'uid-b'"
        ).fetchone()
        recording = connection.execute(
            "SELECT is_recorded FROM recording_status WHERE dialogue_id = ?",
            (removed["id"],),
        ).fetchone()

    assert removed["is_active"] == 0
    assert recording is not None
    assert report.dialogues_deactivated == 1


def test_locked_single_mapping_corrects_multi_cast_order(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    source_path = tmp_path / "EP1.xlsx"
    synchronizer = DialogueSynchronizer()

    hendra = _row(
        uid="single-hendra",
        source_row=2,
        dialogue="Hendra single",
        characters=("Hendra",),
        talents=("Brama",),
        cast_pairs=(CastPair("Hendra", "Brama"),),
    )
    joko = _row(
        uid="single-joko",
        source_row=3,
        dialogue="Joko single",
        characters=("Joko",),
        talents=("Dika",),
        cast_pairs=(CastPair("Joko", "Dika"),),
    )
    multi = _row(
        uid="multi",
        source_row=4,
        dialogue="Dialog bersama",
        characters=("Hendra", "Joko"),
        talents=("Dika", "Brama"),
        cast_pairs=(
            CastPair("Hendra", "Dika"),
            CastPair("Joko", "Brama"),
        ),
    )

    report = synchronizer.synchronize(
        database=database,
        scan=_scan(source_path, "fingerprint-1"),
        parse_results={
            str(source_path): _parse_result(source_path, [hendra, joko, multi])
        },
        synced_at="2026-08-24T10:00:00",
    )

    with database.connect() as connection:
        rows = connection.execute(
            """
            SELECT c.name AS character_name, t.name AS talent_name
            FROM dialog_cast AS dc
            JOIN dialogues AS d ON d.id = dc.dialogue_id
            JOIN characters AS c ON c.id = dc.character_id
            LEFT JOIN talents AS t ON t.id = dc.talent_id
            WHERE d.dialog_uid = 'multi'
            ORDER BY dc.position
            """
        ).fetchall()
        dialogue_count = connection.execute(
            "SELECT COUNT(*) AS total FROM dialogues WHERE dialog_uid = 'multi'"
        ).fetchone()["total"]

    assert [(row["character_name"], row["talent_name"]) for row in rows] == [
        ("Hendra", "Brama"),
        ("Joko", "Dika"),
    ]
    assert dialogue_count == 1
    assert report.auto_locked == 2
