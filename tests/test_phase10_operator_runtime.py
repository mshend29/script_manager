from __future__ import annotations

import importlib.util
import os
import time

from openpyxl import Workbook
import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PYSIDE_AVAILABLE = importlib.util.find_spec("PySide6") is not None

pytestmark = pytest.mark.skipif(
    not PYSIDE_AVAILABLE,
    reason="PySide6 is only installed in the Qt runtime CI job.",
)

if PYSIDE_AVAILABLE:
    from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

    import app.main_window as main_window_module
    from app.main_window import MainWindow
    from core.project import Project
    from core.project_settings import ProjectSettings
    from import_engine.source_sync import SourceSyncEngine


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

    _write_source(
        source / "AA23-第1集_中文.xlsx",
        episode=1,
        dialogue="Halo",
    )

    project = Project(
        file_path=tmp_path / "phase10-operator.smproj",
        settings=ProjectSettings(
            project_name="Phase 10 Operator",
            project_code="P10",
            client_name="Runtime Test",
            source_folder=str(source),
            episode_before="第",
            episode_after="集",
        ),
        project_id="phase10-operator-runtime",
    )
    project.save()
    return project, source


def _wait_until(qapp, predicate, *, timeout: float = 12.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for Qt runtime condition.")


def test_bottom_workspace_navigation_project_dialog_tracking(qapp) -> None:
    window = MainWindow()
    window.show()
    qapp.processEvents()

    for page_name, title in (
        ("PROJECT", "Project"),
        ("DIALOG", "Dialog"),
        ("TRACKING", "Tracking"),
    ):
        window.workspace_nav._buttons[page_name].click()
        qapp.processEvents()
        assert window.page_stack.currentWidget() is window.pages[page_name]
        assert window.workspace_nav._buttons[page_name].isChecked()

    window.close()
    qapp.processEvents()


def test_header_sync_source_runs_prepare_apply_and_lazy_refresh(
    qapp,
    tmp_path,
    monkeypatch,
) -> None:
    project, source = _project(tmp_path)
    initial = SourceSyncEngine().synchronize(project)
    assert not initial.has_errors

    window = MainWindow()
    assert window.open_project_path(
        project.project_file,
        show_errors=False,
    )
    window.show()
    window.set_page("PROJECT")
    qapp.processEvents()

    script_page = window.pages["SCRIPT"]
    assert window._project_data_state.is_dirty("SCRIPT") is True

    _write_source(
        source / "AA23-第2集_中文.xlsx",
        episode=2,
        dialogue="Episode dua dari Sync Source UI",
    )

    class AutoAcceptPreview:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 1

    monkeypatch.setattr(
        main_window_module,
        "SourceRefreshPreviewDialog",
        AutoAcceptPreview,
    )
    monkeypatch.setattr(
        main_window_module.QMessageBox,
        "information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )

    before_revision = window._project_data_state.revision
    window.sync_source()

    _wait_until(
        qapp,
        lambda: (
            window._project_data_state.revision > before_revision
            and not window.source_sync_controller.is_running
        ),
    )

    # PROJECT is the visible page during Apply, so data workspaces stay
    # revision-dirty until the operator opens them.
    assert window._project_data_state.is_dirty("SCRIPT") is True

    window.workspace_nav._buttons["SCRIPT"].click()
    qapp.processEvents()

    assert window.page_stack.currentWidget() is window.pages["SCRIPT"]
    assert window._project_data_state.is_dirty("SCRIPT") is False
    assert script_page.table_model.rowCount() == 2
    assert script_page.episode_combo.findData(2) >= 0

    window.close()
    qapp.processEvents()
