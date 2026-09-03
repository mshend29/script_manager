from __future__ import annotations

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
from services.tracking_service import DELIVERED


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
    uid: str,
    source_row: int,
    dialogue: str,
    character: str,
    talent: str,
) -> ParsedDialogueRow:
    return ParsedDialogueRow(
        source_row=source_row,
        time_in=f"00:00:{source_row:02d},000",
        time_out=f"00:00:{source_row + 1:02d},000",
        dialogue=dialogue,
        raw_character=character,
        raw_talent=talent,
        characters=(character,),
        talents=(talent,),
        cast_pairs=(CastPair(character, talent),),
        dialog_uid=uid,
        status="OK",
    )


def _scan(path: Path, fingerprint: str) -> SourceScanResult:
    return SourceScanResult(
        source_folder=str(path.parent),
        files=[
            ScannedSourceFile(
                file_path=str(path),
                file_name=path.name,
                episode_number=1,
                episode_raw="1",
                file_size=100,
                modified_at="2026-09-02T10:00:00",
                fingerprint=fingerprint,
            )
        ],
    )


def _parse(path: Path, rows: list[ParsedDialogueRow]) -> ScriptParseResult:
    return ScriptParseResult(
        file_path=str(path),
        file_name=path.name,
        episode_number=1,
        layout=_layout(),
        rows=rows,
    )


def _sync(
    synchronizer: DialogueSynchronizer,
    database: Database,
    path: Path,
    fingerprint: str,
    rows: list[ParsedDialogueRow],
):
    return synchronizer.synchronize(
        database=database,
        scan=_scan(path, fingerprint),
        parse_results={str(path): _parse(path, rows)},
        synced_at=(
            "2026-09-02T10:00:00"
            if fingerprint == "fingerprint-1"
            else "2026-09-02T11:00:00"
        ),
    )


def _scope_for_uid(database: Database, dialog_uid: str) -> tuple[int, int, int]:
    with database.connect() as connection:
        row = connection.execute(
            """
            SELECT d.episode_id, dc.talent_id, dc.character_id
            FROM dialogues AS d
            JOIN dialog_cast AS dc ON dc.dialogue_id = d.id
            WHERE d.dialog_uid = ?
            LIMIT 1
            """,
            (dialog_uid,),
        ).fetchone()

    assert row is not None
    assert row["talent_id"] is not None
    return (
        int(row["episode_id"]),
        int(row["talent_id"]),
        int(row["character_id"]),
    )


