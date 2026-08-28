from __future__ import annotations

from core.database import SCHEMA_VERSION
from core.project import (
    PROJECT_FILE_EXTENSION,
    PROJECT_FORMAT_ID,
    PROJECT_FORMAT_NAME,
    PROJECT_FORMAT_VERSION,
)
from core.version import APP_NAME, APP_VERSION, GITHUB_REPOSITORY
from services.application_info_service import ApplicationInfoService


def test_application_info_uses_engine_constants():
    info = ApplicationInfoService().build()

    assert info.app_name == APP_NAME
    assert info.app_version == APP_VERSION
    assert info.project_extension == PROJECT_FILE_EXTENSION
    assert info.project_format_name == PROJECT_FORMAT_NAME
    assert info.project_format_id == PROJECT_FORMAT_ID
    assert info.project_format_version == PROJECT_FORMAT_VERSION
    assert info.database_schema_version == SCHEMA_VERSION
    assert info.repository == GITHUB_REPOSITORY


def test_application_info_contains_runtime_fields_without_project_data():
    info = ApplicationInfoService().build()

    assert info.python_version
    assert info.pyside6_version
    assert info.os_name
    assert info.architecture

    names = set(info.__dataclass_fields__)
    for forbidden in (
        "project_name",
        "client_name",
        "source_folder",
        "project_file",
        "dialogue",
    ):
        assert forbidden not in names
