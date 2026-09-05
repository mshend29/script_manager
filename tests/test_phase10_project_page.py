from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_project_workspace_has_home_and_preserved_dashboard() -> None:
    home = _read("pages/project_page.py")
    dashboard = _read("pages/project_dashboard_page.py")

    assert "class ProjectPage(DashboardProjectPage)" in home
    assert '"ProjectHome"' in home
    assert '"ProjectHomeSidebar"' in home
    assert 'QPushButton("Create New")' in home
    assert 'QPushButton("Open Project")' in home
    assert 'QLabel("Recent Projects")' in home
    assert '["PROJECT", "LAST OPENED"]' in home
    assert "self.show_home()" in home
    assert "self.show_dashboard()" in home

    assert "class ProjectPage(QWidget)" in dashboard
    assert "ContextPanel" not in dashboard
    assert "PageShell" not in dashboard
    assert '"ProjectWorkspace"' in dashboard
    assert '"ProjectIdentityCard"' in dashboard
    assert '"PROJECT DATA"' in dashboard
    assert '"PRODUCTION PIPELINE"' in dashboard
    assert '"NEEDS ATTENTION"' in dashboard
    assert '"RECENT ACTIVITY"' in dashboard


def test_project_home_recent_list_supports_search_sort_and_open() -> None:
    source = _read("pages/project_page.py")

    assert 'setPlaceholderText("Search recent projects…")' in source
    assert "textChanged.connect(self._filter_recent_projects)" in source
    assert "setSortingEnabled(True)" in source
    assert "setSectionsClickable(True)" in source
    assert "setSortIndicatorShown(True)" in source
    assert "Qt.SortOrder.DescendingOrder" in source
    assert "itemDoubleClicked.connect(" in source
    assert "itemActivated.connect(" in source
    assert 'getattr(self.window(), "open_project_path", None)' in source
    assert "existing_only=False" in source


def test_project_identity_uses_real_metadata_without_fake_media() -> None:
    source = _read("pages/project_dashboard_page.py")
    main = _read("app/main_window.py")

    assert "def set_project_metadata(" in source
    assert "project_code" in source
    assert "client_name" in source
    assert "drive_configured" in source
    assert "settings.project_code" in main
    assert "settings.client_name" in main
    assert "settings.main_drive_url" in main
    assert 'f"Source folder: {settings.source_folder or \'-\'}"' in main
    assert 'f"Last sync: {last_sync or \'-\'}"' in main

    forbidden = (
        "avatar",
        "poster",
        "profile photo",
        "talent photo",
        "online presence",
    )
    lowered = (source + _read("pages/project_page.py")).casefold()
    for value in forbidden:
        assert value not in lowered


def test_project_metrics_keep_existing_dashboard_semantics() -> None:
    source = _read("pages/project_dashboard_page.py")

    for attribute in (
        "episodes_card",
        "dialogues_card",
        "characters_card",
        "talents_card",
        "review_card",
        "recording_card",
        "stem_card",
        "delivery_card",
        "revision_card",
        "warning_card",
    ):
        assert f"self.{attribute}" in source

    assert "snapshot.recording_episodes" in source
    assert "snapshot.recorded_waiting_stem" in source
    assert "snapshot.stemmed_waiting_delivery" in source
    assert "snapshot.delivered_tracks" in source
    assert "snapshot.total_tracks" in source
    assert "snapshot.revisions" in source
    assert "snapshot.actions" in source
    assert "snapshot.recent_activity" in source


def test_needs_attention_uses_dashboard_severity_and_existing_action_keys() -> None:
    source = _read("pages/project_dashboard_page.py")
    theme = _read("app/theme.py")

    assert 'button.setProperty("attentionAction", True)' in source
    assert '"dashboardSeverity"' in source
    assert "self.action_requested.emit(key)" in source

    assert 'QPushButton[attentionAction="true"]' in theme
    assert 'dashboardSeverity="ERROR"' in theme
    assert 'dashboardSeverity="WARNING"' in theme
    assert 'dashboardSeverity="INFO"' in theme
