from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_report_problem_help_content_explains_privacy_and_manual_submit():
    content = (
        ROOT / "resources" / "help" / "report_problem.html"
    ).read_text(encoding="utf-8")

    for expected in (
        "Report a Problem",
        "Open GitHub Issue",
        "Copy Report Template",
        "nama project",
        "nama client",
        "Source Folder",
        "Drive URL",
        "dialogue text",
        "Periksa kembali isi laporan sebelum Submit",
    ):
        assert expected in content


def test_report_problem_is_wired_to_help_header_and_main_window():
    header = (ROOT / "widgets" / "page_header.py").read_text(encoding="utf-8")
    page = (ROOT / "pages" / "help_page.py").read_text(encoding="utf-8")
    main = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")

    assert 'HeaderAction("help.report_problem", "Report a Problem")' in header
    assert 'QPushButton("Report a Problem")' in page
    assert '"help.report_problem": self.report_problem' in main
    assert "ProblemReportService().build()" in main
    assert 'self.pages["HELP"].show_report_problem(report)' in main


def test_report_problem_has_open_issue_and_copy_fallback():
    page = (ROOT / "pages" / "help_page.py").read_text(encoding="utf-8")
    main = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")

    assert 'QPushButton("Open GitHub Issue")' in page
    assert 'QPushButton("Copy Report Template")' in page
    assert "issue_requested = Signal(str)" in page
    assert "self.issue_requested.emit(self._issue_url)" in page
    assert "QApplication.clipboard().setText" in page
    assert "help_page.issue_requested.connect(self.open_problem_issue)" in main
    assert "QDesktopServices.openUrl(QUrl(target))" in main


def test_report_problem_environment_is_rendered_from_service_result():
    page = (ROOT / "pages" / "help_page.py").read_text(encoding="utf-8")

    assert 'getattr(report, "environment", {})' in page
    assert 'html.replace("{{ENVIRONMENT_ROWS}}", rows)' in page
    assert 'getattr(report, "issue_url", "")' in page
    assert 'getattr(report, "body", "")' in page
