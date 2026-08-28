from __future__ import annotations

import platform
from dataclasses import dataclass
from urllib.parse import urlencode

import PySide6

from core.database import SCHEMA_VERSION
from core.project import PROJECT_FORMAT_VERSION
from core.version import (
    APP_NAME,
    APP_VERSION,
    GITHUB_NEW_ISSUE_URL,
)


@dataclass(frozen=True)
class ProblemReport:
    title: str
    body: str
    issue_url: str
    environment: dict[str, str]


class ProblemReportService:
    def __init__(
        self,
        *,
        app_version: str = APP_VERSION,
        issue_url: str = GITHUB_NEW_ISSUE_URL,
    ):
        self.app_version = str(app_version).strip()
        self.issue_url = str(issue_url).strip()

    def build(self) -> ProblemReport:
        environment = self._environment()
        body = self._body(environment)
        title = "[Bug] "

        query = urlencode(
            {
                "title": title,
                "body": body,
            }
        )
        issue_url = (
            f"{self.issue_url}?{query}"
            if query
            else self.issue_url
        )

        return ProblemReport(
            title=title,
            body=body,
            issue_url=issue_url,
            environment=environment,
        )

    def _environment(self) -> dict[str, str]:
        return {
            "Application": f"{APP_NAME} {self.app_version}",
            "Project format": str(PROJECT_FORMAT_VERSION),
            "Database schema": str(SCHEMA_VERSION),
            "Python": platform.python_version(),
            "PySide6": str(PySide6.__version__),
            "OS": f"{platform.system()} {platform.release()}".strip(),
            "Architecture": platform.machine() or "unknown",
        }

    @staticmethod
    def _body(environment: dict[str, str]) -> str:
        environment_lines = "\n".join(
            f"- {key}: {value}"
            for key, value in environment.items()
        )

        return (
            "## Problem\n"
            "Describe what went wrong.\n\n"
            "## Steps to reproduce\n"
            "1. \n"
            "2. \n"
            "3. \n\n"
            "## Expected result\n"
            "What did you expect to happen?\n\n"
            "## Actual result\n"
            "What actually happened?\n\n"
            "## Environment\n"
            f"{environment_lines}\n\n"
            "## Additional context\n"
            "Add screenshots or extra details if useful.\n\n"
            "> Privacy note: this template intentionally does not include "
            "project names, client names, source paths, Drive URLs, "
            "dialogue text, or other project content."
        )
