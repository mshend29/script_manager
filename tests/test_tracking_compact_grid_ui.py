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

    # Talent summary stays in the common header while production file tools
    # live in dedicated Tracking workspaces.
    assert "header_row.addWidget(self.title_label)" in tracking
    assert "header_row.addWidget(self.summary_label, 1)" in tracking
    assert 'QLabel("TRACK FILES")' in compact
    assert '["TRACK SUGGESTION", "STEM / EXPORT", "DELIVERED"]' in compact
    assert 'QLabel("OUTPUT HEALTH")' in compact



def test_tracking_has_dedicated_track_files_and_output_health_workspaces():
    compact = _read("pages/tracking_compact_page.py")
    main = _read("app/main_window.py")

    assert 'WORKSPACE_TRACKING = "tracking"' in compact
    assert 'WORKSPACE_TRACK_FILES = "track_files"' in compact
    assert 'WORKSPACE_OUTPUT_HEALTH = "output_health"' in compact
    assert 'QPushButton("Go to Output Health")' in compact
    assert '(WORKSPACE_TRACKING, "Tracking")' in compact
    assert '(WORKSPACE_TRACK_FILES, "Track Files")' in compact
    assert '(WORKSPACE_OUTPUT_HEALTH, "Output Health")' in compact
    assert "QStackedWidget" in compact
    assert "self.show_workspace(WORKSPACE_OUTPUT_HEALTH)" in compact

    # Dashboard output warnings navigate to the detailed health workspace,
    # while ordinary Tracking scope navigation returns to the grid.
    assert 'page.show_workspace("output_health")' in main
    assert 'page.show_workspace("track_files")' in main
    assert 'page.show_workspace("tracking")' in main


def test_track_name_suggestion_uses_three_columns_five_rows_and_canonical_names():
    compact = _read("pages/tracking_compact_page.py")

    assert "TRACK_NAMES_PER_COLUMN = 5" in compact
    assert "TRACK_NAME_COLUMNS = 3" in compact
    assert "TRACK_NAMES_PER_PAGE = TRACK_NAMES_PER_COLUMN * TRACK_NAME_COLUMNS" in compact
    assert 'QLabel("TRACK NAME SUGGESTION")' in compact
    assert "str(row.character_name).upper()" in compact
    assert "index % self.TRACK_NAMES_PER_COLUMN" in compact
    assert "index // self.TRACK_NAMES_PER_COLUMN" in compact
    assert "QApplication.clipboard().setText" in compact
    assert "QToolTip.showText" in compact
    assert 'f"Copied: {text}"' in compact
    assert "Aliases:" in compact


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
