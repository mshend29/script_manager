from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from core.project import Project
from core.project_manager import ProjectManager
from core.project_settings import ProjectSettings
from import_engine.inspector import WorkbookInspector
from import_engine.parser import ScriptParser
from import_engine.source_sync import (
    SourceSyncEngine,
    SourceSyncProgress,
    SourceSyncReport,
)
from services.initial_project_creation_service import (
    InitialProjectCreationError,
    InitialProjectCreationService,
    InitialProjectSourceChangedError,
)
from services.source_preflight_service import SourcePreflightService
from services.source_setup_validation import validate_source_filenames


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


def _write_script(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["IN", "OUT", "DIALOG", "TOKOH", "TALENT"])
    sheet.append(["00:00:01", "00:00:02", "Halo", "INDAH", "Talent A"])
    workbook.save(path)
    workbook.close()


class _CountingInspector:
    def __init__(self) -> None:
        self.delegate = WorkbookInspector()
        self.calls = 0

    def inspect(self, file_path):
        self.calls += 1
        return self.delegate.inspect(file_path)


class _CountingParser:
    def __init__(self) -> None:
        self.delegate = ScriptParser()
        self.calls = 0

    def parse(self, file_path, *, episode_number):
        self.calls += 1
        return self.delegate.parse(file_path, episode_number=episode_number)


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


class _MutatingEngine(SourceSyncEngine):
    def __init__(self, source_file: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self.source_file = source_file
        self.mutated = False

    def synchronize(
        self,
        project,
        *,
        progress_callback=None,
        prepared_input=None,
    ):
        if prepared_input is not None and not self.mutated:
            self.source_file.write_bytes(
                self.source_file.read_bytes() + b"changed-after-create-check"
            )
            self.mutated = True
        return super().synchronize(
            project,
            progress_callback=progress_callback,
            prepared_input=prepared_input,
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


def test_initial_creation_reuses_preflight_parse_without_double_parsing(tmp_path):
    source = tmp_path / "source"
    source_file = source / "EP1.xlsx"
    _write_script(source_file)
    settings = _settings(source)
    validation = validate_source_filenames(
        source,
        episode_before=settings.episode_before,
        episode_after=settings.episode_after,
    )

    inspector = _CountingInspector()
    parser = _CountingParser()
    preflight = SourcePreflightService(
        inspector=inspector,
        parser=parser,
    ).run(validation)
    assert preflight.is_reusable
    assert inspector.calls == 1
    assert parser.calls == 1

    engine = SourceSyncEngine(inspector=inspector, parser=parser)
    manager = ProjectManager()
    progress: list[SourceSyncProgress] = []
    result = InitialProjectCreationService(manager, engine).run(
        settings,
        tmp_path,
        progress_callback=progress.append,
        preflight_report=preflight,
    )

    assert result.project.project_file.is_file()
    assert result.report.parsed_dialogues == 1
    assert inspector.calls == 1
    assert parser.calls == 1
    assert any(item.stage == "preflight_verified" for item in progress)
    assert any(item.stage == "preflight_reuse" for item in progress)


def test_changed_source_blocks_before_smproj_is_created(tmp_path):
    source = tmp_path / "source"
    source_file = source / "EP1.xlsx"
    _write_script(source_file)
    settings = _settings(source)
    validation = validate_source_filenames(
        source,
        episode_before=settings.episode_before,
        episode_after=settings.episode_after,
    )
    preflight = SourcePreflightService().run(validation)
    assert preflight.is_reusable

    source_file.write_bytes(source_file.read_bytes() + b"changed-before-create")

    manager = ProjectManager()
    destination = manager.preview_new_project_file(settings, tmp_path)
    service = InitialProjectCreationService(manager, SourceSyncEngine())

    with pytest.raises(
        InitialProjectSourceChangedError,
        match="Source berubah sejak Source Preflight",
    ):
        service.run(
            settings,
            tmp_path,
            preflight_report=preflight,
        )

    assert destination.exists() is False
    assert manager.current is None


def test_source_changed_after_precreate_check_is_caught_before_database_write(
    tmp_path,
):
    source = tmp_path / "source"
    source_file = source / "EP1.xlsx"
    _write_script(source_file)
    settings = _settings(source)
    validation = validate_source_filenames(
        source,
        episode_before=settings.episode_before,
        episode_after=settings.episode_after,
    )
    preflight = SourcePreflightService().run(validation)
    assert preflight.is_reusable

    manager = ProjectManager()
    destination = manager.preview_new_project_file(settings, tmp_path)
    engine = _MutatingEngine(source_file)
    service = InitialProjectCreationService(manager, engine)

    with pytest.raises(RuntimeError, match="Source berubah setelah preview"):
        service.run(
            settings,
            tmp_path,
            preflight_report=preflight,
        )

    assert engine.mutated is True
    assert destination.exists() is False
    assert manager.current is None


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
