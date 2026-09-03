from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dialog_page_uses_full_width_phase10_workspace() -> None:
    source = (ROOT / "pages" / "dialog_page.py").read_text(
        encoding="utf-8"
    )

    assert "class DialogPage(QWidget)" in source
    assert "ContextPanel" not in source
    assert "PageShell" not in source
    assert '"DialogWorkspace"' in source
    assert '"DialogFilterBar"' in source
    assert '"DialogTable"' in source
    assert '"DialogSessionFooter"' in source
    assert 'QLabel("Dialog")' not in source


def test_dialog_filters_and_search_live_in_one_compact_bar() -> None:
    source = (ROOT / "pages" / "dialog_page.py").read_text(
        encoding="utf-8"
    )

    talent = source.index('QLabel("Talent")')
    character = source.index('QLabel("Tokoh")')
    episode = source.index('QLabel("Episode")')
    search = source.index('self.search_edit = QLineEdit()')

    assert talent < character < episode < search
    assert 'self.search_edit.setPlaceholderText("Search dialog…")' in source
    assert "def _apply_search_filter" in source
    assert "self.table.setRowHidden" in source


def test_dialog_preserves_recording_and_source_revision_semantics() -> None:
    source = (ROOT / "pages" / "dialog_page.py").read_text(
        encoding="utf-8"
    )
    theme = (ROOT / "app" / "theme.py").read_text(encoding="utf-8")

    assert 'self.table.setHorizontalHeaderLabels(["✓", "IN", "OUT", "DIALOG"])' in source
    assert "self._service.set_recorded(int(dialogue_id), recorded)" in source
    assert "self._service.set_recorded_bulk(dialogue_ids, checked)" in source
    assert "⚠ Source Revised" in source
    assert 'COLORS["source_revised"]' in source
    assert 'COLORS["source_revised_soft"]' in source
    assert 'QCheckBox[source_revised="true"]' in theme


def test_dialog_session_summary_and_cast_are_bottom_aligned_and_compact() -> None:
    source = (ROOT / "pages" / "dialog_page.py").read_text(
        encoding="utf-8"
    )

    assert '"DialogSessionSummary"' in source
    assert '"CAST EPISODE"' in source
    assert "self.cast_table.setMaximumHeight(112)" in source
    assert "recorded{revision_text}" in source
