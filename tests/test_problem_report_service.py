from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from services.problem_report_service import ProblemReportService


EXPECTED_ENVIRONMENT_KEYS = {
    "Application",
    "Project format",
    "Database schema",
    "Python",
    "PySide6",
    "OS",
    "Architecture",
}


def test_problem_report_contains_only_approved_environment_fields():
    report = ProblemReportService(app_version="0.1.0").build()

    assert set(report.environment) == EXPECTED_ENVIRONMENT_KEYS
    assert report.environment["Application"] == "Script Manager 0.1.0"


def test_problem_report_template_has_reproduction_sections():
    report = ProblemReportService(app_version="0.1.0").build()

    for expected in (
        "## Problem",
        "## Steps to reproduce",
        "## Expected result",
        "## Actual result",
        "## Environment",
        "## Additional context",
        "Privacy note",
    ):
        assert expected in report.body


def test_problem_report_issue_url_is_prefilled_but_not_submitted():
    report = ProblemReportService(
        app_version="0.1.0",
        issue_url="https://example.com/issues/new",
    ).build()

    parsed = urlparse(report.issue_url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "example.com"
    assert parsed.path == "/issues/new"
    assert query["title"] == ["[Bug] "]
    assert query["body"] == [report.body]


def test_problem_report_service_requires_no_project_data():
    report = ProblemReportService(app_version="0.1.0").build()

    assert "project_name" not in report.environment
    assert "client_name" not in report.environment
    assert "source_folder" not in report.environment
    assert "main_drive_url" not in report.environment
