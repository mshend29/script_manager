from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from core.project import Project
from core.project_manager import ProjectError, ProjectManager
from core.project_settings import ProjectSettings
from core.recent_projects import RecentProjectsStore


def _settings() -> ProjectSettings:
    return ProjectSettings(
        project_name="Lifecycle Project",
        project_code="LC01",
        client_name="Client Lifecycle",
        start_date="2026-09-07",
        source_folder="G:/Client/LC01/Scripts",
        episode_before="EP",
        episode_after="_",
        stem_output_folder="G:/Client/LC01/Stem",
        delivery_folder="G:/Client/LC01/Delivery",
        audio_format="WAV",
        audio_sample_rate=48000,
        audio_bit_depth=24,
        audio_channels=1,
        main_drive_url="https://example.com/main",
        material_drive_url="https://example.com/material",
        delivery_drive_url="https://example.com/delivery",
    )


def test_create_save_close_reopen_preserves_identity_and_settings(tmp_path):
    manager = ProjectManager()
    created = manager.create(_settings(), tmp_path)
    original_file = created.project_file
    original_id = created.project_id

    created.settings.client_name = "Client Setelah Save"
    manager.save()
    manager.close()

    assert manager.current is None
    assert original_file.is_file()

    reopened = manager.open(original_file)
    assert reopened.project_id == original_id
    assert reopened.project_file == original_file
    assert reopened.settings.project_name == "Lifecycle Project"
    assert reopened.settings.project_code == "LC01"
    assert reopened.settings.client_name == "Client Setelah Save"
    assert reopened.settings.project_folder == str(original_file)
    assert original_file.name == "LC01 - Lifecycle Project.smproj"


def test_save_as_preserves_project_identity_and_does_not_rename_source(tmp_path):
    manager = ProjectManager()
    created = manager.create(_settings(), tmp_path / "source")
    source_file = created.project_file
    project_id = created.project_id

    target = tmp_path / "save-as" / "Operator Chosen Name.smproj"
    saved = manager.save_as(target)

    assert source_file.is_file()
    assert source_file.name == "LC01 - Lifecycle Project.smproj"
    assert saved.project_file == target.resolve(strict=False)
    assert saved.project_id == project_id
    assert saved.settings.project_name == "Lifecycle Project"
    assert saved.settings.project_code == "LC01"
    assert saved.settings.project_folder == str(target.resolve(strict=False))

    reopened_source = ProjectManager().open(source_file)
    assert reopened_source.project_id == project_id
    assert reopened_source.project_file == source_file


def test_duplicate_gets_new_identity_but_preserves_project_configuration(tmp_path):
    manager = ProjectManager()
    source = manager.create(_settings(), tmp_path / "source")
    source_id = source.project_id
    source_file = source.project_file

    target = tmp_path / "duplicate" / "Duplicate Target.smproj"
    duplicate = manager.duplicate(target)

    assert source_file.is_file()
    assert duplicate.project_file == target.resolve(strict=False)
    assert duplicate.project_id != source_id
    assert duplicate.settings.project_name == source.settings.project_name
    assert duplicate.settings.project_code == source.settings.project_code
    assert duplicate.settings.client_name == source.settings.client_name
    assert duplicate.settings.project_folder == str(target.resolve(strict=False))

    source_again = ProjectManager().open(source_file)
    assert source_again.project_id == source_id


def test_recover_from_backup_preserves_backup_identity_and_leaves_backup_untouched(
    tmp_path,
):
    source_manager = ProjectManager()
    source = source_manager.create(_settings(), tmp_path / "source")
    source_id = source.project_id
    source_manager.save()

    backup = tmp_path / "backup" / "LC01 Backup.smproj"
    backup.parent.mkdir(parents=True)
    shutil.copy2(source.project_file, backup)

    target = tmp_path / "recovered" / "LC01 Recovered.smproj"
    recovered = ProjectManager().recover_from_backup(
        backup,
        target,
        expected_project_id=source_id,
    )

    assert backup.is_file()
    assert recovered.project_file == target.resolve(strict=False)
    assert recovered.project_id == source_id
    assert recovered.settings.project_name == "Lifecycle Project"
    assert recovered.settings.project_code == "LC01"
    assert recovered.settings.project_folder == str(target.resolve(strict=False))


