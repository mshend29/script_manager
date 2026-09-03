from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_project_page_uses_single_phase10_workspace() -> None:
    source = (ROOT / "pages" / "project_page.py").read_text(
        encoding="utf-8"
    )

    assert "class ProjectPage(QWidget)" in source
    assert "ContextPanel" not in source
    assert "PageShell" not in source
    assert '"ProjectWorkspace"' in source
    assert '"ProjectIdentityCard"' in source
    assert '"PROJECT DATA"' in source
    assert '"PRODUCTION PIPELINE"' in source
    assert '"NEEDS ATTENTION"' in source
    assert '"RECENT ACTIVITY"' in source
    assert '"Project Dashboard"' not in source


def test_project_identity_uses_real_metadata_without_fake_media() -> None:
    source = (ROOT / "pages" / "project_page.py").read_text(
        encoding="utf-8"
    )
    main = (ROOT / "app" / "main_window.py").read_text(
        encoding="utf-8"
    )

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
    lowered = source.casefold()
    for value in forbidden:
        assert value not in lowered


def test_project_metrics_keep_existing_dashboard_semantics() -> None:
    source = (ROOT / "pages" / "project_page.py").read_text(
        encoding="utf-8"
    )

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
    source = (ROOT / "pages" / "project_page.py").read_text(
        encoding="utf-8"
    )
    theme = (ROOT / "app" / "theme.py").read_text(encoding="utf-8")

    assert 'button.setProperty("attentionAction", True)' in source
    assert '"dashboardSeverity"' in source
    assert "self.action_requested.emit(key)" in source

    assert 'QPushButton[attentionAction="true"]' in theme
    assert 'dashboardSeverity="ERROR"' in theme
    assert 'dashboardSeverity="WARNING"' in theme
    assert 'dashboardSeverity="INFO"' in theme
