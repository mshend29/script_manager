from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PAGE = ROOT / "pages" / "script_page.py"
THEME = ROOT / "app" / "theme.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_script_page_uses_model_backed_table_view():
    source = _source(SCRIPT_PAGE)
    tree = ast.parse(source)

    imported_names = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert "QAbstractTableModel" in imported_names
    assert "QTableView" in imported_names
    assert "QTableWidget" not in imported_names
    assert "QTableWidgetItem" not in imported_names


def test_script_sidebar_only_filters_episode_plus_search():
    source = _source(SCRIPT_PAGE)

    assert "self.episode_combo" in source
    assert "self.search_edit" in source
    assert "self.character_combo" not in source
    assert "self.talent_combo" not in source


def test_script_view_keeps_engine_episode_order_instead_of_qt_sorting():
    source = _source(SCRIPT_PAGE)

    assert "self.table.setSortingEnabled(False)" in source
    assert "self.table.setSortingEnabled(True)" not in source
    assert "episode_number=self.episode_combo.currentData()" in source
    assert "character_id=" not in source
    assert "talent_id=" not in source


def test_script_refresh_same_database_does_not_rebuild_filter_widgets():
    source = _source(SCRIPT_PAGE)

    assert "if database is self._database and self._service is not None:" in source
    assert "self.refresh_rows()" in source


def test_source_sync_progress_is_visually_emphasized():
    source = _source(THEME)

    assert "QProgressBar::chunk" in source
    assert "background: #217346" in source
    assert "QStatusBar" in source
    assert "min-height: 34px" in source
