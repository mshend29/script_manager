from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_startup_goes_directly_to_project_workspace_after_splash() -> None:
    source = _read("main.py")

    assert "window.showMaximized()" in source
    assert "splash.finish(window)" in source
    assert "show_startup_recent_projects" not in source
    assert "QTimer.singleShot" not in source
    assert "Recent Projects dialog" in source


def test_project_home_replaces_startup_recent_dialog_visually() -> None:
    source = _read("pages/project_page.py")

    assert 'self.project_home = self._build_project_home()' in source
    assert 'sidebar.setFixedWidth(230)' in source
    assert 'QPushButton("Create New")' in source
    assert 'QPushButton("Open Project")' in source
    assert 'QLabel("Recent Projects")' in source
    assert '["PROJECT", "LAST OPENED"]' in source
    assert 'setPlaceholderText("Search recent projects…")' in source
    assert "setSortingEnabled(True)" in source
    assert "Qt.SortOrder.DescendingOrder" in source


def test_recent_history_supports_longer_project_home_list() -> None:
    source = _read("core/recent_projects.py")
    assert "RECENT_PROJECTS_LIMIT = 30" in source
