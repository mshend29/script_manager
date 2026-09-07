from __future__ import annotations

import ast
from pathlib import Path

from openpyxl import Workbook

from core.project import Project
from core.project_settings import ProjectSettings
from import_engine.source_sync import SourceSyncEngine


ROOT = Path(__file__).resolve().parents[1]


def _write_script(path: Path, *, dialogue: str = "Halo") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def _project(
    tmp_path,
    *,
    episode_before: str = "第",
    episode_after: str = "集",
) -> Project:
    source = tmp_path / "source"
    source.mkdir(exist_ok=True)
    project = Project(
        file_path=tmp_path / "source-sync-regression.smproj",
        settings=ProjectSettings(
            project_name="Source Sync Regression",
            project_code="SSR01",
            client_name="Client",
            source_folder=str(source),
            episode_before=episode_before,
            episode_after=episode_after,
        ),
        project_id="source-sync-regression",
    )
    project.save()
    return project


def _active_counts(project: Project) -> tuple[int, int, int]:
    with project.database.connect() as connection:
        return (
            int(
                connection.execute(
                    "SELECT COUNT(*) FROM source_files WHERE is_active = 1"
                ).fetchone()[0]
            ),
            int(
                connection.execute(
                    "SELECT COUNT(*) FROM episodes WHERE is_active = 1"
                ).fetchone()[0]
            ),
            int(
                connection.execute(
                    "SELECT COUNT(*) FROM dialogues WHERE is_active = 1"
                ).fetchone()[0]
            ),
        )


def test_existing_source_sync_no_change_prepare_is_read_only_and_needs_no_apply(
    tmp_path,
):
    project = _project(tmp_path)
    source_file = Path(project.settings.source_folder) / "AA23-第1集_中文.xlsx"
    _write_script(source_file)
    engine = SourceSyncEngine()

    initial = engine.synchronize(project)
    assert not initial.has_errors
    assert initial.added == 1
    assert initial.dialogues_added == 1
    before = _active_counts(project)

    prepared = engine.prepare(project)

    assert not prepared.has_errors
    assert prepared.scanned == 1
    assert prepared.unchanged == 1
    assert prepared.added == 0
    assert prepared.changed == 0
    assert prepared.restored == 0
    assert prepared.inspected == 0
    assert prepared.parsed_files == 0
    assert prepared.parsed_dialogues == 0
    assert prepared.preview is not None
    assert prepared.preview.has_changes is False
    assert prepared.backup_path == ""
    assert prepared.synced_at == ""
    assert _active_counts(project) == before


def test_existing_source_sync_corrupt_workbook_stops_before_apply(tmp_path):
    project = _project(tmp_path)
    source_file = Path(project.settings.source_folder) / "AA23-第1集_中文.xlsx"
    source_file.write_bytes(b"not-an-xlsx")

    report = SourceSyncEngine().synchronize(project)

    assert report.has_errors
    assert report.scanned == 1
    assert report.inspected == 0
    assert report.parsed_files == 0
    assert report.backup_path == ""
    assert report.synced_at == ""
    assert any(source_file.name in problem for problem in report.problems)
    assert _active_counts(project) == (0, 0, 0)


def test_existing_source_sync_duplicate_episode_stops_before_workbook_open(tmp_path):
    project = _project(tmp_path)
    source = Path(project.settings.source_folder)
    _write_script(source / "AA23-第1集_A.xlsx")
    _write_script(source / "AA23-第1集_B.xlsx")

    report = SourceSyncEngine().synchronize(project)

    assert report.has_errors
    assert report.scanned == 2
    assert set(report.duplicate_episodes) == {1}
    assert len(report.duplicate_episodes[1]) == 2
    assert report.inspected == 0
    assert report.parsed_files == 0
    assert report.backup_path == ""
    assert report.synced_at == ""
    assert _active_counts(project) == (0, 0, 0)


def test_existing_source_sync_wrong_delimiter_stops_at_scanner(tmp_path):
    project = _project(
        tmp_path,
        episode_before="EP",
        episode_after="_",
    )
    source_file = Path(project.settings.source_folder) / "AA23-第1集_中文.xlsx"
    _write_script(source_file)

    report = SourceSyncEngine().synchronize(project)

    assert report.has_errors
    assert report.scanned == 0
    assert report.inspected == 0
    assert report.parsed_files == 0
    assert report.backup_path == ""
    assert report.synced_at == ""
    assert any(source_file.name in problem for problem in report.problems)
    assert _active_counts(project) == (0, 0, 0)


def _method(path: Path, class_name: str, method_name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return item
    raise AssertionError(f"{class_name}.{method_name} not found in {path}")


def test_f5_preview_and_initial_creation_keep_one_production_sync_pipeline():
    main_path = ROOT / "app" / "main_window.py"
    worker_path = ROOT / "app" / "source_sync_worker.py"
    initial_path = ROOT / "services" / "initial_project_creation_service.py"

    sync_source = ast.unparse(_method(main_path, "MainWindow", "sync_source"))
    run_sync = ast.unparse(_method(main_path, "MainWindow", "_run_source_sync"))
    prepared = ast.unparse(_method(main_path, "MainWindow", "_source_sync_prepared"))
    worker_run = ast.unparse(_method(worker_path, "SourceSyncWorker", "run"))
    initial_run = ast.unparse(
        _method(initial_path, "InitialProjectCreationService", "run")
    )

    # F5/menu use the normal prepare -> preview -> apply controller path.
    assert "_run_source_sync" in sync_source
    assert "start_prepare" in run_sync
    assert "SourceRefreshPreviewDialog" in prepared
    assert "apply_after_prepare" in prepared
    assert "preview.has_changes" in prepared
    assert "_refresh_tracking_files_state" in prepared

    # The background worker owns the same production engine prepare/apply.
    assert "self.engine.prepare" in worker_run
    assert "self.engine.apply" in worker_run

    # Initial New Project does not implement a second importer/parser path.
    assert "self.source_sync_engine.synchronize" in initial_run
    assert "SourceSyncEngine(" not in initial_run
