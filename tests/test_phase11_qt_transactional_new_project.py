from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PYSIDE_AVAILABLE = importlib.util.find_spec("PySide6") is not None

pytestmark = pytest.mark.skipif(
    not PYSIDE_AVAILABLE,
    reason="PySide6 is only installed in the Qt runtime CI job.",
)

if PYSIDE_AVAILABLE:
    import app.application_window as application_window_module
    from app.application_window import ApplicationWindow
    from core.project_settings import ProjectSettings
    from import_engine.source_sync import SourceSyncReport


class _FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback) -> None:
        self._callbacks.append(callback)

    def emit(self) -> None:
        for callback in list(self._callbacks):
            callback()


class _FakeDialog:
    instances: list["_FakeDialog"] = []
    submit_count = 1

    def __init__(self, parent=None):
        self.parent = parent
        self.settings = ProjectSettings(
            project_name="Project Retry",
            project_code="PR01",
            client_name="Client",
            start_date="2026-09-07",
        )
        self.parent_folder = "/project-target"
        self.create_requested = _FakeSignal()
        self.exec_count = 0
        self.accepted = False
        self.failure_messages: list[str] = []
        self.success_reports: list[object] = []
        self.__class__.instances.append(self)

    def exec(self) -> int:
        self.exec_count += 1
        for _ in range(self.__class__.submit_count):
            self.create_requested.emit()
            if self.accepted:
                break
        return int(self.accepted)

    def creation_failed(self, error: object) -> None:
        self.failure_messages.append(str(error))

    def creation_succeeded(self, report: object) -> None:
        self.success_reports.append(report)
        self.accepted = True


class _FakeStatusBar:
    def __init__(self):
        self.messages: list[tuple] = []

    def showMessage(self, *args) -> None:  # noqa: N802 - Qt API compatibility
        self.messages.append(tuple(args))


class _FakeWindow:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.project_manager = SimpleNamespace()
        self.source_sync_engine = SimpleNamespace()
        self._project_data_state = SimpleNamespace(
            reset=lambda **kwargs: self.reset_calls.append(kwargs)
        )
        self.reset_calls: list[dict[str, object]] = []
        self.clear_calls = 0
        self.refresh_calls = 0
        self.recent_projects: list[object] = []
        self.window_titles: list[str] = []
        self.pages_shown: list[str] = []
        self.creation_calls = 0
        self._status_bar = _FakeStatusBar()

    def _block_project_change_during_sync(self, _title: str) -> bool:
        return False

    def _start_initial_project_creation(self, dialog) -> None:
        self.creation_calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            self._initial_project_result = None
            dialog.creation_failed(outcome)
            return

        self._initial_project_result = outcome
        dialog.creation_succeeded(
            SourceSyncReport(scanned=1, parsed_dialogues=7)
        )

    def _clear_data_pages(self) -> None:
        self.clear_calls += 1

    def refresh_project_page(self) -> None:
        self.refresh_calls += 1

    def setWindowTitle(self, value: str) -> None:  # noqa: N802
        self.window_titles.append(value)

    def _record_recent_project(self, project) -> None:
        self.recent_projects.append(project)

    def set_page(self, page_name: str) -> None:
        self.pages_shown.append(page_name)

    def statusBar(self):  # noqa: N802
        return self._status_bar


def _project() -> SimpleNamespace:
    return SimpleNamespace(
        project_id="project-1",
        project_file=Path("/project-target/PR01 - Project Retry.smproj"),
        settings=ProjectSettings(
            project_name="Project Retry",
            project_code="PR01",
            client_name="Client",
            start_date="2026-09-07",
        ),
    )


def test_failure_retries_inside_same_wizard_and_records_recent_only_after_success(
    monkeypatch,
):
    _FakeDialog.instances.clear()
    _FakeDialog.submit_count = 2
    project = _project()
    window = _FakeWindow([RuntimeError("disk failure"), project])

    monkeypatch.setattr(
        application_window_module,
        "TransactionalNewProjectDialog",
        _FakeDialog,
    )

    ApplicationWindow.new_project(window)

    assert len(_FakeDialog.instances) == 1
    dialog = _FakeDialog.instances[0]
    assert dialog.exec_count == 1
    assert window.creation_calls == 2
    assert dialog.failure_messages == ["disk failure"]
    assert dialog.success_reports
    assert window.recent_projects == [project]
    assert window.clear_calls == 1
    assert window.refresh_calls == 1
    assert window.pages_shown == ["PROJECT"]


def test_cancel_after_failure_keeps_failed_project_out_of_recent(monkeypatch):
    _FakeDialog.instances.clear()
    _FakeDialog.submit_count = 1
    window = _FakeWindow([RuntimeError("sync failure")])

    monkeypatch.setattr(
        application_window_module,
        "TransactionalNewProjectDialog",
        _FakeDialog,
    )

    ApplicationWindow.new_project(window)

    dialog = _FakeDialog.instances[0]
    assert dialog.exec_count == 1
    assert dialog.failure_messages == ["sync failure"]
    assert window.recent_projects == []
    assert window.clear_calls == 0
    assert window.refresh_calls == 0
    assert window.window_titles == []


def test_success_refreshes_state_records_recent_and_opens_project_dashboard(monkeypatch):
    _FakeDialog.instances.clear()
    _FakeDialog.submit_count = 1
    project = _project()
    window = _FakeWindow([project])

    monkeypatch.setattr(
        application_window_module,
        "TransactionalNewProjectDialog",
        _FakeDialog,
    )

    ApplicationWindow.new_project(window)

    assert window.reset_calls == [{"mark_dirty": True}]
    assert window.window_titles == ["Project Retry - Script Manager"]
    assert window.recent_projects == [project]
    assert window.pages_shown == ["PROJECT"]
    assert window._status_bar.messages[-1] == (
        f"Proyek dibuat dan sumber tersinkron: {project.project_file}",
        5000,
    )