def test_lifecycle_targets_never_overwrite_existing_smproj(tmp_path):
    manager = ProjectManager()
    manager.create(_settings(), tmp_path / "source")

    existing = tmp_path / "existing.smproj"
    existing.write_bytes(b"do-not-overwrite")
    original_bytes = existing.read_bytes()

    with pytest.raises(ProjectError, match="sudah ada"):
        manager.save_as(existing)
    assert existing.read_bytes() == original_bytes

    with pytest.raises(ProjectError, match="sudah ada"):
        manager.duplicate(existing)
    assert existing.read_bytes() == original_bytes


def test_recent_projects_tracks_current_path_without_duplicate_identity(tmp_path):
    manager = ProjectManager()
    project = manager.create(_settings(), tmp_path / "source")
    store = RecentProjectsStore(tmp_path / "recent.json")

    store.add(
        project_id=project.project_id,
        project_name=project.settings.project_name,
        file_path=project.project_file,
    )
    first_path = project.project_file

    save_as_target = tmp_path / "save-as" / "Moved By User.smproj"
    saved = manager.save_as(save_as_target)
    store.replace_project_path(
        project_id=saved.project_id,
        old_path=first_path,
        new_path=saved.project_file,
        project_name=saved.settings.project_name,
    )

    items = store.list(existing_only=True)
    assert len(items) == 1
    assert items[0].project_id == project.project_id
    assert Path(items[0].file_path) == saved.project_file

    duplicate = manager.duplicate(tmp_path / "duplicate" / "Clone.smproj")
    store.add(
        project_id=duplicate.project_id,
        project_name=duplicate.settings.project_name,
        file_path=duplicate.project_file,
    )
    items = store.list(existing_only=True)
    assert [item.project_id for item in items] == [
        duplicate.project_id,
        saved.project_id,
    ]


def test_legacy_filename_opens_closes_and_reopens_without_auto_rename(tmp_path):
    legacy_path = tmp_path / "AA23.smproj"
    legacy = Project(
        file_path=legacy_path,
        settings=ProjectSettings(
            project_name="Legacy Project",
            project_code="AA23",
            client_name="Legacy Client",
        ),
        project_id="legacy-lifecycle-id",
    )
    legacy.save()

    manager = ProjectManager()
    opened = manager.open(legacy_path)
    assert opened.project_file == legacy_path
    assert opened.project_id == "legacy-lifecycle-id"

    manager.save()
    manager.close()
    reopened = manager.open(legacy_path)

    assert reopened.project_file == legacy_path
    assert reopened.project_id == "legacy-lifecycle-id"
    assert legacy_path.is_file()
    assert not (tmp_path / "AA23 - Legacy Project.smproj").exists()


def test_smproj_file_association_entrypoint_contract_remains_available():
    root = Path(__file__).resolve().parents[1]
    main_py = (root / "main.py").read_text(encoding="utf-8")
    main_window = (root / "app" / "main_window.py").read_text(encoding="utf-8")
    project_py = (root / "core" / "project.py").read_text(encoding="utf-8")

    # The entrypoint accepts a filesystem argument and delegates format
    # validation to the normal open-project path. Keeping suffix validation in
    # Project/ProjectManager avoids a second file-format policy in main.py.
    assert "project_args = [" in main_py
    assert "candidate = Path(project_args[0]).expanduser()" in main_py
    assert "window.open_project_path(candidate)" in main_py
    assert "Proyek Script Manager (*.smproj)" in main_window
    assert 'PROJECT_FILE_EXTENSION = ".smproj"' in project_py
