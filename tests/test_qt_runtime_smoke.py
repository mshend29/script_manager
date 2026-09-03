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
            project_code="QT",
            client_name="Test Client",
            source_folder=str(source),
            episode_before="第",
            episode_after="集",
            main_drive_url="https://drive.google.com/example",
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

    project_page = window.pages["PROJECT"]
    assert project_page.project_name.text() == "Qt Runtime"
    assert project_page.project_identity.text() == "QT  •  Test Client"
    assert project_page.drive_status.text() == "Main drive: Configured"
    assert project_page.empty_action_bar.isHidden()
    assert project_page.episodes_card.value_label.text() == "1"
    assert project_page.dialogues_card.value_label.text() == "1"

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

    dialog_page.talent_combo.setCurrentIndex(
        dialog_page.talent_combo.findText("Brama")
    )
    qapp.processEvents()
    dialog_page.character_combo.setCurrentIndex(
        dialog_page.character_combo.findText("Hendra")
    )
    qapp.processEvents()
    dialog_page.episode_combo.setCurrentIndex(
        dialog_page.episode_combo.findData(1)
    )
    qapp.processEvents()

    assert dialog_page.table.rowCount() == 1
    assert "0/1 recorded" in dialog_page.selection_info.text()

    dialog_page.search_edit.setText("not present")
    qapp.processEvents()
    assert dialog_page.table.isRowHidden(0)

    dialog_page.search_edit.setText("Halo")
    qapp.processEvents()
    assert not dialog_page.table.isRowHidden(0)

    dialog_page.set_all_checked(True)
    qapp.processEvents()
    assert next(iter(dialog_page._checkboxes.values())).isChecked()
    assert "1/1 recorded" in dialog_page.selection_info.text()

    window.resize(1100, 700)
    window.set_page("TRACKING")
    qapp.processEvents()

    tracking_page = window.pages["TRACKING"]
    assert window._project_data_state.is_dirty("TRACKING") is False
    assert tracking_page.layout().itemAt(0).widget().isHidden()
    assert tracking_page.character_table.maximumHeight() == 112
    assert tracking_page.status_legend_widget is not None
    assert tracking_page.tracking_workspace_stack.currentIndex() == 0

    talent_index = tracking_page.talent_combo.findText("Brama")
    assert talent_index > 0
    tracking_page.talent_combo.setCurrentIndex(talent_index)
    qapp.processEvents()

    episode_index = tracking_page.episode_combo.findData(1)
    assert episode_index > 0
    tracking_page.episode_combo.setCurrentIndex(episode_index)
    qapp.processEvents()

    assert tracking_page.episode_combo.currentData() == 1
    assert len(tracking_page._workspace_rows) == 1
    assert tracking_page._workspace_rows[0].character_name == "Hendra"
    assert len(tracking_page._workspace_rows[0].chips) == 1

    window.set_page("DATA")
    qapp.processEvents()

    data_page = window.pages["DATA"]
    assert data_page._controller.is_bound is True
    assert data_page.overview_values["active_dialogues"].text() == "2"
    assert window._project_data_state.is_dirty("DATA") is False

    window.close()
    qapp.processEvents()
