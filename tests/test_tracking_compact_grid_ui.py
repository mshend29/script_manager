from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_episode_chip_only_shows_episode_number_and_uses_fixed_size():
    source = _read("widgets/episode_chip.py")

    assert 'self.setText(f"EP {chip.episode_number}")' in source
    assert "chip.status_label" not in source.split("self.setText", 1)[1].split(")", 1)[0]
    assert "chip.progress_text" not in source.split("self.setText", 1)[1].split(")", 1)[0]
    assert "self.setFixedSize(72, 38)" in source
    assert "border-radius: 9px" in source
    assert "detail_requested" in source


def test_tracking_workspace_uses_two_column_character_episode_grid():
    source = _read("pages/tracking_page.py")

    assert 'QLabel("TOKOH")' in source
    assert 'QLabel("EPISODE")' in source
    assert "QGridLayout(self.rows_container)" in source
    assert "_build_character_card" not in source
    assert "EpisodeChipButton(chip)" in source
    assert "detail_requested.connect(self._open_episode_detail)" in source


def test_tracking_sidebar_has_colored_status_legend_and_character_status_columns():
    source = _read("pages/tracking_page.py")

    assert "status_palette(status)" in source
    assert 'setHorizontalHeaderLabels(["TOKOH", "STATUS"])' in source
    assert "status_item.setBackground" in source
    assert "status_item.setForeground" in source


def test_tracking_episode_detail_moves_status_and_dialog_counts_into_dialog():
    source = _read("dialogs/tracking_episode_dialog.py")

    assert 'form.addRow("Status saat ini"' in source
    assert '"Dialog recorded"' in source
    assert "chip.recorded_dialogues" in source
    assert "chip.total_dialogues" in source
    assert 'self.status_combo.addItem("Ready to Stem"' in source
    assert 'self.status_combo.addItem("Stemmed"' in source
    assert 'self.status_combo.addItem("Delivered"' in source
    assert 'self.status_combo.addItem("Revision"' in source
