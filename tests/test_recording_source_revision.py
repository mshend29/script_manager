from __future__ import annotations

import sqlite3
from pathlib import Path

from openpyxl import Workbook

from core.database import Database
from core.project import Project
from core.project_settings import ProjectSettings
from import_engine.source_sync import SourceSyncEngine
from services.audit_service import AuditService
from services.recording_service import RecordingService


def _write_source(path, *, dialogue: str) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "SCRIPT"
    sheet.append([None, None, None, None, None])
    sheet.append(["IN", "OUT", "DIALOG", "TOKOH", "TALENT"])
    sheet.append(
        [
            "00:00:01,000",
            "00:00:02,000",
            dialogue,
            "Hendra",
            "Brama",
        ]
    )
    workbook.save(path)
    workbook.close()


def _project(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    source_file = source / "AA23-第1集_中文.xlsx"
    _write_source(source_file, dialogue="Halo")

    project = Project(
        file_path=tmp_path / "recording-revision.smproj",
        settings=ProjectSettings(
            project_name="Recording Revision",
            source_folder=str(source),
            episode_before="第",
            episode_after="集",
        ),
        project_id="recording-revision",
    )
    project.save()
    return project, source_file


def _scope(project: Project):
    with project.database.connect() as connection:
        row = connection.execute(
            """
            SELECT
                d.id AS dialogue_id,
                c.id AS character_id,
                t.id AS talent_id
            FROM dialogues AS d
            JOIN dialog_cast AS dc ON dc.dialogue_id = d.id
            JOIN characters AS c ON c.id = dc.character_id
            JOIN talents AS t ON t.id = dc.talent_id
            WHERE d.is_active = 1
            LIMIT 1
            """
        ).fetchone()
    return (
        int(row["dialogue_id"]),
        int(row["character_id"]),
        int(row["talent_id"]),
    )


def test_recorded_line_becomes_source_revised_without_losing_history(tmp_path):
    project, source_file = _project(tmp_path)
    engine = SourceSyncEngine()
    initial = engine.synchronize(project)
    assert not initial.has_errors

    dialogue_id, character_id, talent_id = _scope(project)
    service = RecordingService(project.database)
    service.set_recorded(dialogue_id, True)

    with project.database.connect() as connection:
        before = connection.execute(
            """
            SELECT
                rs.recorded_at,
                rs.source_signature_at_recording,
                d.source_signature
            FROM recording_status AS rs
            JOIN dialogues AS d ON d.id = rs.dialogue_id
            WHERE rs.dialogue_id = ?
            """,
            (dialogue_id,),
        ).fetchone()

    assert before["recorded_at"]
    assert str(before["source_signature_at_recording"]) == str(
        before["source_signature"]
    )

    _write_source(source_file, dialogue="Halo semuanya")
    refreshed = engine.synchronize(project)
    assert not refreshed.has_errors

    rows = service.get_dialogues(
        talent_id=talent_id,
        character_id=character_id,
        episode_number=1,
    )
    assert len(rows) == 1
    assert rows[0].dialogue_id == dialogue_id
    assert rows[0].is_recorded is True
    assert rows[0].source_revised is True

    with project.database.connect() as connection:
        after = connection.execute(
            """
            SELECT
                rs.is_recorded,
                rs.recorded_at,
                rs.source_signature_at_recording,
                d.source_signature
            FROM recording_status AS rs
            JOIN dialogues AS d ON d.id = rs.dialogue_id
            WHERE rs.dialogue_id = ?
            """,
            (dialogue_id,),
        ).fetchone()

    assert int(after["is_recorded"]) == 1
    assert str(after["recorded_at"]) == str(before["recorded_at"])
    assert str(after["source_signature_at_recording"]) == str(
        before["source_signature_at_recording"]
    )
    assert str(after["source_signature_at_recording"]) != str(
        after["source_signature"]
    )

    audit = AuditService(project.database).recent(1)
    assert audit
    assert audit[0].action == "REFRESH_APPLIED"


def test_rerecord_or_bulk_check_accepts_current_source_signature(tmp_path):
    project, source_file = _project(tmp_path)
    engine = SourceSyncEngine()
    engine.synchronize(project)

    dialogue_id, character_id, talent_id = _scope(project)
    service = RecordingService(project.database)
    service.set_recorded(dialogue_id, True)

    _write_source(source_file, dialogue="Revisi")
    engine.synchronize(project)

    stale = service.get_dialogues(
        talent_id=talent_id,
        character_id=character_id,
        episode_number=1,
    )
    assert stale[0].source_revised is True

    # Check All semantics: marking an already-recorded revised line as recorded
    # again means the operator accepts the current source after re-recording.
    assert service.set_recorded_bulk([dialogue_id], True) == 1

    accepted = service.get_dialogues(
        talent_id=talent_id,
        character_id=character_id,
        episode_number=1,
    )
    assert accepted[0].is_recorded is True
    assert accepted[0].source_revised is False

    with project.database.connect() as connection:
        current = connection.execute(
            """
            SELECT
                rs.source_signature_at_recording,
                d.source_signature
            FROM recording_status AS rs
            JOIN dialogues AS d ON d.id = rs.dialogue_id
            WHERE rs.dialogue_id = ?
            """,
            (dialogue_id,),
        ).fetchone()

    assert str(current["source_signature_at_recording"]) == str(
        current["source_signature"]
    )

    service.set_recorded_bulk([dialogue_id], False)

    with project.database.connect() as connection:
        cleared = connection.execute(
            """
            SELECT is_recorded, source_signature_at_recording
            FROM recording_status
            WHERE dialogue_id = ?
            """,
            (dialogue_id,),
        ).fetchone()

    assert int(cleared["is_recorded"]) == 0
    assert cleared["source_signature_at_recording"] is None


def test_schema_v11_migration_backfills_recorded_source_baseline(tmp_path):
    path = tmp_path / "recording-v10.db"
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        connection.executescript(
            """
            CREATE TABLE dialogues (
                id INTEGER PRIMARY KEY,
                dialog_uid TEXT NOT NULL UNIQUE,
                source_signature TEXT
            );

            CREATE TABLE recording_status (
                dialogue_id INTEGER PRIMARY KEY,
                is_recorded INTEGER NOT NULL DEFAULT 0,
                recorded_at TEXT,
                updated_at TEXT
            );

            INSERT INTO dialogues(id, dialog_uid, source_signature)
            VALUES(1, 'persistent-1', 'source-signature-1');

            INSERT INTO dialogues(id, dialog_uid, source_signature)
            VALUES(2, 'persistent-2', 'source-signature-2');

            INSERT INTO recording_status(
                dialogue_id, is_recorded, recorded_at, updated_at
            )
            VALUES(1, 1, '2026-09-02T10:00:00', '2026-09-02T10:00:00');

            INSERT INTO recording_status(
                dialogue_id, is_recorded, recorded_at, updated_at
            )
            VALUES(2, 0, NULL, '2026-09-02T10:00:00');
            """
        )

        Database._migrate_recording_source_signature_v11(connection)

        columns = {
            str(row["name"])
            for row in connection.execute(
                "PRAGMA table_info(recording_status)"
            ).fetchall()
        }
        recorded = connection.execute(
            """
            SELECT source_signature_at_recording
            FROM recording_status
            WHERE dialogue_id = 1
            """
        ).fetchone()
        unrecorded = connection.execute(
            """
            SELECT source_signature_at_recording
            FROM recording_status
            WHERE dialogue_id = 2
            """
        ).fetchone()
    finally:
        connection.close()

    assert "source_signature_at_recording" in columns
    assert str(recorded["source_signature_at_recording"]) == "source-signature-1"
    assert unrecorded["source_signature_at_recording"] is None


def test_dialog_page_contains_source_revision_operator_feedback() -> None:
    source = Path("pages/dialog_page.py").read_text(encoding="utf-8")

    assert "⚠ Source Revised" in source
    assert "source_revised" in source
    assert "Recording history tetap dipertahankan" in source
