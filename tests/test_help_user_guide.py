from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_user_guide_covers_current_application_areas():
    guide_file = ROOT / "resources" / "help" / "user_guide.html"
    assert guide_file.is_file()

    content = guide_file.read_text(encoding="utf-8")

    for expected in (
        "User Guide",
        ".smproj",
        "Project Settings",
        "Import Source",
        "Refresh Data",
        "SCRIPT",
        "DIALOG",
        "TRACKING",
        "DATA",
        "TOOLS",
        "Character Alias",
        "Output Health",
        "Restore Backup",
        "Recover Project",
    ):
        assert expected in content


def test_help_page_can_switch_between_getting_started_and_user_guide():
    page = (ROOT / "pages" / "help_page.py").read_text(encoding="utf-8")

    assert "USER_GUIDE_FILE" in page
    assert 'QPushButton("User Guide")' in page
    assert "def show_user_guide" in page
    assert "def _set_active_button" in page
    assert 'button.setProperty("primary", is_active)' in page
    assert 'button.setProperty("secondary", not is_active)' in page


def test_user_guide_action_is_wired_to_ribbon_and_main_window():
    ribbon = (ROOT / "app" / "ribbon.py").read_text(encoding="utf-8")
    main = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")

    assert '("help.user_guide", "User Guide")' in ribbon
    assert '"help.user_guide": self.open_user_guide' in main
    assert "def open_user_guide" in main
    assert "page.show_user_guide()" in main


def test_user_guide_stage_does_not_add_later_help_features():
    ribbon = (ROOT / "app" / "ribbon.py").read_text(encoding="utf-8")

    for action in (
        "help.shortcuts",
    ):
        assert action not in ribbon
