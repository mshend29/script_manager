from __future__ import annotations

from pathlib import Path

import pytest

from core.project import Project
from core.project_filename import (
    format_new_project_filename,
    new_project_destination,
)
from core.project_manager import ProjectError, ProjectManager
from core.project_settings import (
    NEW_PROJECT_BLOCKING_FIELDS,
    NEW_PROJECT_OPTIONAL_FIELDS,
    PROJECT_SETTINGS_FIELD_GROUPS,
    ProjectSettings,
    validate_project_settings_contract,
)


def test_project_settings_contract_covers_all_phase11_persistent_fields():
    flattened = {
        field
        for fields in PROJECT_SETTINGS_FIELD_GROUPS.values()
        for field in fields
    }
    assert flattened == {
        "project_name",
        "project_code",
        "client_name",
        "start_date",
        "source_folder",
        "episode_before",
        "episode_after",
        "stem_output_folder",
        "delivery_folder",
        "audio_format",
        "audio_sample_rate",
        "audio_bit_depth",
        "audio_channels",
        "main_drive_url",
        "material_drive_url",
        "delivery_drive_url",
    }
    assert NEW_PROJECT_OPTIONAL_FIELDS == {
        "main_drive_url",
        "material_drive_url",
        "delivery_drive_url",
    }
    assert {
        "project_name",
        "project_code",
        "client_name",
        "start_date",
        "source_folder",
        "stem_output_folder",
        "delivery_folder",
    }.issubset(NEW_PROJECT_BLOCKING_FIELDS)


def test_project_folder_remains_runtime_only_and_normalization_is_shared(tmp_path):
    settings = ProjectSettings(
        project_name="  AA23  ",
        project_code="  A23  ",
        client_name="  Client  ",
        project_folder=str(tmp_path / "AA23.smproj"),
        source_folder=f"  {tmp_path / 'source'}  ",
        audio_format="mp3",
        audio_sample_rate=88200,
        audio_bit_depth=20,
        audio_channels=6,
    ).normalized()

    assert settings.project_name == "AA23"
    assert settings.project_code == "A23"
    assert settings.client_name == "Client"
    assert settings.audio_format == "WAV"
    assert settings.audio_sample_rate == 48000
    assert settings.audio_bit_depth == 24
    assert settings.audio_channels == 1
    assert "project_folder" not in settings.to_persistent_dict()


def test_basic_contract_validation_distinguishes_new_project_requirements():
    settings = ProjectSettings(
        project_name="AA23",
        project_code="AA23",
        client_name="Client",
    )
    basic = validate_project_settings_contract(settings)
    assert not basic

    strict = validate_project_settings_contract(
        settings,
        strict_new_project=True,
    )
    assert {issue.field for issue in strict} == {
        "source_folder",
        "stem_output_folder",
        "delivery_folder",
    }


def test_official_new_project_filename_normal():
    assert (
        format_new_project_filename("AA23", "Cinta di Ujung Senja")
        == "AA23 - Cinta di Ujung Senja.smproj"
    )


def test_official_new_project_filename_preserves_valid_unicode():
    assert (
        format_new_project_filename("中文01", "Cinta di 東京")
        == "中文01 - Cinta di 東京.smproj"
    )


def test_official_new_project_filename_sanitizes_windows_invalid_characters():
    assert (
        format_new_project_filename("AA:23", 'Cinta/Final? "OK"')
        == "AA_23 - Cinta_Final_ _OK_.smproj"
    )


def test_official_new_project_filename_strips_duplicate_smproj_suffixes():
    assert (
        format_new_project_filename("AA23.smproj", "Cinta.smproj.smproj")
        == "AA23 - Cinta.smproj"
    )


def test_official_new_project_filename_collapses_whitespace():
    assert (
        format_new_project_filename("  AA   23  ", "  Cinta\n  Senja ")
        == "AA 23 - Cinta Senja.smproj"
    )


def test_project_manager_preview_and_create_use_same_filename_rule(tmp_path):
    manager = ProjectManager()
    settings = ProjectSettings(
        project_name="Cinta/Final",
        project_code="AA:23",
    )

    preview = manager.preview_new_project_file(settings, tmp_path)
    assert preview == new_project_destination(
        tmp_path,
        "AA:23",
        "Cinta/Final",
    )

    project = manager.create(settings, tmp_path)
    assert project.project_file == preview
    assert project.settings.project_name == "Cinta/Final"
    assert project.settings.project_code == "AA:23"


def test_project_manager_detects_existing_destination_before_overwrite(tmp_path):
    manager = ProjectManager()
    settings = ProjectSettings(
        project_name="Project",
        project_code="AA23",
    )
    manager.create(settings, tmp_path)

    with pytest.raises(ProjectError, match="sudah ada"):
        ProjectManager().create(settings, tmp_path)


def test_existing_legacy_named_smproj_still_opens_without_rename(tmp_path):
    legacy_path = tmp_path / "AA23.smproj"
    legacy = Project(
        file_path=legacy_path,
        settings=ProjectSettings(
            project_name="Legacy Project",
            project_code="AA23",
        ),
        project_id="legacy-phase11",
    )
    legacy.save()

    opened = ProjectManager().open(legacy_path)
    assert opened.project_file == legacy_path
    assert legacy_path.is_file()
    assert not (tmp_path / "AA23 - Legacy Project.smproj").exists()
