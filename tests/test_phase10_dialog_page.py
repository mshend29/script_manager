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
    assert '"DialogSelectionFooter"' in source
    assert '"DialogCastPanel"' in source
    assert "QSplitter(Qt.Orientation.Horizontal)" in source
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

    assert 'self.table.setHorizontalHeaderLabels(["", "IN", "OUT", "DIALOG"])' in source
    assert "class DialogHeaderView(QHeaderView)" in source
    assert "header.bulk_toggled.connect(self.set_all_checked)" in source
    assert "self._service.set_recorded(int(dialogue_id), recorded)" in source
    assert "self._service.set_recorded_bulk(dialogue_ids, checked)" in source
    assert "⚠ Source Revised" in source
    assert 'COLORS["source_revised_text"]' in source
    assert 'COLORS["source_revised_soft"]' in source
    assert 'QCheckBox[source_revised="true"]' in theme


def test_dialog_data_and_cast_use_seventy_thirty_split_layout() -> None:
    source = (ROOT / "pages" / "dialog_page.py").read_text(
        encoding="utf-8"
    )

    assert '"DialogSessionSummary"' in source
    assert '"CAST EPISODE"' in source
    assert "content_splitter.setStretchFactor(0, 7)" in source
    assert "content_splitter.setStretchFactor(1, 3)" in source
    assert "content_splitter.setSizes([700, 300])" in source
    assert "self.cast_table.setMaximumHeight(112)" not in source
    assert "recorded{revision_text}" in source
