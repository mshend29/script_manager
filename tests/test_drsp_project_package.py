from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.project import (
    PROJECT_FORMAT_VERSION,
    PROJECT_PACKAGE_EXTENSION,
    PROJECT_PACKAGE_TYPE,
    Project,
    ProjectFormatError,
)
from core.project_manager import ProjectError, ProjectManager
from core.project_settings import ProjectSettings
from services.audit_service import AuditService


def _write_legacy_project(root: Path, *, name: str = "Legacy") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    descriptor = root / "project.json"
    descriptor.write_text(
        json.dumps(
            {
                "format_version": 1,
                "created_at": "2026-08-28T07:00:00",
                "updated_at": "2026-08-28T07:00:00",
                "settings": {
                    "project_name": name,
                    "project_code": name,
                    "client_name": "",
                    "project_folder": str(root),
                    "source_folder": "",
                },
            }
        ),
        encoding="utf-8",
    )
    return descriptor


def test_new_project_is_writable_drsp_directory_package(tmp_path):
    manager = ProjectManager()
    project = manager.create(
        ProjectSettings(
            project_name="AA23",
            project_code="AA23",
        ),
        tmp_path,
    )

    assert project.root == tmp_path / "AA23.drsp"
    assert project.root.is_dir()
    assert project.is_package
    assert project.project_file.is_file()
    assert project.database_file.is_file()
    assert project.backups_folder.is_dir()
    assert project.logs_folder.is_dir()
    assert project.settings.project_folder == str(project.root)

    payload = json.loads(project.project_file.read_text(encoding="utf-8"))
    assert payload["format_version"] == PROJECT_FORMAT_VERSION
    assert payload["package_type"] == PROJECT_PACKAGE_TYPE
    assert payload["package_extension"] == PROJECT_PACKAGE_EXTENSION


def test_project_code_already_containing_drsp_does_not_duplicate_extension(
    tmp_path,
):
    project = ProjectManager().create(
        ProjectSettings(
            project_name="AA23",
            project_code="AA23.drsp",
        ),
        tmp_path,
    )

    assert project.root.name == "AA23.drsp"


def test_drsp_package_opens_by_directory_or_internal_descriptor(tmp_path):
    manager = ProjectManager()
    created = manager.create(
        ProjectSettings(project_name="Package"),
        tmp_path,
    )
    root = created.root
    descriptor = created.project_file
    manager.close()

    by_directory = ProjectManager().open(root)
    assert by_directory.root == root
    assert by_directory.is_package

    by_descriptor = ProjectManager().open(descriptor)
    assert by_descriptor.root == root
    assert by_descriptor.is_package


def test_legacy_v1_project_folder_remains_supported(tmp_path):
    legacy_root = tmp_path / "Legacy Project"
    descriptor = _write_legacy_project(legacy_root)

    project = ProjectManager().open(legacy_root)

    assert project.root == legacy_root
    assert not project.is_package
    assert project.settings.project_name == "Legacy"
    assert project.database_file.exists()

    direct = Project.load(descriptor)
    assert direct.root == legacy_root
    assert not direct.is_package


def test_convert_legacy_project_preserves_contents_and_rebases_internal_paths(
    tmp_path,
):
    legacy_root = tmp_path / "AA23"
    _write_legacy_project(legacy_root, name="AA23")

    internal_source = legacy_root / "source"
    internal_output = legacy_root / "output"
    external_delivery = tmp_path / "Google Drive" / "SETORAN"
    internal_source.mkdir(parents=True)
    internal_output.mkdir(parents=True)
    external_delivery.mkdir(parents=True)

    manager = ProjectManager()
    project = manager.open(legacy_root)
    project.settings.source_folder = str(internal_source)
    project.settings.stem_output_folder = str(internal_output)
    project.settings.delivery_folder = str(external_delivery)
    project.save()

    backup_marker = project.backups_folder / "marker.txt"
    log_marker = project.logs_folder / "marker.log"
    backup_marker.write_text("backup", encoding="utf-8")
    log_marker.write_text("log", encoding="utf-8")

    converted = manager.convert_current_to_package()

    expected_root = tmp_path / "AA23.drsp"
    assert converted.root == expected_root
    assert converted.is_package
    assert not legacy_root.exists()
    assert expected_root.is_dir()

    assert (expected_root / "backups" / "marker.txt").read_text(
        encoding="utf-8"
    ) == "backup"
    assert (expected_root / "logs" / "marker.log").read_text(
        encoding="utf-8"
    ) == "log"

    assert converted.settings.source_folder == str(
        expected_root / "source"
    )
    assert converted.settings.stem_output_folder == str(
        expected_root / "output"
    )
    assert converted.settings.delivery_folder == str(external_delivery)
    assert converted.settings.project_folder == str(expected_root)

    payload = json.loads(
        converted.project_file.read_text(encoding="utf-8")
    )
    assert payload["package_type"] == PROJECT_PACKAGE_TYPE

    audit = AuditService(converted.database).recent(1)
    assert audit
    assert audit[0].action == "CONVERT_TO_DRSP"


def test_convert_legacy_project_refuses_existing_target(tmp_path):
    legacy_root = tmp_path / "Legacy"
    _write_legacy_project(legacy_root)
    target = tmp_path / "Legacy.drsp"
    target.mkdir()

    manager = ProjectManager()
    manager.open(legacy_root)

    with pytest.raises(ProjectError, match="Target .drsp"):
        manager.convert_current_to_package()

    assert legacy_root.is_dir()
    assert target.is_dir()
    assert manager.current is not None
    assert manager.current.root == legacy_root


def test_drsp_path_that_is_a_regular_file_is_rejected(tmp_path):
    fake = tmp_path / "Broken.drsp"
    fake.write_text("not a package", encoding="utf-8")

    with pytest.raises(ProjectFormatError, match="directory"):
        Project.load(fake)


def test_project_ui_uses_package_folder_open_and_exposes_conversion():
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

    assert "QFileDialog.getExistingDirectory" in main_window
    assert '"Open Project Package (.drsp or Legacy Folder)"' in main_window
    assert "def convert_project_to_drsp" in main_window
    assert '"tools.convert_drsp": self.convert_project_to_drsp' in main_window

    assert 'QPushButton("Convert to .drsp")' in tools_page
    assert '"tools.convert_drsp"' in tools_page
    assert '("tools.convert_drsp", "Convert to .drsp")' in ribbon
    assert "writable .drsp directory package" in new_dialog

    assert "len(sys.argv) > 1" in main_py
    assert "window.open_project_path(candidate)" in main_py
