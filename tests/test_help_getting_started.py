from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_getting_started_help_content_covers_core_workflow():
    help_file = ROOT / "resources" / "help" / "getting_started.html"
    assert help_file.is_file()

    content = help_file.read_text(encoding="utf-8")

    for expected in (
        "Getting Started",
        ".smproj",
        "Source Script Folder",
        "Sync Source",
        "DIALOG",
        "TRACKING",
        "Save As",
        "Duplicate",
        "Recover Project",
    ):
        assert expected in content


def test_help_page_loads_offline_getting_started_document():
    page = (ROOT / "pages" / "help_page.py").read_text(encoding="utf-8")

    assert "QTextBrowser" in page
    assert "GETTING_STARTED_FILE" in page
    assert "getting_started.html" in page
    assert "def show_getting_started" in page
    assert "setOpenExternalLinks(False)" in page


def test_help_tab_and_getting_started_action_are_wired():
    header = (ROOT / "widgets" / "page_header.py").read_text(encoding="utf-8")
    main = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")

    assert '"HELP": PageHeaderSpec(' in header
    assert 'HeaderAction("help.getting_started", "Getting Started")' in header

    assert '"HELP": HelpPage()' in main
    assert '"help.getting_started": self.open_getting_started' in main
    assert 'def open_getting_started' in main
