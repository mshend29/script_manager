from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_dialog_table_is_single_line_and_has_copy_all_control():
    source = _read("pages/dialog_page.py")

    assert "self.table.setWordWrap(False)" in source
    assert "self.table.setTextElideMode(Qt.TextElideMode.ElideRight)" in source
    assert "self.table.verticalHeader().setDefaultSectionSize(38)" in source
    assert 'QPushButton("Copy All Dialog")' in source
    assert "self.copy_all_button.clicked.connect(self._copy_all_dialogues_clicked)" in source
    assert 'self.search_edit.setPlaceholderText("Search dialog…")' in source
    assert "self.search_edit.textChanged.connect(self._apply_search_filter)" in source


def test_copy_all_dialogues_copies_only_dialog_text_one_record_per_line():
    source = _read("pages/dialog_page.py")

    assert 'return " ".join(str(value or "").splitlines()).strip()' in source
    assert "for row in self._dialogue_rows" in source
    assert 'QApplication.clipboard().setText("\\n".join(lines))' in source
    assert "row.time_in" not in source.split("def copy_all_dialogues", 1)[1].split(
        "def _copy_all_dialogues_clicked", 1
    )[0]
    assert "row.time_out" not in source.split("def copy_all_dialogues", 1)[1].split(
        "def _copy_all_dialogues_clicked", 1
    )[0]


def test_dialog_episode_selection_has_prev_next_navigation():
    source = _read("pages/dialog_page.py")

    assert 'QPushButton("‹ Prev")' in source
    assert 'QPushButton("Next ›")' in source
    assert "_select_adjacent_episode(-1)" in source
    assert "_select_adjacent_episode(1)" in source
    assert "self._update_episode_navigation()" in source
    assert "self.prev_episode_button.setEnabled" in source
    assert "self.next_episode_button.setEnabled" in source
