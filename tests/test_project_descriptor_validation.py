import json

import pytest

from core.project_manager import ProjectError, ProjectManager
from core.project_settings import ProjectSettings


def _assert_no_project_side_effects(folder) -> None:
    assert not (folder / "project.db").exists()
    assert not (folder / "backups").exists()
    assert not (folder / "logs").exists()


def test_unrelated_json_is_rejected_without_side_effects(tmp_path):
    unrelated = tmp_path / "unrelated_preferences.json"
    unrelated.write_text("{}", encoding="utf-8")

    manager = ProjectManager()
    with pytest.raises(ProjectError, match="project.json"):
        manager.open(unrelated)

    assert not manager.is_open
    _assert_no_project_side_effects(tmp_path)


def test_invalid_project_json_is_rejected_without_side_effects(tmp_path):
    descriptor = tmp_path / "project.json"
    descriptor.write_text(json.dumps({}), encoding="utf-8")

    manager = ProjectManager()
    with pytest.raises(ProjectError, match="format"):
        manager.open(descriptor)

    assert not manager.is_open
    _assert_no_project_side_effects(tmp_path)


def test_valid_project_descriptor_still_opens(tmp_path):
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
    assert reopened.database_file.exists()