def _set_delivered(database: Database, scope: tuple[int, int, int]) -> None:
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO stem_status(
                episode_id, talent_id, character_id, status, note
            )
            VALUES(?, ?, ?, ?, 'semantic-test')
            ON CONFLICT(episode_id, talent_id, character_id)
            DO UPDATE SET status = excluded.status, note = excluded.note
            """,
            (*scope, DELIVERED),
        )


def _status(database: Database, scope: tuple[int, int, int]):
    with database.connect() as connection:
        row = connection.execute(
            """
            SELECT status
            FROM stem_status
            WHERE episode_id = ?
              AND talent_id = ?
              AND character_id = ?
            """,
            scope,
        ).fetchone()
    return None if row is None else str(row["status"])


def test_added_dialogue_invalidates_only_affected_cast_scope(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    path = tmp_path / "EP1.xlsx"
    sync = DialogueSynchronizer()

    hendra = _row("uid-h", 2, "Hendra lama", "Hendra", "Brama")
    joko = _row("uid-j", 3, "Joko lama", "Joko", "Dika")
    _sync(sync, database, path, "fingerprint-1", [hendra, joko])

    hendra_scope = _scope_for_uid(database, "uid-h")
    joko_scope = _scope_for_uid(database, "uid-j")
    _set_delivered(database, hendra_scope)
    _set_delivered(database, joko_scope)

    added = _row("uid-new", 4, "Tambahan", "Hendra", "Brama")
    report = _sync(
        sync,
        database,
        path,
        "fingerprint-2",
        [hendra, joko, added],
    )

    assert _status(database, hendra_scope) is None
    assert _status(database, joko_scope) == DELIVERED
    assert [
        item.reasons for item in report.tracking_invalidations
    ] == [("DIALOG_ADDED",)]


def test_removed_dialogue_invalidates_only_removed_cast_scope(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    path = tmp_path / "EP1.xlsx"
    sync = DialogueSynchronizer()

    hendra = _row("uid-h", 2, "Hendra lama", "Hendra", "Brama")
    joko = _row("uid-j", 3, "Joko lama", "Joko", "Dika")
    _sync(sync, database, path, "fingerprint-1", [hendra, joko])

    hendra_scope = _scope_for_uid(database, "uid-h")
    joko_scope = _scope_for_uid(database, "uid-j")
    _set_delivered(database, hendra_scope)
    _set_delivered(database, joko_scope)

    report = _sync(
        sync,
        database,
        path,
        "fingerprint-2",
        [joko],
    )

    assert _status(database, hendra_scope) is None
    assert _status(database, joko_scope) == DELIVERED
    assert [
        item.reasons for item in report.tracking_invalidations
    ] == [("DIALOG_REMOVED",)]


def test_text_revision_invalidates_only_revised_cast_scope(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    path = tmp_path / "EP1.xlsx"
    sync = DialogueSynchronizer()

    hendra = _row("uid-h", 2, "Hendra lama", "Hendra", "Brama")
    joko = _row("uid-j", 3, "Joko lama", "Joko", "Dika")
    _sync(sync, database, path, "fingerprint-1", [hendra, joko])

    hendra_scope = _scope_for_uid(database, "uid-h")
    joko_scope = _scope_for_uid(database, "uid-j")
    _set_delivered(database, hendra_scope)
    _set_delivered(database, joko_scope)

    revised = _row(
        "uid-h-revised",
        2,
        "Hendra revisi",
        "Hendra",
        "Brama",
    )
    report = _sync(
        sync,
        database,
        path,
        "fingerprint-2",
        [revised, joko],
    )

    assert _status(database, hendra_scope) is None
    assert _status(database, joko_scope) == DELIVERED
    assert [
        item.reasons for item in report.tracking_invalidations
    ] == [("SOURCE_REVISED",)]


def test_cast_change_invalidates_old_and_new_scopes_but_not_unrelated(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    path = tmp_path / "EP1.xlsx"
    sync = DialogueSynchronizer()

    old_hendra = _row("uid-a", 2, "A", "Hendra", "Brama")
    dika_hendra = _row("uid-b", 3, "B", "Hendra", "Dika")
    unrelated = _row("uid-c", 4, "C", "Joko", "Vega")
    _sync(
        sync,
        database,
        path,
        "fingerprint-1",
        [old_hendra, dika_hendra, unrelated],
    )

    old_scope = _scope_for_uid(database, "uid-a")
    new_scope = _scope_for_uid(database, "uid-b")
    unrelated_scope = _scope_for_uid(database, "uid-c")
    assert old_scope != new_scope

    for scope in (old_scope, new_scope, unrelated_scope):
        _set_delivered(database, scope)

    # Real parser signatures ignore talent when character identity is present,
    # so uid-a remains the same while the resolved cast moves to Hendra / Dika.
    changed_cast = _row("uid-a", 2, "A", "Hendra", "Dika")
    report = _sync(
        sync,
        database,
        path,
        "fingerprint-2",
        [changed_cast, dika_hendra, unrelated],
    )

    assert _status(database, old_scope) is None
    assert _status(database, new_scope) is None
    assert _status(database, unrelated_scope) == DELIVERED

    invalidated = {
        (item.episode_id, item.talent_id, item.character_id): item.reasons
        for item in report.tracking_invalidations
    }
    assert invalidated[old_scope] == ("CAST_CHANGED",)
    assert invalidated[new_scope] == ("CAST_CHANGED",)
    assert unrelated_scope not in invalidated


def test_revision_status_is_preserved_during_semantic_invalidation(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    path = tmp_path / "EP1.xlsx"
    sync = DialogueSynchronizer()

    original = _row("uid-h", 2, "Lama", "Hendra", "Brama")
    _sync(sync, database, path, "fingerprint-1", [original])
    scope = _scope_for_uid(database, "uid-h")

    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO stem_status(
                episode_id, talent_id, character_id, status, note
            )
            VALUES(?, ?, ?, 'REVISION', 'manual revision')
            """,
            scope,
        )

    revised = _row("uid-h-new", 2, "Baru", "Hendra", "Brama")
    report = _sync(
        sync,
        database,
        path,
        "fingerprint-2",
        [revised],
    )

    assert _status(database, scope) == "REVISION"
    assert report.tracking_invalidations == []
