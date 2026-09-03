from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_tracking_keeps_compact_matrix_as_primary_workspace() -> None:
    base = _read("pages/tracking_page.py")
    compact = _read("pages/tracking_compact_page.py")
    chip = _read("widgets/episode_chip.py")

    assert "FlowLayout(episode_holder" in base
    assert "EpisodeChipButton(chip)" in base
    assert "self.setFixedSize(46, 34)" in chip
    assert '"TrackingGridWorkspace"' in compact
    assert "matrix_layout.addWidget(self.scroll, 1)" in compact

    assert "context.hide()" in compact
    assert '"TrackingFilterBar"' in compact
    assert '"TrackingLegendBar"' in compact
    assert '"TrackingWorkspaceTabs"' in compact


def test_tracking_filters_and_legend_are_compact_and_visible() -> None:
    base = _read("pages/tracking_page.py")
    compact = _read("pages/tracking_compact_page.py")

    status_order = base.split("STATUS_ORDER = (", 1)[1].split(")", 1)[0]
    assert "READY_TO_STEM" not in status_order
    assert 'QLabel("Talent")' in compact
    assert 'QLabel("Episode")' in compact
    assert "self.status_legend_widget" in compact
    assert "for status in STATUS_ORDER:" in compact
    assert "self._status_legend_label(status)" in compact

    assert "self.talent_combo.setMinimumWidth(170)" in compact
    assert "self.episode_combo.setMinimumWidth(132)" in compact
    assert 'setProperty("trackingNav", True)' in compact


def test_tracking_footer_stays_secondary_to_episode_matrix() -> None:
    compact = _read("pages/tracking_compact_page.py")

    assert '"TrackingQueuePanel"' in compact
    assert '"TrackingHealthStrip"' in compact
    assert 'QLabel("TRACKS TO STEM")' in compact
    assert "self.character_table.setMaximumHeight(112)" not in compact
    assert 'QPushButton("Go to Output Health")' in compact
    assert "body.addWidget(queue_panel)" in compact
    assert "queue_layout.addWidget(self.output_health_summary, 0)" in compact


def test_tracking_status_palette_uses_shared_semantic_tokens() -> None:
    theme = _read("app/theme.py")
    chip = _read("widgets/episode_chip.py")
    compact = _read("pages/tracking_compact_page.py")

    for token in (
        "recorded",
        "stemmed",
        "delivered",
        "revision",
        "attention",
        "neutral",
    ):
        assert f'COLORS["{token}"]' in chip or f'"{token}":' in theme

    assert 'from app.theme import COLORS' in chip
    assert 'from app.theme import COLORS' in compact
    assert 'QColor("#9a5a00")' not in compact
    assert 'QColor("#176b2c")' not in compact
    assert 'QColor("#FFF4CE")' not in compact


def test_tracking_remains_text_first_without_avatar_or_episode_cards() -> None:
    sources = (
        _read("pages/tracking_page.py")
        + _read("pages/tracking_compact_page.py")
    ).casefold()

    for forbidden in (
        "avatar",
        "portrait",
        "talent photo",
        "character photo",
    ):
        assert forbidden not in sources

    assert "large episode card" not in sources
