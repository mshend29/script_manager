from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_project_workspace_has_home_and_preserved_dashboard() -> None:
    home = _read("pages/project_page.py")
    dashboard = _read("pages/project_dashboard_page.py")

    assert "class ProjectPage(DashboardProjectPage)" in home
    assert "ProjectHome" in home
    assert "ProjectHomeSidebar" in home
    for label in (
        "Buat Baru",
        "Buka Proyek",
        "Proyek Terbaru",
        "PROYEK",
        "TERAKHIR DIBUKA",
    ):
        assert label in home
    assert "self.show_home()" in home
    assert "self.show_dashboard()" in home

    assert "class ProjectPage(QWidget)" in dashboard
    assert "ContextPanel" not in dashboard
    assert "PageShell" not in dashboard
    for token in (
        "ProjectWorkspace",
        "ProjectIdentityCard",
        "DATA PROYEK",
        "ALUR PRODUKSI",
        "PERLU PERHATIAN",
        "AKTIVITAS TERBARU",
    ):
        assert token in dashboard


def test_project_dashboard_uses_production_flow_instead_of_card_matrix() -> None:
    source = _read("pages/project_dashboard_page.py")

    assert "ProjectMetricStrip" in source
    assert "ProjectPipelineRail" in source
    assert "ProjectRevisionLoop" in source
    assert "→" in source
    assert "self.delivery_progress = QProgressBar()" in source
    assert "self.pipeline_progress_text" in source
    assert "snapshot.delivered_tracks / snapshot.total_tracks" not in source
    assert "delivered_tracks / total_tracks" in source

    # Project metrics live in one strip; the production flow is not rebuilt as
    # another QGridLayout of equal bordered cards.
    assert "def _build_metric_strip" in source
    assert "def _build_pipeline_rail" in source
    assert 'role="pipeline"' in source
    assert 'role="revision"' in source

    # Perlu Perhatian is deliberately a vertical work queue, while activity is
    # a lightweight timeline instead of another heavy dashboard card.
    assert "self.action_layout.addWidget(button, index, 0)" in source
    assert "ProjectActivityPanel" in source
    assert "ProjectActivityDot" in source


def test_project_dashboard_after_hero_uses_weighted_two_columns() -> None:
    source = _read("pages/project_dashboard_page.py")

    assert "ProjectDashboardColumns" in source
    assert "ProjectProductionColumn" in source
    assert "ProjectMonitoringColumn" in source
    assert "dashboard_columns.setColumnStretch(0, 13)" in source
    assert "dashboard_columns.setColumnStretch(1, 7)" in source

    # Left side owns the project metrics and production flow.
    assert "production_layout.addWidget(self._build_metric_strip())" in source
    assert "production_layout.addWidget(self._build_pipeline_rail())" in source

    # Right side stacks operator attention above the activity timeline.
    assert "monitoring_layout.addWidget(self.attention_panel)" in source
    assert "monitoring_layout.addWidget(self.activity_frame, 1)" in source


def test_project_home_recent_list_supports_search_sort_and_open() -> None:
    source = _read("pages/project_page.py")

    assert "Cari proyek terbaru…" in source
    assert "textChanged.connect(self._filter_recent_projects)" in source
    assert "setSortingEnabled(True)" in source
    assert "setSectionsClickable(True)" in source
    assert "setSortIndicatorShown(True)" in source
    assert "Qt.SortOrder.DescendingOrder" in source
    assert "itemClicked.connect(self._open_recent_item)" in source
    assert "itemDoubleClicked.connect(" not in source
    assert "QAbstractItemView.SelectionMode.NoSelection" in source
    assert "open_project_path" in source
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
    assert "Folder sumber:" in main
    assert "Sinkron terakhir:" in main

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
