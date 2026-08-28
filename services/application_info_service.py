from __future__ import annotations

import platform
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version

from core.database import SCHEMA_VERSION
from core.project import (
    PROJECT_FILE_EXTENSION,
    PROJECT_FORMAT_ID,
    PROJECT_FORMAT_NAME,
    PROJECT_FORMAT_VERSION,
)
from core.version import (
    APP_NAME,
    APP_VERSION,
    GITHUB_REPOSITORY,
    GITHUB_REPOSITORY_URL,
)


@dataclass(frozen=True)
class ApplicationInfo:
    app_name: str
    app_version: str
    project_extension: str
    project_format_name: str
    project_format_id: str
    project_format_version: int
    database_schema_version: int
    python_version: str
    pyside6_version: str
    os_name: str
    architecture: str
    repository: str
    repository_url: str


class ApplicationInfoService:
    def build(self) -> ApplicationInfo:
        return ApplicationInfo(
            app_name=APP_NAME,
            app_version=APP_VERSION,
            project_extension=PROJECT_FILE_EXTENSION,
            project_format_name=PROJECT_FORMAT_NAME,
            project_format_id=PROJECT_FORMAT_ID,
            project_format_version=PROJECT_FORMAT_VERSION,
            database_schema_version=SCHEMA_VERSION,
            python_version=platform.python_version(),
            pyside6_version=self._package_version("PySide6"),
            os_name=f"{platform.system()} {platform.release()}".strip(),
            architecture=platform.machine() or "unknown",
            repository=GITHUB_REPOSITORY,
            repository_url=GITHUB_REPOSITORY_URL,
        )

    @staticmethod
    def _package_version(package_name: str) -> str:
        try:
            return version(package_name)
        except PackageNotFoundError:
            return "not installed"
