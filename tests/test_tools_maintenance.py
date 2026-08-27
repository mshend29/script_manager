from __future__ import annotations

import sqlite3
from pathlib import Path

from core.database import Database, SCHEMA_VERSION
from core.project import Project
from core.project_settings import ProjectSettings
from services.audit_service import AuditService
from services.backup_service import BackupService
from services.project_diagnostics_service import (
    STATUS_OK,
    ProjectDiagnosticsService,
)


def _insert_talent(database: Database, name: str) -> None:
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO talents(name, normalized_name, is_active)
            VALUES(?, ?, 1)
            """,
            (name, name.casefold()),
        )


def test_backup_restore_replaces_database_and_creates_safety_backup(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()

    _insert_talent(database, "Before")
    service = BackupService(database)
    original_backup = service.create("checkpoint")

    _insert_talent(database, "After")

    safety_backup, schema = service.restore(original_backup)

    assert safety_backup.exists()
    assert safety_backup != original_backup
    assert schema == SCHEMA_VERSION

    with database.connect() as connection:
        talents = [
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM talents ORDER BY id"
            ).fetchall()
        ]

    assert talents == ["Before"]

    audit = AuditService(database).recent(1)
    assert audit
    assert audit[0].action == "RESTORE_BACKUP"
    assert audit[0].details["source_backup"] == str(original_backup)
    assert audit[0].details["safety_backup"] == str(safety_backup)


def test_backup_validation_rejects_non_script_manager_and_newer_schema(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    service = BackupService(database)

    invalid = tmp_path / "invalid.db"
    connection = sqlite3.connect(invalid)
    try:
        connection.execute("CREATE TABLE random_table(id INTEGER)")
        connection.commit()
    finally:
        connection.close()

    valid, message = service.validate_backup(invalid)
    assert valid is False
    assert "bukan database Script Manager" in message

    newer = tmp_path / "newer.db"
    connection = sqlite3.connect(newer)
    try:
        connection.execute(
            "CREATE TABLE app_meta(key TEXT PRIMARY KEY, value TEXT)"
        )
        connection.execute(
            "INSERT INTO app_meta(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION + 1),),
        )
        connection.commit()
    finally:
        connection.close()

    valid, message = service.validate_backup(newer)
    assert valid is False
    assert "lebih baru" in message


def test_project_diagnostics_reports_database_and_folder_health(tmp_path):
    root = tmp_path / "project"
    source = tmp_path / "source"
    output = tmp_path / "output"
    delivery = tmp_path / "delivery"
    source.mkdir()
    output.mkdir()
    delivery.mkdir()

    project = Project(
        root=root,
        settings=ProjectSettings(
            project_name="Tools Test",
            source_folder=str(source),
            stem_output_folder=str(output),
            delivery_folder=str(delivery),
            main_drive_url="https://example.com/main",
        ),
    )
    project.ensure_structure()
    project.database.initialize()

    diagnostics = ProjectDiagnosticsService(project).run()
    checks = {check.key: check for check in diagnostics.checks}

    assert checks["schema"].status == STATUS_OK
    assert checks["integrity"].status == STATUS_OK
    assert checks["foreign_keys"].status == STATUS_OK
    assert checks["source_folder"].status == STATUS_OK
    assert checks["stem_output_folder"].status == STATUS_OK
    assert checks["delivery_folder"].status == STATUS_OK
    assert checks["main_drive"].status == STATUS_OK


def test_tools_page_and_ribbon_expose_real_maintenance_actions():
    root = Path(__file__).resolve().parents[1]
    page = (root / "pages" / "tools_page.py").read_text(encoding="utf-8")
    ribbon = (root / "app" / "ribbon.py").read_text(encoding="utf-8")
    main = (root / "app" / "main_window.py").read_text(encoding="utf-8")

    assert '"Tools & Maintenance"' in page
    assert '"PROJECT DIAGNOSTICS"' in page
    assert '"FOLDERS & DRIVE LINKS"' in page
    assert '"AUDIT HISTORY"' in page
    assert '"Restore Backup"' in page
    assert "ProjectDiagnosticsService" in page
    assert "AuditService" in page

    for action in (
        "tools.diagnostics",
        "tools.audit",
        "tools.backup",
        "tools.restore_backup",
        "tools.open_project_folder",
        "tools.open_source_folder",
        "tools.open_output_folder",
        "tools.open_delivery_folder",
        "tools.open_backups",
        "tools.open_logs",
        "tools.open_main_drive",
        "tools.open_material_drive",
        "tools.open_delivery_drive",
    ):
        assert action in ribbon
        assert action in main

    assert "QDesktopServices.openUrl" in main
    assert "QUrl.fromLocalFile" in main
    assert "service.validate_backup(backup_path)" in main
    assert "service.restore(backup_path)" in main
