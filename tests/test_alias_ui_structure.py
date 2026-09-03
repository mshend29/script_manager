from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_character_alias_ui_is_manual_and_reversible():
    source = _read("pages/data_alias_page.py")
    assert '"ALIASES"' in source
    assert 'QPushButton("Set as Alias")' in source
    assert 'QPushButton("Add Alias Name…")' in source
    assert 'QPushButton("Remove Alias / Restore")' in source
    assert "set_character_alias" in source
    assert "remove_alias" in source


def test_tracking_status_legend_is_two_column_grid():
    source = _read("pages/tracking_compact_page.py")
    assert "QGridLayout" in source
    assert "index // 2" in source
    assert "index % 2" in source


def test_main_window_uses_enhanced_data_and_tracking_pages():
    source = _read("app/main_window.py")
    entrypoint = _read("main.py")

    assert "from pages.data_alias_page import AliasDataPage as DataPage" in source
    assert (
        "from pages.tracking_compact_page import "
        "CompactTrackingPage as TrackingPage"
    ) in source
    assert "main_window_module.DataPage" not in entrypoint
    assert "main_window_module.TrackingPage" not in entrypoint
