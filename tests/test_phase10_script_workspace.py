from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_script_filters_move_into_workspace_toolbar() -> None:
    source = _read("pages/script_page.py")

    assert 'ContextPanel("TOKOH & TALENT")' in source
    assert 'filter_bar.setObjectName("ScriptFilterBar")' in source
    assert 'self.result_label = QLabel("Belum ada proyek terbuka")' in source
    assert 'episode_label = QLabel("Episode")' in source
    assert 'self.episode_combo.addItem("Semua Episode", None)' in source
    assert 'QPushButton("‹ Sebelumnya")' in source
    assert 'QPushButton("Berikutnya ›")' in source
    assert 'setPlaceholderText("Cari naskah…")' in source


def test_script_sidebar_groups_cast_by_talent_for_current_scope() -> None:
    source = _read("pages/script_page.py")

    assert "class ScriptCastTableModel(QAbstractTableModel)" in source
    assert 'HEADERS = ("TALENT", "TOKOH")' in source
    assert 'self.cast_table = ScriptTableView()' in source
    assert "self.cast_table.setModel(self.cast_model)" in source
    assert "def _refresh_cast_sidebar" in source
    assert "episode_number = self.episode_combo.currentData()" in source
    assert 'search=""' in source
    assert "talent_cast: dict[str, set[str]] = {}" in source
    assert "talent_cast.setdefault(talent_text, set()).add(character_text)" in source
    assert '" / ".join(' in source
    assert '"Semua episode"' in source
    assert 'f"Episode {episode_number}"' in source
    assert 'f"{self._format_count(len(unique_talents))} talent • "' in source


def test_script_dialogue_rows_are_single_line_like_dialog_workspace() -> None:
    source = _read("pages/script_page.py")

    assert "self.table.setWordWrap(False)" in source
    assert "self.table.setTextElideMode(Qt.TextElideMode.ElideRight)" in source
    assert "self.table.verticalHeader().setDefaultSectionSize(38)" in source
    assert "tooltip = row.dialogue" in source
    assert 'tooltip += f"\\n\\nSumber: {row.source_file_name}"' in source


def test_script_episode_navigation_includes_all_episodes_scope() -> None:
    source = _read("pages/script_page.py")

    assert "def _select_adjacent_episode" in source
    assert "current + int(offset)" in source
    assert "max(current + int(offset), 0)" in source
    assert "current > 0" in source
    assert "current < count - 1" in source


def test_script_visible_character_terminology_is_tokoh() -> None:
    source = _read("pages/script_page.py")

    assert 'HEADERS = ("EPISODE", "IN", "OUT", "DIALOG", "TOKOH", "TALENT")' in source
    assert '"Character"' not in source
    assert '"CHARACTER"' not in source
