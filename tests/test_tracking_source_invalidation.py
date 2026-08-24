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
from services.tracking_service import (
    DELIVERED,
    IN_PROGRESS,
    NOT_READY,
    RECORDED,
    TrackingService,
)


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


def _row(uid: str, source_row: int, dialogue: str) -> ParsedDialogueRow:
    return ParsedDialogueRow(
        source_row=source_row,
        time_in=f"00:00:{source_row:02d},000",
        time_out=f"00:00:{source_row + 1:02d},000",
        dialogue=dialogue,
        raw_character="Hendra",
        raw_talent="Brama",
        characters=("Hendra",),
        talents=("Brama",),
        cast_pairs=(CastPair("Hendra", "Brama"),),
        dialog_uid=uid,
        status="OK",
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
    return SourceScanResult(source_folder=str(path.parent), files=[item])


def _parse(path: Path, rows: list[ParsedDialogueRow]) -> ScriptParseResult:
    return ScriptParseResult(
        file_path=str(path),
        file_name=path.name,
        episode_number=1,
        layout=_layout(),
        rows=rows,
    )


def _single_chip(service: TrackingService, talent_id: int):
    character_rows = service.get_character_rows(talent_id, episode_number=1)
    assert len(character_rows) == 1
    assert len(character_rows[0].chips) == 1
    return character_rows[0].chips[0]


def test_changed_source_invalidates_delivered_status_before_new_line_is_recorded(
    tmp_path,
):
    database = Database(tmp_path / "project.db")
    database.initialize()
    source_path = tmp_path / "EP1.xlsx"

    synchronizer = DialogueSynchronizer()
    original = _row("uid-original", 2, "Dialog lama")

    synchronizer.synchronize(
        database=database,
        scan=_scan(source_path, "fingerprint-1"),
        parse_results={str(source_path): _parse(source_path, [original])},
        synced_at="2026-08-24T10:00:00",
    )

    with database.connect() as connection:
        ids = connection.execute(
            """
            SELECT
                d.id AS dialogue_id,
                e.id AS episode_id,
                dc.character_id,
                dc.talent_id
            FROM dialogues AS d
            JOIN episodes AS e ON e.id = d.episode_id
            JOIN dialog_cast AS dc ON dc.dialogue_id = d.id
            WHERE d.dialog_uid = 'uid-original'
            """
        ).fetchone()
        connection.execute(
            """
            UPDATE recording_status
            SET is_recorded = 1,
                recorded_at = '2026-08-24T10:05:00',
                updated_at = '2026-08-24T10:05:00'
            WHERE dialogue_id = ?
            """,
            (int(ids["dialogue_id"]),),
        )

    service = TrackingService(database)
    episode_id = int(ids["episode_id"])
    character_id = int(ids["character_id"])
    talent_id = int(ids["talent_id"])

    service.set_downstream_status(
        episode_id=episode_id,
        talent_id=talent_id,
        character_id=character_id,
        status=DELIVERED,
    )
    before = _single_chip(service, talent_id)
    assert before.display_status == DELIVERED

    added = _row("uid-new", 4, "Dialog tambahan client")
    report = synchronizer.synchronize(
        database=database,
        scan=_scan(source_path, "fingerprint-2"),
        parse_results={str(source_path): _parse(source_path, [original, added])},
        synced_at="2026-08-24T11:00:00",
    )

    during = _single_chip(service, talent_id)
    assert during.total_dialogues == 2
    assert during.recorded_dialogues == 1
    assert during.recording_status == IN_PROGRESS
    assert during.downstream_status == NOT_READY
    assert during.display_status == IN_PROGRESS
    assert any(
        "status tracking downstream direset karena source berubah" in warning
        for warning in report.warnings
    )

    with database.connect() as connection:
        new_dialogue = connection.execute(
            "SELECT id FROM dialogues WHERE dialog_uid = 'uid-new'"
        ).fetchone()
        connection.execute(
            """
            UPDATE recording_status
            SET is_recorded = 1,
                recorded_at = '2026-08-24T11:05:00',
                updated_at = '2026-08-24T11:05:00'
            WHERE dialogue_id = ?
            """,
            (int(new_dialogue["id"]),),
        )
        stale_status = connection.execute(
            """
            SELECT status
            FROM stem_status
            WHERE episode_id = ?
              AND talent_id = ?
              AND character_id = ?
            """,
            (episode_id, talent_id, character_id),
        ).fetchone()

    assert stale_status is None

    after = _single_chip(service, talent_id)
    assert after.recorded_dialogues == 2
    assert after.recording_status == RECORDED
    assert after.downstream_status == NOT_READY
    assert after.display_status == RECORDED
