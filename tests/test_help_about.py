from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_about_content_describes_application_and_project_format():
    content = (
        ROOT / "resources" / "help" / "about.html"
    ).read_text(encoding="utf-8")

    for expected in (
        "About Script Manager",
        "{{APP_NAME}}",
        "{{APP_VERSION}}",
        "{{PROJECT_EXTENSION}}",
        "{{PROJECT_FORMAT_NAME}}",
        "{{PROJECT_FORMAT_ID}}",
        "{{PROJECT_FORMAT_VERSION}}",
        "{{DATABASE_SCHEMA_VERSION}}",
        "{{PYTHON_VERSION}}",
        "{{PYSIDE6_VERSION}}",
        "{{OS_NAME}}",
        "{{ARCHITECTURE}}",
        "{{REPOSITORY}}",
        "Source Excel",
        "tidak di-embed",
    ):
        assert expected in content


def test_about_is_wired_to_help_ribbon_and_main_window():
    ribbon = (ROOT / "app" / "ribbon.py").read_text(encoding="utf-8")
    page = (ROOT / "pages" / "help_page.py").read_text(encoding="utf-8")
    main = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")

    assert '("help.about", "About Script Manager")' in ribbon
    assert 'QPushButton("About Script Manager")' in page
    assert '"help.about": self.open_about' in main
    assert "ApplicationInfoService().build()" in main
    assert 'self.pages["HELP"].show_about(info)' in main


def test_about_page_renders_dynamic_engine_information():
    page = (ROOT / "pages" / "help_page.py").read_text(encoding="utf-8")

    assert "ABOUT_FILE" in page
    assert "def show_about" in page
    assert '"APP_VERSION": getattr(info, "app_version", "")' in page
    assert (
        '"PROJECT_FORMAT_VERSION": getattr('
        in page
    )
    assert (
        '"DATABASE_SCHEMA_VERSION": getattr('
        in page
    )
    assert 'html.replace(' in page
    assert "self.about_button" in page


def test_help_ribbon_now_contains_complete_planned_help_set():
    ribbon = (ROOT / "app" / "ribbon.py").read_text(encoding="utf-8")

    for action in (
        "help.getting_started",
        "help.user_guide",
        "help.keyboard_shortcuts",
        "help.check_updates",
        "help.report_problem",
        "help.about",
    ):
        assert action in ribbon
