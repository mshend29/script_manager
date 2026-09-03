from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_unresolved_table_has_talent_column_and_manual_cell_actions():
    source = _read("pages/data_page.py")

    assert '["EPS", "ISSUE", "CHARACTER", "TALENT", "DIALOG", "SOURCE"]' in source
    assert "self.unresolved_table.cellClicked.connect" in source
    assert 'menu.addAction("Add Character…")' in source
    assert 'menu.addAction("Add Talent…")' in source
    assert 'menu.addAction("Open Source")' in source
    assert 'menu.addAction("Mark as Narration / Non-Dialogue")' in source
    assert 'menu.addAction("Restore to Needs Review")' in source
    assert "self._controller.add_missing_character(" in source
    assert "self._controller.add_talent_and_lock(" in source
    controller = _read("pages/data_workspace_controller.py")
    assert "service.ensure_character(name)" in controller
    assert "service.assign_missing_character" in controller
    assert "service.ensure_talent(name)" in controller
    assert "service.set_locked_mapping" in controller
    assert "QDesktopServices.openUrl" in source


def test_character_mapping_surfaces_unresolved_first_with_warning_colors():
    page = _read("pages/data_page.py")
    service = _read("services/data_service.py")

    assert 'UNRESOLVED_CHARACTER_COLOR = QColor("#FDE7E9")' in page
    assert 'UNRESOLVED_TALENT_COLOR = QColor("#FFF4CE")' in page
    assert "row.missing_character" in page
    assert '"⚠ Talent Unknown"' in page

    assert 'name="⚠ Character Unknown"' in service
    assert 'locked_talent_name="⚠ Talent Unknown"' in service
    assert "result.insert(" in service
    assert "ORDER BY unresolved_dialogues DESC" in service


def test_sidebar_add_talent_is_removed_and_cast_mapping_only_shows_on_character_tab():
    source = _read("pages/data_page.py")

    assert "self.add_talent_button" not in source
    assert "self._cast_mapping_widgets" in source
    assert "self.tabs.currentChanged.connect(self._data_tab_changed)" in source
    assert "self._update_cast_mapping_visibility()" in source
    assert 'self.TAB_INDEX["characters"]' in source
    assert "widget.setVisible(visible)" in source


def test_missing_character_stays_manual_in_validation_copy():
    source = _read("services/data_service.py")

    assert "ACTIVE_DIALOGUE_NO_CAST" in source
    assert "memerlukan keputusan manual" in source
    assert "assign_missing_character" in source
    assert "ensure_character" in source
