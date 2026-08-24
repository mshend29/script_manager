from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from core.database import Database
from import_engine.episode_extractor import extract_episode_number
from import_engine.parser import ScriptParser
from import_engine.scanner import ScannedSourceFile, SourceScanResult
from import_engine.synchronizer import DialogueSynchronizer


def _save_source(path: Path, character: str, talent: str) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "SCRIPT"
    sheet.append(["IN", "OUT", "DIALOG", "TOKOH", "TALENT"])
    sheet.append(
        [
            "00:00:01,000",
            "00:00:02,000",
            "Reaksi",
            character,
            talent,
        ]
    )
    workbook.save(path)


def _scan(path: Path, *, episode_number: int) -> SourceScanResult:
    return SourceScanResult(
        source_folder=str(path.parent),
        files=[
            ScannedSourceFile(
                file_path=str(path),
                file_name=path.name,
                episode_number=episode_number,
                episode_raw=str(episode_number),
                file_size=path.stat().st_size,
                modified_at="2026-08-24T13:00:00",
                fingerprint="real-source-test",
            )
        ],
    )


def test_unicode_episode_delimiters_match_real_source_filename() -> None:
    result = extract_episode_number(
        "AA23-第110集_中文.xlsx",
        before="第",
        after="集",
    )

    assert result.episode_number == 110
    assert result.raw_value == "110"


def test_single_group_character_can_keep_multiple_source_talents(tmp_path) -> None:
    source_path = tmp_path / "AA23-第103集_中文.xlsx"
    _save_source(source_path, "Komplotan penipu", "Vega & Brama")

    parsed = ScriptParser().parse(source_path, episode_number=103)
    row = parsed.rows[0]

    assert row.characters == ("Komplotan penipu",)
    assert row.talents == ("Vega", "Brama")
    assert len(row.cast_pairs) == 2
    assert "MULTI_TALENT" in row.status

    database = Database(tmp_path / "project.db")
    database.initialize()

    report = DialogueSynchronizer().synchronize(
        database=database,
        scan=_scan(source_path, episode_number=103),
        parse_results={str(source_path): parsed},
        synced_at="2026-08-24T13:00:00",
    )

    with database.connect() as connection:
        cast_rows = connection.execute(
            """
            SELECT c.name AS character_name, t.name AS talent_name
            FROM dialog_cast AS dc
            JOIN characters AS c ON c.id = dc.character_id
            LEFT JOIN talents AS t ON t.id = dc.talent_id
            ORDER BY dc.position
            """
        ).fetchall()
        locked_count = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM character_talent AS ct
            JOIN characters AS c ON c.id = ct.character_id
            WHERE c.normalized_name = 'komplotan penipu'
              AND ct.is_locked = 1
            """
        ).fetchone()["total"]

    assert [
        (item["character_name"], item["talent_name"])
        for item in cast_rows
    ] == [
        ("Komplotan penipu", "Vega"),
        ("Komplotan penipu", "Brama"),
    ]
    assert locked_count == 0
    assert report.unresolved_cast == 0


def test_generic_all_talent_stays_unresolved_and_is_not_created(tmp_path) -> None:
    source_path = tmp_path / "AA23-第46集_中文.xlsx"
    _save_source(source_path, "[Crowded]", "All")

    parsed = ScriptParser().parse(source_path, episode_number=46)
    row = parsed.rows[0]

    assert row.characters == ("Crowded",)
    assert row.talents == ()
    assert "GENERIC_TALENT" in row.status
    assert "MISSING_TALENT" in row.status

    database = Database(tmp_path / "project.db")
    database.initialize()

    report = DialogueSynchronizer().synchronize(
        database=database,
        scan=_scan(source_path, episode_number=46),
        parse_results={str(source_path): parsed},
        synced_at="2026-08-24T13:00:00",
    )

    with database.connect() as connection:
        all_talent_count = connection.execute(
            "SELECT COUNT(*) AS total FROM talents WHERE normalized_name = 'all'"
        ).fetchone()["total"]
        cast = connection.execute(
            """
            SELECT c.normalized_name, dc.talent_id
            FROM dialog_cast AS dc
            JOIN characters AS c ON c.id = dc.character_id
            """
        ).fetchone()

    assert all_talent_count == 0
    assert cast["normalized_name"] == "crowded"
    assert cast["talent_id"] is None
    assert report.unresolved_cast == 1
