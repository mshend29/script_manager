from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


MENU_BINDINGS = {
    "Ctrl+N": 'self._add_menu_action(file_menu, "New Project", self.new_project, "Ctrl+N")',
    "Ctrl+O": 'self._add_menu_action(file_menu, "Open Project", self.open_project, "Ctrl+O")',
    "Ctrl+S": 'self._add_menu_action(file_menu, "Save Project", self.save_project, "Ctrl+S")',
    "Ctrl+W": 'self._add_menu_action(file_menu, "Close Project", self.close_project, "Ctrl+W")',
    "F5": 'self._add_menu_action(data_menu, "Sync Source", self.sync_source, "F5")',
}

MULTILINE_MENU_BINDINGS = {
    "Ctrl+Shift+S": (
        '"Save As",',
        'self.save_project_as,',
        '"Ctrl+Shift+S",',
    ),
    "F1": (
        '"Getting Started",',
        'self.open_getting_started,',
        '"F1",',
    ),
}


def test_keyboard_shortcuts_help_matches_implemented_bindings():
    main = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")
    help_file = ROOT / "resources" / "help" / "keyboard_shortcuts.html"
    help_content = help_file.read_text(encoding="utf-8")

    assert "QAction" in main
    assert "QKeySequence" in main
    assert "def _init_keyboard_shortcuts" in main
    assert '("Ctrl+F", self.open_script_search)' in main

    for sequence, source_fragment in MENU_BINDINGS.items():
        assert source_fragment in main
        assert sequence in help_content

    for sequence, fragments in MULTILINE_MENU_BINDINGS.items():
        for fragment in fragments:
            assert fragment in main
        assert sequence in help_content

    assert "Ctrl+F" in help_content


def test_ctrl_f_navigates_to_script_search():
    main = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")

    assert "def open_script_search" in main
    assert 'self.set_page("SCRIPT")' in main
    assert "self.focus_script_search()" in main


def test_keyboard_shortcuts_help_navigation_is_wired():
    page = (ROOT / "pages" / "help_page.py").read_text(encoding="utf-8")
    main = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")

    assert "KEYBOARD_SHORTCUTS_FILE" in page
    assert "def show_keyboard_shortcuts" in page

    assert 'help_menu = menu_bar.addMenu("&Help")' in main
    assert '"Shortcut",' in main
    assert "self.open_keyboard_shortcuts" in main
    assert "def open_keyboard_shortcuts" in main
    assert "page.show_keyboard_shortcuts()" in main


def test_keyboard_shortcuts_page_explains_sync_source_semantics():
    content = (
        ROOT / "resources" / "help" / "keyboard_shortcuts.html"
    ).read_text(encoding="utf-8")

    assert "F5 bukan sekadar refresh tampilan" in content
    assert "Sync Source" in content
    assert "source Excel" in content
