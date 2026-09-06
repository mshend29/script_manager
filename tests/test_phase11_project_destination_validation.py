from __future__ import annotations

from pathlib import Path

from core.project_filename import new_project_destination
from core.project_settings import ProjectSettings
from services.project_setup_validation import (
    create_project_destination_folder,
    looks_like_browser_url,
    validate_project_identity_destination,
)


def _settings(**overrides) -> ProjectSettings:
    values = {
        "project_name": "Cinta di Ujung Senja",
        "project_code": "AA23",
        "client_name": "Client A",
        "start_date": "2026-09-06",
    }
    values.update(overrides)
    return ProjectSettings(**values)


def test_project_destination_accepts_complete_identity_and_writable_folder(tmp_path):
    result = validate_project_identity_destination(
        _settings(),
        tmp_path,
        verify_writable=True,
    )

    assert result.is_valid
    assert result.issues == ()
    assert result.parent_folder == tmp_path
    assert result.destination_file == (
        tmp_path / "AA23 - Cinta di Ujung Senja.smproj"
    )
    assert not list(tmp_path.glob(".script_manager_write_test_*"))


def test_project_destination_blocks_missing_identity_and_invalid_date(tmp_path):
    result = validate_project_identity_destination(
        _settings(
            project_name="",
            project_code="",
            client_name="",
            start_date="06/09/2026",
        ),
        tmp_path,
    )

    assert result.is_valid is False
    fields = {issue.field for issue in result.issues}
    assert {
        "project_name",
        "project_code",
        "client_name",
        "start_date",
    } <= fields


def test_project_destination_rejects_browser_url():
    assert looks_like_browser_url("https://drive.google.com/drive/folders/example")
    result = validate_project_identity_destination(
        _settings(),
        "https://drive.google.com/drive/folders/example",
    )

    assert result.is_valid is False
    assert result.parent_folder is None
    assert result.destination_file is None
    assert "filesystem" in result.issues[0].message


def test_project_destination_rejects_file_instead_of_folder(tmp_path):
    target = tmp_path / "not-a-folder"
    target.write_text("x", encoding="utf-8")

    result = validate_project_identity_destination(_settings(), target)

    assert result.is_valid is False
    assert any(
        issue.field == "project_destination"
        and "bukan folder" in issue.message
        for issue in result.issues
    )


def test_missing_destination_folder_requires_explicit_create(tmp_path):
    target = tmp_path / "nested" / "projects"

    before = validate_project_identity_destination(_settings(), target)
    assert before.is_valid is False
    assert target.exists() is False
    assert any("Buat Folder" in issue.message for issue in before.issues)

    created = create_project_destination_folder(target)
    assert created == target
    assert target.is_dir()

    after = validate_project_identity_destination(
        _settings(),
        target,
        verify_writable=True,
    )
    assert after.is_valid


def test_project_destination_blocks_existing_smproj_collision(tmp_path):
    destination = new_project_destination(
        tmp_path,
        "AA23",
        "Cinta di Ujung Senja",
    )
    destination.write_bytes(b"existing")

    result = validate_project_identity_destination(_settings(), tmp_path)

    assert result.is_valid is False
    assert result.destination_file == destination
    assert any(issue.field == "project_file" for issue in result.issues)
