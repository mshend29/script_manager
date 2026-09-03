from __future__ import annotations

import importlib.util
import os

from openpyxl import Workbook
import pytest

from core.project import Project
from core.project_settings import ProjectSettings
from import_engine.source_sync import SourceSyncEngine


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PYSIDE_AVAILABLE = importlib.util.find_spec("PySide6") is not None

pytestmark = pytest.mark.skipif(
    not PYSIDE_AVAILABLE,
    reason="PySide6 is only installed in the Qt runtime CI job.",
)

if PYSIDE_AVAILABLE:
    from PySide6.QtWidgets import QApplication

    from app.main_window import MainWindow
    from pages.data_alias_page import AliasDataPage
    from pages.tracking_compact_page import CompactTrackingPage


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


def _write_source(path, *, episode: int, dialogue: str) -> None:
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
            "Hendra" if episode == 1 else "Joko",
            "Brama" if episode == 1 else "Dika",
        ]
    )
    workbook.save(path)
    workbook.close()


def _project(tmp_path):
    source = tmp_path / "source"
    source.mkdir()

    source_file = source / "AA23-第1集_中文.xlsx"
    _write_source(source_file, episode=1, dialogue="Halo")

    project = Project(
        file_path=tmp_path / "qt-runtime.smproj",
        settings=ProjectSettings(
            project_name="Qt Runtime",
            source_folder=str(source),
            episode_before="第",
            episode_after="集",
        ),
        project_id="qt-runtime-smoke",
    )
    project.save()
    return project, source


def test_main_window_constructs_all_major_pages(qapp) -> None:
    window = MainWindow()

    assert tuple(window.PAGE_ORDER) == (
        "PROJECT",
        "SCRIPT",
        "DIALOG",
        "TRACKING",
        "DATA",
        "TOOLS",
        "HELP",
    )
    assert set(window.pages) == set(window.PAGE_ORDER)
    assert window.page_stack.count() == len(window.PAGE_ORDER)

    for page_name in window.PAGE_ORDER:
        assert window.pages[page_name] is not None

    assert isinstance(window.pages["DATA"], AliasDataPage)
    assert isinstance(window.pages["TRACKING"], CompactTrackingPage)

    assert window.sidebar is not None
    assert window.page_header is not None
    assert window.page_header.title_label.text() == "Project"

    window.set_page("DIALOG")
    qapp.processEvents()
    assert window.sidebar._buttons["DIALOG"].isChecked()
    assert window.page_header.title_label.text() == "Dialog"

    window.set_page("TRACKING")
    qapp.processEvents()
    assert window.sidebar._buttons["TRACKING"].isChecked()
    assert window.page_header.title_label.text() == "Tracking"

    window.set_page("PROJECT")
    qapp.processEvents()

    window.close()
    qapp.processEvents()


def test_project_open_source_sync_and_lazy_page_reload(qapp, tmp_path) -> None:
    project, source = _project(tmp_path)
    engine = SourceSyncEngine()

    initial = engine.synchronize(project)
    assert not initial.has_errors

    window = MainWindow()
    assert window.open_project_path(
        project.project_file,
        show_errors=False,
    )

    window.set_page("SCRIPT")
    qapp.processEvents()

    script_page = window.pages["SCRIPT"]
    assert script_page.table_model.rowCount() == 1
    assert script_page.table_model.data(
        script_page.table_model.index(0, 3)
    ) == "Halo"
    assert script_page.episode_combo.findData(1) >= 0

    # Simulate a successful source commit outside the UI worker, then emit the
    # exact application-level revision event used by _source_sync_applied.
    second_source = source / "AA23-第2集_中文.xlsx"
    _write_source(second_source, episode=2, dialogue="Episode dua")
    refreshed = engine.synchronize(project)
    assert not refreshed.has_errors

    revision = window._project_data_state.mark_changed()
    window.project_data_changed.emit(revision)
    qapp.processEvents()

    # The visible SCRIPT workspace refreshes immediately, including filters.
    assert script_page.table_model.rowCount() == 2
    assert script_page.episode_combo.findData(2) >= 0
    assert window._project_data_state.is_dirty("SCRIPT") is False

    # Hidden data workspaces stay dirty until opened.
    assert window._project_data_state.is_dirty("DIALOG") is True
    assert window._project_data_state.is_dirty("TRACKING") is True
    assert window._project_data_state.is_dirty("DATA") is True

    window.set_page("DIALOG")
    qapp.processEvents()

    dialog_page = window.pages["DIALOG"]
    assert window._project_data_state.is_dirty("DIALOG") is False
    assert dialog_page.talent_combo.findText("Brama") >= 0
    assert dialog_page.talent_combo.findText("Dika") >= 0

    window.set_page("DATA")
    qapp.processEvents()

    data_page = window.pages["DATA"]
    assert data_page._controller.is_bound is True
    assert data_page.overview_values["active_dialogues"].text() == "2"
    assert window._project_data_state.is_dirty("DATA") is False

    window.close()
    qapp.processEvents()
