from __future__ import annotations

from core.project_settings import ProjectSettings
from services.project_settings_change_validation import (
    settings_change_flags,
    validate_existing_project_settings_change,
)


def _baseline(tmp_path) -> ProjectSettings:
    return ProjectSettings(
        project_name="Existing",
        project_code="EX01",
        client_name="Client",
        start_date="2026-09-07",
        source_folder=str(tmp_path / "offline-source"),
        episode_before="EP",
        episode_after="_",
        stem_output_folder=str(tmp_path / "offline-stem"),
        delivery_folder=str(tmp_path / "offline-delivery"),
        main_drive_url="",
        material_drive_url="",
        delivery_drive_url="",
    )


def test_unchanged_offline_existing_folders_are_warnings_not_blockers(tmp_path):
    baseline = _baseline(tmp_path)

    result = validate_existing_project_settings_change(
        baseline,
        baseline,
        verify_writable=True,
    )

    assert result.is_valid
    assert not result.errors
    warning_fields = {issue.field for issue in result.warnings}
    assert {
        "source_folder",
        "stem_output_folder",
        "delivery_folder",
    }.issubset(warning_fields)
    assert any("tidak tersedia" in issue.message for issue in result.warnings)


def test_new_invalid_output_folder_blocks_save_even_if_other_existing_drive_is_offline(
    tmp_path,
):
    baseline = _baseline(tmp_path)
    candidate = ProjectSettings.from_dict(baseline.to_dict())
    candidate.stem_output_folder = str(tmp_path / "new-missing-stem")

    result = validate_existing_project_settings_change(
        baseline,
        candidate,
        verify_writable=True,
    )

    assert not result.is_valid
    assert any(
        issue.field == "stem_output_folder"
        and issue.severity == "error"
        for issue in result.issues
    )
    assert any(
        issue.field == "delivery_folder"
        and issue.severity == "warning"
        for issue in result.issues
    )


def test_changed_source_requires_valid_folder_and_delimiters(tmp_path):
    baseline = _baseline(tmp_path)
    source = tmp_path / "new-source"
    source.mkdir()
    (source / "AA23_EP001_SCRIPT.xlsx").write_bytes(b"filename-only")
    (source / "AA23_EP002_SCRIPT.xlsm").write_bytes(b"filename-only")

    candidate = ProjectSettings.from_dict(baseline.to_dict())
    candidate.source_folder = str(source)

    valid = validate_existing_project_settings_change(baseline, candidate)
    assert valid.is_valid
    assert valid.source_changed

    candidate.episode_before = "WRONG"
    invalid = validate_existing_project_settings_change(baseline, candidate)
    assert not invalid.is_valid
    assert any(
        issue.field == "source_filename"
        and issue.severity == "error"
        for issue in invalid.issues
    )


def test_optional_urls_can_be_empty_but_new_malformed_url_blocks(tmp_path):
    baseline = _baseline(tmp_path)
    same = validate_existing_project_settings_change(baseline, baseline)
    assert same.is_valid

    candidate = ProjectSettings.from_dict(baseline.to_dict())
    candidate.main_drive_url = "G:/Client/AA23"
    invalid = validate_existing_project_settings_change(baseline, candidate)

    assert not invalid.is_valid
    assert any(
        issue.field == "main_drive_url"
        and issue.severity == "error"
        for issue in invalid.issues
    )

    legacy = ProjectSettings.from_dict(baseline.to_dict())
    legacy.main_drive_url = "legacy-not-a-url"
    legacy_result = validate_existing_project_settings_change(legacy, legacy)
    assert legacy_result.is_valid
    assert any(
        issue.field == "main_drive_url"
        and issue.severity == "warning"
        for issue in legacy_result.issues
    )


def test_clearing_new_identity_value_blocks_but_unchanged_legacy_blank_warns(tmp_path):
    baseline = _baseline(tmp_path)
    candidate = ProjectSettings.from_dict(baseline.to_dict())
    candidate.client_name = ""

    result = validate_existing_project_settings_change(baseline, candidate)
    assert not result.is_valid
    assert any(
        issue.field == "client_name"
        and issue.severity == "error"
        for issue in result.issues
    )

    legacy = ProjectSettings.from_dict(baseline.to_dict())
    legacy.client_name = ""
    legacy_result = validate_existing_project_settings_change(legacy, legacy)
    assert legacy_result.is_valid
    assert any(
        issue.field == "client_name"
        and issue.severity == "warning"
        for issue in legacy_result.issues
    )


def test_change_flags_separate_source_tracking_and_links(tmp_path):
    baseline = _baseline(tmp_path)

    source = ProjectSettings.from_dict(baseline.to_dict())
    source.episode_after = "-"
    assert settings_change_flags(baseline, source) == (True, False, False)

    tracking = ProjectSettings.from_dict(baseline.to_dict())
    tracking.audio_channels = 2
    assert settings_change_flags(baseline, tracking) == (False, True, False)

    links = ProjectSettings.from_dict(baseline.to_dict())
    links.main_drive_url = "https://drive.google.com/drive/folders/example"
    assert settings_change_flags(baseline, links) == (False, False, True)
