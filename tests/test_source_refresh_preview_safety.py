from __future__ import annotations

import hashlib
import sqlite3

from openpyxl import Workbook

from core.database import Database, SCHEMA_VERSION
from core.project import Project
from core.project_settings import ProjectSettings
from import_engine.source_sync import SourceSyncEngine
from services.audit_service import AuditService


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_source(path, *, talent: str) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Worksheet"
    sheet.append([None, None, None, None, None])
    sheet.append(["IN", "OUT", "DIALOG", "TOKOH", "TALENT"])
    sheet.append([
        "00:00:01,000",
        "00:00:02,000",
        "Halo",
        "Bapak kemeja biru",
        talent,
    ])
    workbook.save(path)
    workbook.close()


def _project(tmp_path) -> tuple[Project, object]:
    source = tmp_path / "source"
    source.mkdir()
    file_path = source / "AA23-第87集_中文.xlsx"
    _write_source(file_path, talent="Brama")

    project = Project(
        root=tmp_path / "project",
        settings=ProjectSettings(
            project_name="Preview Test",
            source_folder=str(source),
            episode_before="第",
            episode_after="集",
        ),
    )
    project.ensure_structure()
    project.database.initialize()
    return project, file_path


def test_prepare_is_read_only_then_apply_backs_up_audits_and_changes_cast(tmp_path):
    project, source_file = _project(tmp_path)
    engine = SourceSyncEngine()

    initial = engine.synchronize(project)
    assert not initial.has_errors

    with project.database.connect() as connection:
        dialogue = connection.execute(
            "SELECT id, episode_id FROM dialogues LIMIT 1"
        ).fetchone()
        connection.execute(
            """
            UPDATE recording_status
            SET is_recorded = 1,
                recorded_at = '2026-08-27T13:00:00',
                updated_at = '2026-08-27T13:00:00'
            WHERE dialogue_id = ?
            """,
            (int(dialogue["id"]),),
        )
        cast = connection.execute(
            "SELECT character_id, talent_id FROM dialog_cast WHERE dialogue_id = ?",
            (int(dialogue["id"]),),
        ).fetchone()
        connection.execute(
            """
            INSERT INTO stem_status(
                episode_id, talent_id, character_id,
                status, note, updated_at
            ) VALUES(?, ?, ?, 'REVISION', 'client check', '2026-08-27T13:00:00')
            """,
            (
                int(dialogue["episode_id"]),
                int(cast["talent_id"]),
                int(cast["character_id"]),
            ),
        )

    _write_source(source_file, talent="Vega")

    before_prepare = _sha256(project.database_file)
    prepared = engine.prepare(project)
    after_prepare = _sha256(project.database_file)

    assert before_prepare == after_prepare
    assert prepared.preview is not None
    assert prepared.preview.source_changed == 1
    assert prepared.preview.cast_changed == 1
    assert prepared.preview.recording_affected == 1
    assert prepared.preview.tracking_affected == 1
    assert prepared.synced_at == ""
    assert prepared.backup_path == ""

    applied = engine.apply(project, prepared)
    assert applied.backup_path
    backup_path = project.root / "backups" / (
        __import__("pathlib").Path(applied.backup_path).name
    )
    assert backup_path.exists()

    with project.database.connect() as connection:
        cast_after = connection.execute(
            """
            SELECT t.name AS talent_name, rs.is_recorded
            FROM dialog_cast AS dc
            JOIN talents AS t ON t.id = dc.talent_id
            JOIN recording_status AS rs ON rs.dialogue_id = dc.dialogue_id
            LIMIT 1
            """
        ).fetchone()

    assert str(cast_after["talent_name"]) == "Vega"
    assert int(cast_after["is_recorded"]) == 1

    audit = AuditService(project.database).recent(1)
    assert audit
    assert audit[0].action == "REFRESH_APPLIED"
    assert audit[0].details["backup_path"] == applied.backup_path


def test_schema_migration_creates_pre_migration_backup(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()

    with database.connect() as connection:
        connection.execute(
            "UPDATE app_meta SET value = ? WHERE key = 'schema_version'",
            (str(SCHEMA_VERSION - 1),),
        )

    database.initialize()

    backups = list((tmp_path / "backups").glob("project_before_schema_*.db"))
    assert backups

    connection = sqlite3.connect(backups[0])
    try:
        version = connection.execute(
            "SELECT value FROM app_meta WHERE key = 'schema_version'"
        ).fetchone()[0]
    finally:
        connection.close()

    assert version == str(SCHEMA_VERSION - 1)

    with database.connect() as connection:
        current = connection.execute(
            "SELECT value FROM app_meta WHERE key = 'schema_version'"
        ).fetchone()[0]
        table = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name = 'audit_log'
            """
        ).fetchone()

    assert current == str(SCHEMA_VERSION)
    assert table is not None
