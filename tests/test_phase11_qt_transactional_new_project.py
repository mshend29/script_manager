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


class _FakeDialog:
    instances: list["_FakeDialog"] = []
    exec_results: list[int] = []

    def __init__(self, parent=None):
        self.parent = parent
        self.settings = ProjectSettings(
            project_name="Project Retry",
            project_code="PR01",
            client_name="Client",
            start_date="2026-09-06",
        )
        self.parent_folder = "/project-target"
        self.exec_count = 0
        self.review_refresh_count = 0
        self.__class__.instances.append(self)

    def exec(self) -> int:
        self.exec_count += 1
        return self.__class__.exec_results.pop(0)

    def _refresh_review(self) -> None:
        self.review_refresh_count += 1


class _FakeStatusBar:
    def __init__(self):
        self.messages: list[tuple] = []

    def showMessage(self, *args) -> None:  # noqa: N802 - Qt API compatibility
        self.messages.append(tuple(args))


class _FakeProjectManager:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls: list[tuple[ProjectSettings, str]] = []

    def create_transactional(self, settings, parent_folder):
        self.calls.append((settings, parent_folder))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class _FakeWindow:
    def __init__(self, manager):
        self.project_manager = manager
        self._project_data_state = SimpleNamespace(
            reset=lambda **kwargs: self.reset_calls.append(kwargs)
        )
        self.reset_calls: list[dict[str, object]] = []
        self.clear_calls = 0
        self.refresh_calls = 0
        self.recent_projects: list[object] = []
        self.window_titles: list[str] = []
        self._status_bar = _FakeStatusBar()

    def _block_project_change_during_sync(self, _title: str) -> bool:
        return False

    def _clear_data_pages(self) -> None:
        self.clear_calls += 1

    def refresh_project_page(self) -> None:
        self.refresh_calls += 1

    def setWindowTitle(self, value: str) -> None:  # noqa: N802
        self.window_titles.append(value)

    def _record_recent_project(self, project) -> None:
        self.recent_projects.append(project)

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
            start_date="2026-09-06",
        ),
    )


def test_create_failure_reopens_same_wizard_and_does_not_record_recent(monkeypatch):
    _FakeDialog.instances.clear()
    _FakeDialog.exec_results = [1, 0]
    manager = _FakeProjectManager([RuntimeError("disk failure")])
    window = _FakeWindow(manager)
    errors: list[str] = []

    monkeypatch.setattr(application_window_module, "NewProjectDialog", _FakeDialog)
    monkeypatch.setattr(
        application_window_module.QMessageBox,
        "critical",
        lambda _parent, _title, message: errors.append(str(message)),
    )

    ApplicationWindow.new_project(window)

    assert len(_FakeDialog.instances) == 1
    dialog = _FakeDialog.instances[0]
    assert dialog.exec_count == 2
    assert dialog.review_refresh_count == 1
    assert len(manager.calls) == 1
    assert manager.calls[0][0] is dialog.settings
    assert manager.calls[0][1] == dialog.parent_folder
    assert errors and "disk failure" in errors[0]
    assert window.recent_projects == []
    assert window.clear_calls == 0
    assert window.refresh_calls == 0
    assert window.window_titles == []


def test_success_records_recent_only_after_transaction(monkeypatch):
    _FakeDialog.instances.clear()
    _FakeDialog.exec_results = [1]
    project = _project()
    manager = _FakeProjectManager([project])
    window = _FakeWindow(manager)

    monkeypatch.setattr(application_window_module, "NewProjectDialog", _FakeDialog)

    ApplicationWindow.new_project(window)

    assert len(_FakeDialog.instances) == 1
    assert _FakeDialog.instances[0].exec_count == 1
    assert window.clear_calls == 1
    assert window.reset_calls == [{"mark_dirty": True}]
    assert window.refresh_calls == 1
    assert window.window_titles == ["Project Retry - Script Manager"]
    assert window.recent_projects == [project]
    assert window._status_bar.messages[-1] == (
        f"Proyek dibuat: {project.project_file}",
        5000,
    )
