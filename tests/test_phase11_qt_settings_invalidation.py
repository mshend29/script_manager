from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace

import pytest

from core.project_settings import ProjectSettings


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PYSIDE_AVAILABLE = importlib.util.find_spec("PySide6") is not None

pytestmark = pytest.mark.skipif(
    not PYSIDE_AVAILABLE,
    reason="PySide6 is only installed in the Qt runtime CI job.",
)

if PYSIDE_AVAILABLE:
    import app.application_window as application_window_module
    from app.application_window import ApplicationWindow


class _FakeStatusBar:
    def __init__(self) -> None:
        self.messages: list[tuple[object, ...]] = []

    def showMessage(self, *args) -> None:  # noqa: N802 - Qt compatibility
        self.messages.append(tuple(args))


class _FakeDataState:
    def __init__(self) -> None:
        self.dirty: list[str] = []

    def mark_dirty(self, page_name: str) -> None:
        self.dirty.append(page_name)


class _FakeManager:
    def __init__(self, project) -> None:
        self.current = project
        self.updated: list[ProjectSettings] = []

    def update_settings(self, settings: ProjectSettings) -> None:
        self.updated.append(settings)
        self.current.settings = settings.normalized()


class _FakeDialog:
    candidate: ProjectSettings | None = None

    def __init__(self, settings, parent=None) -> None:
        self.result_settings = self.__class__.candidate or settings

    def exec(self) -> int:
        return 1


class _FakeWindow:
    def __init__(self, baseline: ProjectSettings) -> None:
        project = SimpleNamespace(settings=baseline)
        self.project_manager = _FakeManager(project)
        self._project_data_state = _FakeDataState()
        self.tracking_refresh_calls = 0
        self.project_refresh_calls = 0
        self.window_titles: list[str] = []
        self._status_bar = _FakeStatusBar()

    def _block_project_change_during_sync(self, _title: str) -> bool:
        return False

    def refresh_project_page(self) -> None:
        self.project_refresh_calls += 1

    def setWindowTitle(self, title: str) -> None:  # noqa: N802
        self.window_titles.append(title)

    def statusBar(self):  # noqa: N802
        return self._status_bar

    def _invalidate_source_dependent_workspace(self) -> None:
        ApplicationWindow._invalidate_source_dependent_workspace(self)

    def _refresh_tracking_files_state(self) -> None:
        self.tracking_refresh_calls += 1


def _baseline(tmp_path) -> ProjectSettings:
    return ProjectSettings(
        project_name="Existing",
        project_code="EX01",
        client_name="Client",
        start_date="2026-09-07",
        source_folder=str(tmp_path / "source-a"),
        episode_before="EP",
        episode_after="_",
        stem_output_folder=str(tmp_path / "stem-a"),
        delivery_folder=str(tmp_path / "delivery-a"),
        main_drive_url="https://example.com/old",
    )


def _run(monkeypatch, window: _FakeWindow, candidate: ProjectSettings) -> None:
    _FakeDialog.candidate = candidate
    monkeypatch.setattr(
        application_window_module,
        "ProjectSettingsDialog",
        _FakeDialog,
    )
    ApplicationWindow.open_project_settings(window)


def test_source_change_invalidates_all_source_dependent_workspaces(monkeypatch, tmp_path):
    baseline = _baseline(tmp_path)
    candidate = ProjectSettings.from_dict(baseline.to_dict())
    candidate.source_folder = str(tmp_path / "source-b")
    window = _FakeWindow(baseline)

    _run(monkeypatch, window, candidate)

    assert window._project_data_state.dirty == [
        "SCRIPT",
        "DIALOG",
        "TRACKING",
        "DELIVERY",
        "DATA",
    ]
    assert window.tracking_refresh_calls == 0
    assert "F5" in str(window._status_bar.messages[-1][0])


def test_tracking_configuration_change_reuses_filesystem_refresh(monkeypatch, tmp_path):
    baseline = _baseline(tmp_path)
    candidate = ProjectSettings.from_dict(baseline.to_dict())
    candidate.audio_channels = 2
    window = _FakeWindow(baseline)

    _run(monkeypatch, window, candidate)

    assert window._project_data_state.dirty == []
    assert window.tracking_refresh_calls == 1
    assert "Tracking/Delivery" in str(window._status_bar.messages[-1][0])


def test_link_only_change_does_not_invalidate_source_or_filesystem(monkeypatch, tmp_path):
    baseline = _baseline(tmp_path)
    candidate = ProjectSettings.from_dict(baseline.to_dict())
    candidate.main_drive_url = "https://example.com/new"
    window = _FakeWindow(baseline)

    _run(monkeypatch, window, candidate)

    assert window._project_data_state.dirty == []
    assert window.tracking_refresh_calls == 0
    assert window.project_refresh_calls == 1
    assert window.project_manager.updated == [candidate]
    assert window._status_bar.messages[-1][0] == "Pengaturan proyek tersimpan"
