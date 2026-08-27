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
    assert "Status: {chip.status_label}" in source
    assert "detail dan menu aksi" in source


def test_episode_chip_has_go_to_dialog_menu_with_exact_cast_filters():
    source = _read("widgets/episode_chip.py")

    assert "QMenu" in source
    assert 'addAction("Go to Dialog")' in source
    assert "self._action_menu.popup(" in source
    assert 'ribbon.select_tab("DIALOG")' in source
    assert "dialog_page.reload(" in source
    assert "preferred_talent_id=self.chip.talent_id" in source
    assert "preferred_character_id=self.chip.character_id" in source
    assert "preferred_episode=self.chip.episode_number" in source


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


def test_tracking_detail_shares_action_row_and_revision_is_only_manual_control():
    ribbon = _read("app/ribbon.py")
    tracking = _read("pages/tracking_page.py")
    compact = _read("pages/tracking_compact_page.py")

    assert "class TrackingDetailGroup" in ribbon
    assert 'QPushButton("Mark Revision")' in ribbon
    assert '"Clear Revision"' in ribbon
    assert "status_palette(REVISION)" in ribbon
    assert "self._set_status_card(chip.display_status)" in ribbon
    assert "self.status_change_requested.emit(requested)" in ribbon
    assert "tracking_status_change_requested" in ribbon
    assert "set_tracking_detail" in ribbon

    # Automatic statuses are no longer exposed as manual ribbon buttons.
    assert 'QPushButton(STATUS_LABELS[status])' not in ribbon
    assert "READY_TO_STEM" not in ribbon
    assert "STEMMED" not in ribbon
    assert "DELIVERED" not in ribbon

    # TRACKING detail remains on the same horizontal ribbon row.
    assert 'if tab_name == "TRACKING":' in ribbon
    assert "row = QHBoxLayout(page)" in ribbon
    assert "row.addWidget(self.tracking_detail_group, 1)" in ribbon

    assert "TrackingEpisodeDialog" not in tracking
    assert "tracking_detail_changed.connect(ribbon.set_tracking_detail)" in tracking
    assert "ribbon.tracking_status_change_requested.connect" in tracking
    assert "self._service.set_downstream_status(" in tracking

    # Talent summary shares the workspace header and file inventory sits below
    # the character/episode grid.
    assert "header_row.addWidget(self.title_label)" in tracking
    assert "header_row.addWidget(self.summary_label, 1)" in tracking
    assert 'QLabel("TRACK FILES")' in compact
    assert '["TRACK SUGGESTION", "STEM / EXPORT", "DELIVERED"]' in compact
    assert 'QLabel("OUTPUT HEALTH")' in compact

