from pathlib import Path

from openpyxl import Workbook

from core.project import Project
from core.project_settings import ProjectSettings
from import_engine.source_sync import SourceSyncEngine


ROOT = Path(__file__).resolve().parents[1]


def _write_source(path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Worksheet"
    sheet.append([None, None, None, None, None])
    sheet.append(["IN", "OUT", "DIALOG", "TOKOH", "TALENT"])
    sheet.append([
        "00:00:01,000",
        "00:00:02,000",
        "Progress test",
        "Hendra",
        "Brama",
    ])
    workbook.save(path)
    workbook.close()


def _make_project(tmp_path) -> Project:
    source_folder = tmp_path / "source"
    source_folder.mkdir()
    _write_source(source_folder / "AA23-第1集_中文.xlsx")

    project = Project(
        root=tmp_path / "project",
        settings=ProjectSettings(
            project_name="Progress Test",
            project_folder=str(tmp_path / "project"),
            source_folder=str(source_folder),
            episode_before="第",
            episode_after="集",
        ),
    )
    project.ensure_structure()
    project.database.initialize()
    return project


def test_source_sync_reports_progress_for_files_that_are_processed(tmp_path):
    project = _make_project(tmp_path)
    events = []

    report = SourceSyncEngine().synchronize(
        project,
        progress_callback=events.append,
    )

    assert not report.has_errors
    assert report.added == 1

    stages = [event.stage for event in events]
    assert stages[0] == "scanning"
    assert "classifying" in stages
    assert "inspecting" in stages
    assert "parsing" in stages
    assert "diffing" in stages
    assert "preview_ready" in stages
    assert "backup" in stages
    assert "synchronizing" in stages
    assert stages[-1] == "complete"

    inspect_events = [
        event for event in events if event.stage == "inspecting"
    ]
    assert [(event.current, event.total) for event in inspect_events] == [
        (0, 1),
        (1, 1),
    ]
    assert inspect_events[-1].file_name == "AA23-第1集_中文.xlsx"

    parse_events = [event for event in events if event.stage == "parsing"]
    assert [(event.current, event.total) for event in parse_events] == [
        (0, 1),
        (1, 1),
    ]
    assert parse_events[-1].file_name == "AA23-第1集_中文.xlsx"


def test_unchanged_refresh_skips_file_progress_but_reports_sync(tmp_path):
    project = _make_project(tmp_path)
    engine = SourceSyncEngine()
    initial = engine.synchronize(project)
    assert not initial.has_errors

    events = []
    refreshed = engine.synchronize(
        project,
        progress_callback=events.append,
    )

    assert not refreshed.has_errors
    assert refreshed.unchanged == 1

    stages = [event.stage for event in events]
    assert "inspecting" not in stages
    assert "parsing" not in stages
    assert stages == [
        "scanning",
        "classifying",
        "diffing",
        "preview_ready",
        "backup",
        "synchronizing",
        "complete",
    ]


def test_worker_and_main_window_wire_progress_with_queued_delivery():
    worker_source = (
        ROOT / "app" / "source_sync_worker.py"
    ).read_text(encoding="utf-8")
    main_source = (
        ROOT / "app" / "main_window.py"
    ).read_text(encoding="utf-8")

    assert "progress = Signal(object)" in worker_source
    assert "progress_callback=self.progress.emit" in worker_source.replace(
        "\n", ""
    ).replace(" ", "")

    assert "QProgressBar" in main_source
    assert "worker.progress.connect(" in main_source
    assert "self._source_sync_progress" in main_source
    assert "Qt.ConnectionType.QueuedConnection" in main_source
    assert "Inspecting workbooks" in (
        ROOT / "import_engine" / "source_sync.py"
    ).read_text(encoding="utf-8")
