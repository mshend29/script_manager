import sqlite3

import pytest

from core.project_manager import ProjectError, ProjectManager
from core.project_settings import ProjectSettings


def test_unrelated_json_is_rejected_without_opening_project(tmp_path):
    unrelated = tmp_path / "unrelated_preferences.json"
    unrelated.write_text("{}", encoding="utf-8")

    manager = ProjectManager()
    with pytest.raises(ProjectError, match=r"\.smproj"):
        manager.open(unrelated)

    assert not manager.is_open


def test_sqlite_without_smproj_metadata_is_rejected(tmp_path):
    project_file = tmp_path / "invalid.smproj"
    connection = sqlite3.connect(project_file)
    try:
        connection.execute("CREATE TABLE unrelated(id INTEGER)")
        connection.commit()
    finally:
        connection.close()

    manager = ProjectManager()
    with pytest.raises(ProjectError, match="bukan Script Management Project"):
        manager.open(project_file)

    assert not manager.is_open


def test_valid_smproj_still_opens(tmp_path):
    manager = ProjectManager()
    created = manager.create(
        ProjectSettings(project_name="Valid Project"),
        tmp_path,
    )
    project_file = created.project_file
    manager.close()

    reopened = ProjectManager().open(project_file)

    assert reopened.settings.project_name == "Valid Project"
    assert reopened.project_file == project_file
    assert reopened.database_file == project_file
    assert reopened.database_file.exists()
