from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


EXPECTED_BINDINGS = {
    "Ctrl+N": "self.new_project",
    "Ctrl+O": "self.open_project",
    "Ctrl+S": "self.save_project",
    "Ctrl+Shift+S": "self.save_project_as",
    "Ctrl+W": "self.close_project",
    "Ctrl+F": "self.open_script_search",
    "F5": "self.refresh_source",
    "F1": "self.open_getting_started",
}


def test_keyboard_shortcuts_help_matches_implemented_bindings():
    main = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")
    help_file = ROOT / "resources" / "help" / "keyboard_shortcuts.html"
    help_content = help_file.read_text(encoding="utf-8")

    assert "def _init_keyboard_shortcuts" in main
    assert "QShortcut" in main
    assert "QKeySequence" in main

    for sequence, handler in EXPECTED_BINDINGS.items():
        assert f'("{sequence}", {handler})' in main
        assert sequence in help_content


def test_ctrl_f_navigates_to_script_search():
    main = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")

    assert "def open_script_search" in main
    assert 'self.ribbon.select_tab("SCRIPT")' in main
    assert "self.focus_script_search()" in main


def test_keyboard_shortcuts_help_navigation_is_wired():
    page = (ROOT / "pages" / "help_page.py").read_text(encoding="utf-8")
    ribbon = (ROOT / "app" / "ribbon.py").read_text(encoding="utf-8")
    main = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")

    assert "KEYBOARD_SHORTCUTS_FILE" in page
    assert 'QPushButton("Keyboard Shortcuts")' in page
    assert "def show_keyboard_shortcuts" in page
    assert "self.keyboard_shortcuts_button" in page

    assert (
        '("help.keyboard_shortcuts", "Keyboard Shortcuts")'
        in ribbon
    )
    assert (
        '"help.keyboard_shortcuts": self.open_keyboard_shortcuts'
        in main
    )
    assert "def open_keyboard_shortcuts" in main
    assert "page.show_keyboard_shortcuts()" in main


def test_keyboard_shortcuts_page_explains_refresh_data_semantics():
    content = (
        ROOT / "resources" / "help" / "keyboard_shortcuts.html"
    ).read_text(encoding="utf-8")

    assert "F5 bukan sekadar refresh tampilan" in content
    assert "Refresh Data" in content
    assert "source Excel" in content


def test_keyboard_shortcuts_stage_does_not_add_later_help_features():
    ribbon = (ROOT / "app" / "ribbon.py").read_text(encoding="utf-8")

    for action in (
        "help.about",
    ):
        assert action not in ribbon
