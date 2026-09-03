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
    assert "def open_dialog_scope(" in source
    assert 'set_page("DIALOG")' in source
    assert "dialog_page.reload(" in source
    assert "preferred_talent_id=chip.talent_id" in source
    assert "preferred_character_id=chip.character_id" in source
    assert "preferred_episode=chip.episode_number" in source
    assert "open_dialog_scope(self.window(), self.chip)" in source
    assert 'getattr(window, "ribbon", None)' not in source


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


def test_tracking_column_headers_stay_outside_scroll_area():
    tracking = _read("pages/tracking_page.py")
    compact = _read("pages/tracking_compact_page.py")

    assert 'self.grid_header = QFrame()' in tracking
    assert 'self.character_header_label = QLabel("TOKOH")' in tracking
    assert 'self.episode_header_label = QLabel("EPISODE")' in tracking
    reset = tracking.split("def _reset_tracking_grid", 1)[1].split(
        "def _refresh_workspace", 1
    )[0]
    assert 'QLabel("TOKOH")' not in reset
    assert 'QLabel("EPISODE")' not in reset
    assert "matrix_layout.addWidget(self.grid_header)" in compact
    assert "matrix_layout.addWidget(self.scroll, 1)" in compact


def test_tracking_episode_popup_is_compact_and_screen_aware():
    tracking = _read("pages/tracking_page.py")

    assert "class TrackingEpisodeComboBox(QComboBox)" in tracking
    assert "MAX_VISIBLE_EPISODES = 8" in tracking
    assert "MAX_POPUP_HEIGHT = 250" in tracking
    assert "QTimer.singleShot(0, self._position_popup)" in tracking
    assert "self.screen().availableGeometry()" in tracking
    assert "popup.move(x, y)" in tracking
    assert "self.episode_combo = TrackingEpisodeComboBox()" in tracking


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


def test_tracking_detail_bar_preserves_revision_as_only_manual_status_control():
    tracking = _read("pages/tracking_page.py")
    compact = _read("pages/tracking_compact_page.py")

    assert '"TrackingDetailBar"' in compact
    assert 'QPushButton("Mark Revision")' in compact
    assert '"Clear Revision"' in compact
    assert 'setProperty("trackingRevisionAction", True)' in compact
    assert "tracking_detail_changed.connect(" in compact
    assert "self._update_tracking_detail_bar" in compact
    assert "def _tracking_revision_clicked" in compact
    assert "NOT_READY" in compact
    assert "REVISION" in compact
    assert "self.apply_selected_status(requested)" in compact

    # Automatic file/recording-derived statuses remain non-manual.
    assert 'QPushButton(STATUS_LABELS[status])' not in compact
    assert "self._service.set_downstream_status(" in tracking
    assert 'getattr(window, "ribbon", None)' not in tracking
    assert "tracking_status_change_requested" not in tracking

    # Talent summary stays compact while file tools remain dedicated workspaces.
    assert "header_row.addWidget(self.summary_label, 1)" in tracking
    assert 'QLabel("TRACK FILES")' in compact
    assert '["TRACK SUGGESTION", "STEM / EXPORT", "DELIVERED"]' in compact
    assert 'QLabel("OUTPUT HEALTH")' in compact



def test_delivery_hides_tracking_only_controls_and_matrix():
    delivery = _read("pages/delivery_page.py")

    assert "self.grid_header.hide()" in delivery
    assert "self.scroll.hide()" in delivery
    assert "self.summary_label.hide()" in delivery
    assert "self.episode_combo.hide()" in delivery
    assert "self.prev_episode_button.hide()" in delivery
    assert "self.next_episode_button.hide()" in delivery
    assert "filter_layout.addWidget(self.talent_combo)" in delivery
    assert "self.rename_episode_button.hide()" in delivery

    build = delivery.split("def _build_tracking_workspaces", 1)[1].split(
        "def show_workspace", 1
    )[0]
    assert 'QLabel("Episode")' not in build
    assert "filter_layout.addWidget(self.summary_label" not in build


def test_delivery_owns_track_files_and_output_health_workspaces():
    compact = _read("pages/tracking_compact_page.py")
    delivery = _read("pages/delivery_page.py")
    main = _read("app/main_window.py")

    assert 'WORKSPACE_TRACKING = "tracking"' in compact
    assert 'WORKSPACE_TRACK_FILES = "track_files"' in compact
    assert 'WORKSPACE_OUTPUT_HEALTH = "output_health"' in compact
    assert "class DeliveryPage(CompactTrackingPage)" in delivery
    assert '(WORKSPACE_TRACK_FILES, "Track Files")' in delivery
    assert '(WORKSPACE_OUTPUT_HEALTH, "Output Health")' in delivery
    assert '"DeliveryWorkspaceStack"' in delivery
    assert '"DELIVERY": DeliveryPage()' in main

    # Output workflow dashboard actions route to Delivery, while Revision
    # continues to route to Tracking.
    assert 'self.set_page("DELIVERY")' in main
    assert 'page.show_workspace(' in main
    assert 'self.set_page("TRACKING")' in main


