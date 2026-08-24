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


def _scan(path: Path) -> SourceScanResult:
    item = ScannedSourceFile(
        file_path=str(path),
        file_name=path.name,
        episode_number=44,
        episode_raw="44",
        file_size=100,
        modified_at="2026-08-24T10:00:00",
        fingerprint="fingerprint-44",
    )
    return SourceScanResult(source_folder=str(path.parent), files=[item])


def _parse(path: Path) -> ScriptParseResult:
    talents = ("Anisa", "Fitri", "Anggraini")
    row = ParsedDialogueRow(
        source_row=37,
        time_in="00:00:10,000",
        time_out="00:00:12,000",
        dialogue="Crowd dialogue",
        raw_character="Crowded Anak kecil",
        raw_talent="Anisa, Fitri, Anggraini",
        characters=("Crowded Anak kecil",),
        talents=talents,
        cast_pairs=tuple(
            CastPair("Crowded Anak kecil", talent) for talent in talents
        ),
        dialog_uid="ep44-crowded-multitalent",
        status="MULTI_TALENT",
    )
    return ScriptParseResult(
        file_path=str(path),
        file_name=path.name,
        episode_number=44,
        layout=_layout(),
        rows=[row],
    )


def test_manual_mapping_collapses_multitalent_cast_without_integrity_error(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    source_path = tmp_path / "AA23-第44集_中文.xlsx"

    DialogueSynchronizer().synchronize(
        database=database,
        scan=_scan(source_path),
        parse_results={str(source_path): _parse(source_path)},
        synced_at="2026-08-24T10:00:00",
    )

    with database.connect() as connection:
        context = connection.execute(
            """
            SELECT
                d.id AS dialogue_id,
                d.episode_id,
                dc.character_id
            FROM dialogues AS d
            JOIN dialog_cast AS dc ON dc.dialogue_id = d.id
            WHERE d.dialog_uid = 'ep44-crowded-multitalent'
            LIMIT 1
            """
        ).fetchone()
        talents = connection.execute(
            "SELECT id, name FROM talents ORDER BY name COLLATE NOCASE"
        ).fetchall()
        before_cast = connection.execute(
            """
            SELECT dc.talent_id, dc.position
            FROM dialog_cast AS dc
            WHERE dc.dialogue_id = ? AND dc.character_id = ?
            ORDER BY dc.position
            """,
            (int(context["dialogue_id"]), int(context["character_id"])),
        ).fetchall()

        assert len(before_cast) == 3

        connection.execute(
            """
            UPDATE recording_status
            SET is_recorded = 1,
                recorded_at = '2026-08-24T10:05:00',
                updated_at = '2026-08-24T10:05:00'
            WHERE dialogue_id = ?
            """,
            (int(context["dialogue_id"]),),
        )

        for talent in talents:
            connection.execute(
                """
                INSERT INTO stem_status(
                    episode_id, talent_id, character_id,
                    status, note, updated_at
                ) VALUES(?, ?, ?, 'DELIVERED', '', '2026-08-24T10:06:00')
                """,
                (
                    int(context["episode_id"]),
                    int(talent["id"]),
                    int(context["character_id"]),
                ),
            )

    talent_by_name = {str(row["name"]): int(row["id"]) for row in talents}
    selected_talent_id = talent_by_name["Anisa"]
    character_id = int(context["character_id"])
    dialogue_id = int(context["dialogue_id"])

    DataService(database).set_locked_mapping(character_id, selected_talent_id)

    with database.connect() as connection:
        after_cast = connection.execute(
            """
            SELECT talent_id, position
            FROM dialog_cast
            WHERE dialogue_id = ? AND character_id = ?
            ORDER BY position
            """,
            (dialogue_id, character_id),
        ).fetchall()
        locked = connection.execute(
            """
            SELECT talent_id, is_locked, source
            FROM character_talent
            WHERE character_id = ? AND is_locked = 1
            """,
            (character_id,),
        ).fetchone()
        recording = connection.execute(
            "SELECT is_recorded FROM recording_status WHERE dialogue_id = ?",
            (dialogue_id,),
        ).fetchone()
        stem_count = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM stem_status
            WHERE episode_id = ? AND character_id = ?
            """,
            (int(context["episode_id"]), character_id),
        ).fetchone()

    assert len(after_cast) == 1
    assert int(after_cast[0]["talent_id"]) == selected_talent_id
    assert int(after_cast[0]["position"]) == 0
    assert int(locked["talent_id"]) == selected_talent_id
    assert int(locked["is_locked"]) == 1
    assert str(locked["source"]) == "manual"
    assert int(recording["is_recorded"]) == 1
    assert int(stem_count["total"]) == 0
