from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_episode_chip_only_shows_number_and_uses_compact_fixed_size():
    source = _read("widgets/episode_chip.py")

    assert 'self.setText(str(chip.episode_number))' in source
    assert 'self.setText(f"EP ' not in source
    assert "self.setFixedSize(46, 34)" in source
    assert "border-radius: 9px" in source
    assert "detail_requested" in source
    assert "detail di ribbon" in source


def test_tracking_workspace_wraps_episode_chips_without_horizontal_scroll():
    source = _read("pages/tracking_page.py")

    assert 'QLabel("TOKOH")' in source
    assert 'QLabel("EPISODE")' in source
    assert "QGridLayout(self.rows_container)" in source
    assert "FlowLayout(episode_holder" in source
    assert "ScrollBarAlwaysOff" in source
    assert "setMinimumWidth(250 +" not in source
    assert "EpisodeChipButton(chip)" in source
    assert "detail_requested.connect(self._select_episode_detail)" in source


def test_tracking_sidebar_has_talent_scoped_episode_nav_and_character_status_columns():
    source = _read("pages/tracking_page.py")

    assert "get_episodes_for_talent(int(talent_id))" in source
    assert 'QPushButton("‹ Prev")' in source
    assert 'QPushButton("Next ›")' in source
    assert "_select_adjacent_episode(-1)" in source
    assert "_select_adjacent_episode(1)" in source
    assert "if index < 0 and episodes:" in source
    assert "index = 1" in source
    assert "status_palette(status)" in source
    assert 'setHorizontalHeaderLabels(["TOKOH", "STATUS"])' in source
    assert "status_item.setBackground" in source
    assert "status_item.setForeground" in source


def test_tracking_detail_and_status_controls_live_in_ribbon_and_autosave():
    ribbon = _read("app/ribbon.py")
    tracking = _read("pages/tracking_page.py")

    assert "class TrackingDetailGroup" in ribbon
    assert 'QLabel("Ubah status:")' in ribbon
    assert 'self.status_combo.addItem("Auto (Recording Status)"' in ribbon
    assert 'self.status_combo.addItem("Ready to Stem"' in ribbon
    assert 'self.status_combo.addItem("Stemmed"' in ribbon
    assert 'self.status_combo.addItem("Delivered"' in ribbon
    assert 'self.status_combo.addItem("Revision"' in ribbon
    assert "self.status_change_requested.emit(str(status))" in ribbon
    assert "tracking_status_change_requested" in ribbon
    assert "set_tracking_detail" in ribbon

    assert "TrackingEpisodeDialog" not in tracking
    assert "dialog.exec()" not in tracking
    assert "tracking_detail_changed.connect(ribbon.set_tracking_detail)" in tracking
    assert "ribbon.tracking_status_change_requested.connect" in tracking
    assert "self._service.set_downstream_status(" in tracking
    assert "self._refresh_selected_detail()" in tracking