def test_track_name_suggestion_is_single_scroll_column_without_pagination():
    compact = _read("pages/tracking_compact_page.py")

    assert 'QLabel("TRACK NAME SUGGESTION")' in compact
    assert "str(row.character_name).upper()" in compact
    assert "self.track_name_scroll = QScrollArea()" in compact
    assert "self.track_name_grid.addWidget(button, index, 0)" in compact
    assert "TRACK_NAMES_PER_COLUMN" not in compact
    assert "TRACK_NAME_COLUMNS" not in compact
    assert "TRACK_NAMES_PER_PAGE" not in compact
    assert "track_name_prev" not in compact
    assert "track_name_next" not in compact
    assert "track_name_page_label" not in compact
    assert "QApplication.clipboard().setText" in compact
    assert "QToolTip.showText" in compact
    assert 'f"Copied: {text}"' in compact
    assert "Aliases:" in compact


def test_track_files_layout_uses_twenty_eighty_split():
    compact = _read("pages/tracking_compact_page.py")

    assert "body.setStretchFactor(0, 1)" in compact
    assert "body.setStretchFactor(1, 4)" in compact
    assert "body.setSizes([220, 880])" in compact
    assert "suggestion_panel.setMinimumWidth(190)" in compact


def test_output_health_workspace_explains_episode_counts_and_warning_details():
    compact = _read("pages/tracking_compact_page.py")

    assert 'QLabel("OUTPUT SUMMARY")' in compact
    assert 'QLabel("EPISODE STATUS")' in compact
    assert 'QLabel("WARNINGS")' in compact
    assert '["EPS", "STEM", "DELIVERY", "WARNING"]' in compact
    assert '["TYPE", "EPS", "CHARACTER", "FILE", "MESSAGE"]' in compact
    assert '"Expected Tracks"' in compact
    assert '"Valid Stem"' in compact
    assert '"Valid Delivery"' in compact
    assert "warning.message" in compact


def test_track_files_workspace_exposes_safe_expected_filename_rename_actions():
    compact = _read("pages/tracking_compact_page.py")
    dialog = _read("dialogs/track_rename_preview_dialog.py")
    service = _read("services/track_rename_service.py")

    assert 'QPushButton("Match & Rename Episode")' in compact
    assert 'QPushButton("Batch Match & Rename Talent")' in compact
    assert '"Match / Rename Stem / Export…"' in compact
    assert "cellDoubleClicked.connect" in compact
    assert "TrackRenamePreviewDialog" in compact
    assert "self._track_rename_service.execute(plan)" in compact

    assert '"CURRENT", "EXPECTED", "STATUS"' in dialog
    assert "Tidak ada file yang akan" in dialog
    assert "ditimpa" in dialog
    assert "self.rename_button.setEnabled(count > 0)" in dialog

    assert "RENAME_COLLISION" in service
    assert "RENAME_AMBIGUOUS" in service
    assert "source.rename(target)" in service
    assert "target.exists()" in service
    assert "for source, target in reversed(completed):" in service


def test_output_health_turns_simple_exports_into_actionable_rename_recommendations():
    compact = _read("pages/tracking_compact_page.py")

    assert '"RENAME_RECOMMENDED"' in compact
    assert "parse_simple_export_filename" in compact
    assert "_rename_recommendations_by_source" in compact
    assert "Current:" in compact
    assert "Expected:" in compact
    assert "_output_warning_double_clicked" in compact


def test_unmatched_episode_exports_remain_visible_and_can_be_manually_mapped():
    compact = _read("pages/tracking_compact_page.py")
    dialog = _read("dialogs/track_rename_preview_dialog.py")
    service = _read("services/track_rename_service.py")

    assert '"UNMATCHED EXPORT"' in compact
    assert '"AMBIGUOUS EXPORT"' in compact
    assert "unmatched_items = [" in compact
    assert "item.character_id is None" in compact
    assert "Double-click Stem / Export" in compact

    assert "QComboBox" in dialog
    assert '"Choose expected…"' in dialog
    assert "_manual_choice_changed" in dialog
    assert "assign_manual_expected" in dialog
    assert "File Unmatched atau Ambiguous" in dialog

    assert "The episode is known" in service
    assert "choices=self._choices(episode_rows)" in service
    assert "def assign_manual_expected(" in service
    assert "Expected filename dipilih manual oleh user." in service
