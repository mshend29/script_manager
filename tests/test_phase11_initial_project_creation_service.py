from __future__ import annotations

from pathlib import Path

import pytest

from core.project import Project
from core.project_manager import ProjectManager
from core.project_settings import ProjectSettings
from import_engine.source_sync import SourceSyncProgress, SourceSyncReport
from services.initial_project_creation_service import (
    InitialProjectCreationError,
    InitialProjectCreationService,
)


def _settings(source_folder: Path) -> ProjectSettings:
    return ProjectSettings(
        project_name="Initial Sync",
        project_code="IS01",
        client_name="Client",
        start_date="2026-09-07",
        source_folder=str(source_folder),
        episode_before="EP",
        episode_after="",
    )


class _SuccessfulEngine:
    def synchronize(self, project, *, progress_callback=None):
        if progress_callback is not None:
            progress_callback(
                SourceSyncProgress(
                    stage="synchronizing",
                    message="Applying source changes...",
                )
            )

        with project.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO source_files(
                    file_path, file_name, episode_number, fingerprint,
                    is_active, imported_at, last_seen_at
                )
                VALUES(?, ?, ?, ?, 1, ?, ?)
                """,
                ("/source/EP1.xlsx", "EP1.xlsx", 1, "fp-1", "now", "now"),
            )
            source_id = int(cursor.lastrowid)
            cursor = connection.execute(
                """
                INSERT INTO episodes(episode_number, source_file_id, title, is_active)
                VALUES(?, ?, ?, 1)
                """,
                (1, source_id, "Episode 1"),
            )
            episode_id = int(cursor.lastrowid)
            connection.execute(
                """
                INSERT INTO dialogues(
                    dialog_uid, episode_id, source_file_id, dialog_text, is_active
                )
                VALUES(?, ?, ?, ?, 1)
                """,
                ("dialog-1", episode_id, source_id, "Halo"),
            )

        return SourceSyncReport(
            scanned=1,
            inspected=1,
            parsed_files=1,
            parsed_dialogues=1,
            added=1,
            dialogues_added=1,
            synced_at="2026-09-07T07:00:00",
        )


class _ErrorReportEngine:
    def synchronize(self, project, *, progress_callback=None):
        return SourceSyncReport(
            scanned=1,
            problems=["EP1.xlsx: workbook corrupt"],
        )


class _VerificationMismatchEngine:
    def synchronize(self, project, *, progress_callback=None):
        return SourceSyncReport(
            scanned=1,
            parsed_files=1,
            parsed_dialogues=3,
        )


def test_initial_creation_runs_sync_verifies_and_keeps_project(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    manager = ProjectManager()
    service = InitialProjectCreationService(manager, _SuccessfulEngine())
    progress: list[SourceSyncProgress] = []

    result = service.run(
        _settings(source),
        tmp_path,
        progress_callback=progress.append,
    )

    assert result.project.project_file.is_file()
    assert manager.current is result.project
    assert result.report.parsed_dialogues == 1
    assert [item.stage for item in progress] == [
        "creating_project",
        "synchronizing",
        "verifying",
        "ready",
    ]

    with result.project.database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM episodes WHERE is_active = 1"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM dialogues WHERE is_active = 1"
        ).fetchone()[0] == 1


def test_initial_sync_error_report_rolls_back_and_restores_previous(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    manager = ProjectManager()
    previous = Project(
        file_path=tmp_path / "existing.smproj",
        settings=ProjectSettings(project_name="Existing", project_code="EX01"),
        project_id="existing-project",
    )
    manager.current = previous
    settings = _settings(source)
    destination = manager.preview_new_project_file(settings, tmp_path)
    service = InitialProjectCreationService(manager, _ErrorReportEngine())

    with pytest.raises(InitialProjectCreationError, match="workbook corrupt"):
        service.run(settings, tmp_path)

    assert destination.exists() is False
    assert manager.current is previous


def test_post_sync_verification_failure_rolls_back_project(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    manager = ProjectManager()
    settings = _settings(source)
    destination = manager.preview_new_project_file(settings, tmp_path)
    service = InitialProjectCreationService(
        manager,
        _VerificationMismatchEngine(),
    )

    with pytest.raises(InitialProjectCreationError, match="Verifikasi database"):
        service.run(settings, tmp_path)

    assert destination.exists() is False
    assert manager.current is None
