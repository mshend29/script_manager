from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.project import (
    PROJECT_FILE_EXTENSION,
    PROJECT_FORMAT_ID,
    PROJECT_FORMAT_VERSION,
    Project,
    ProjectFormatError,
)
from core.project_manager import ProjectManager
from core.project_settings import ProjectSettings


def test_new_project_is_single_writable_smproj_file(tmp_path):
    manager = ProjectManager()
    project = manager.create(
        ProjectSettings(
            project_name="AA23",
            project_code="AA23",
        ),
        tmp_path,
    )

    expected = tmp_path / "AA23.smproj"
    assert project.project_file == expected
    assert project.database_file == expected
    assert project.root == tmp_path
    assert expected.is_file()
    assert project.settings.project_folder == str(expected)
    assert project.backups_folder.is_dir()
    assert project.logs_folder.is_dir()

    with sqlite3.connect(expected) as connection:
        meta = dict(
            connection.execute(
                "SELECT key, value FROM smproj_meta"
            ).fetchall()
        )
        settings = dict(
            connection.execute(
                "SELECT key, value_json FROM project_settings"
            ).fetchall()
        )

    assert meta["format_id"] == PROJECT_FORMAT_ID
    assert int(meta["format_version"]) == PROJECT_FORMAT_VERSION
    assert "project_name" in settings
    assert "project_folder" not in settings


def test_project_code_with_smproj_extension_does_not_duplicate_extension(
    tmp_path,
):
    project = ProjectManager().create(
        ProjectSettings(
            project_name="AA23",
            project_code="AA23.smproj",
        ),
        tmp_path,
    )

    assert project.project_file.name == "AA23.smproj"


def test_smproj_reopens_as_same_project(tmp_path):
    manager = ProjectManager()
    created = manager.create(
        ProjectSettings(
            project_name="Package",
            client_name="Client A",
        ),
        tmp_path,
    )
    project_file = created.project_file
    project_id = created.project_id
    manager.close()

    reopened = ProjectManager().open(project_file)

    assert reopened.project_file == project_file
    assert reopened.project_id == project_id
    assert reopened.settings.project_name == "Package"
    assert reopened.settings.client_name == "Client A"
    assert reopened.settings.project_folder == str(project_file)


def test_wrong_extension_is_rejected(tmp_path):
    fake = tmp_path / "Broken.db"
    fake.write_text("not a project", encoding="utf-8")

    with pytest.raises(ProjectFormatError, match=r"\.smproj"):
        Project.load(fake)


def test_non_sqlite_smproj_is_rejected(tmp_path):
    fake = tmp_path / "Broken.smproj"
    fake.write_text("not sqlite", encoding="utf-8")

    with pytest.raises(ProjectFormatError, match="SQLite"):
        Project.load(fake)


def test_unrelated_sqlite_smproj_is_rejected(tmp_path):
    fake = tmp_path / "Unrelated.smproj"
    connection = sqlite3.connect(fake)
    try:
        connection.execute("CREATE TABLE random_data(id INTEGER)")
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(ProjectFormatError, match="bukan Script Management Project"):
        Project.load(fake)


def test_project_ui_uses_smproj_file_picker_and_no_drsp_conversion():
    root = Path(__file__).resolve().parents[1]
    main_window = (root / "app" / "main_window.py").read_text(
        encoding="utf-8"
    )
    tools_page = (root / "pages" / "tools_page.py").read_text(
        encoding="utf-8"
    )
    ribbon = (root / "app" / "ribbon.py").read_text(
        encoding="utf-8"
    )
    new_dialog = (root / "dialogs" / "new_project_dialog.py").read_text(
        encoding="utf-8"
    )
    main_py = (root / "main.py").read_text(encoding="utf-8")

    assert "QFileDialog.getOpenFileName" in main_window
    assert "Script Management Project (*.smproj)" in main_window
    assert "convert_project_to_drsp" not in main_window
    assert "tools.convert_drsp" not in main_window
    assert "Convert to .drsp" not in tools_page
    assert "tools.convert_drsp" not in ribbon
    assert "(.smproj)" in new_dialog

    assert "len(sys.argv) > 1" in main_py
    assert "window.open_project_path(candidate)" in main_py


def test_project_extension_constant_is_smproj():
    assert PROJECT_FILE_EXTENSION == ".smproj"
