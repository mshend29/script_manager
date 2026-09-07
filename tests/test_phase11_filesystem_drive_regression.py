from __future__ import annotations

import os

from core.project_settings import ProjectSettings
from services import audio_setup_validation
from services.audio_setup_validation import validate_audio_setup
from services.folder_links_setup_validation import validate_folder_links_setup
from services.project_settings_change_validation import (
    validate_existing_project_settings_change,
)
from services.project_setup_validation import looks_like_browser_url


def _operational_settings(tmp_path) -> ProjectSettings:
    source = tmp_path / "Sumber Naskah 中文"
    stem = tmp_path / "Stem Export Audio"
    delivery = tmp_path / "Setoran Final 東京"
    source.mkdir()
    stem.mkdir()
    delivery.mkdir()
    return ProjectSettings(
        project_name="Filesystem Regression",
        project_code="FS01",
        client_name="Client",
        start_date="2026-09-07",
        source_folder=str(source),
        episode_before="EP",
        episode_after="_",
        stem_output_folder=str(stem),
        delivery_folder=str(delivery),
    )


def test_local_paths_with_spaces_and_unicode_are_valid_operational_folders(tmp_path):
    settings = _operational_settings(tmp_path)

    audio = validate_audio_setup(settings, verify_writable=True)
    links = validate_folder_links_setup(settings)

    assert audio.is_valid
    assert links.is_valid
    assert not links.errors


def test_google_drive_desktop_mapped_and_unc_shapes_are_filesystem_not_browser_urls():
    filesystem_paths = (
        r"G:\My Drive\Client\AA23\Scripts",
        r"Z:\Produksi\Client\AA23\Stem",
        r"\\server\share\Client\AA23\Setoran",
    )

    for value in filesystem_paths:
        assert looks_like_browser_url(value) is False

    assert looks_like_browser_url(
        "https://drive.google.com/drive/folders/example"
    ) is True


def test_changed_browser_url_in_folder_is_blocking_and_filesystem_value_in_url_is_blocking(
    tmp_path,
):
    baseline = _operational_settings(tmp_path)

    folder_candidate = ProjectSettings.from_dict(baseline.to_dict())
    folder_candidate.stem_output_folder = (
        "https://drive.google.com/drive/folders/stem"
    )
    folder_result = validate_existing_project_settings_change(
        baseline,
        folder_candidate,
    )
    assert not folder_result.is_valid
    assert any(
        issue.field == "stem_output_folder"
        and issue.severity == "error"
        and "URL browser" in issue.message
        for issue in folder_result.issues
    )

    url_candidate = ProjectSettings.from_dict(baseline.to_dict())
    url_candidate.main_drive_url = r"G:\My Drive\Client\AA23"
    url_result = validate_existing_project_settings_change(
        baseline,
        url_candidate,
    )
    assert not url_result.is_valid
    assert any(
        issue.field == "main_drive_url"
        and issue.severity == "error"
        for issue in url_result.issues
    )


def test_changed_read_only_output_folder_blocks_save(monkeypatch, tmp_path):
    baseline = _operational_settings(tmp_path)
    readonly = tmp_path / "Read Only Stem"
    readonly.mkdir()
    candidate = ProjectSettings.from_dict(baseline.to_dict())
    candidate.stem_output_folder = str(readonly)

    real_access = os.access

    def fake_access(path, mode):
        if str(path) == str(readonly) and mode == os.W_OK:
            return False
        return real_access(path, mode)

    monkeypatch.setattr(audio_setup_validation.os, "access", fake_access)

    result = validate_existing_project_settings_change(
        baseline,
        candidate,
        verify_writable=True,
    )

    assert not result.is_valid
    assert any(
        issue.field == "stem_output_folder"
        and issue.severity == "error"
        and "tidak dapat ditulis" in issue.message
        for issue in result.issues
    )


def test_unchanged_temporarily_unavailable_existing_folders_remain_warnings(tmp_path):
    baseline = ProjectSettings(
        project_name="Legacy Offline",
        project_code="OFF01",
        client_name="Client",
        start_date="2026-09-07",
        source_folder=str(tmp_path / "offline source"),
        stem_output_folder=str(tmp_path / "offline stem"),
        delivery_folder=str(tmp_path / "offline delivery"),
    )

    result = validate_existing_project_settings_change(
        baseline,
        baseline,
        verify_writable=True,
    )

    assert result.is_valid
    assert not result.errors
    assert {
        "source_folder",
        "stem_output_folder",
        "delivery_folder",
    }.issubset({issue.field for issue in result.warnings})


def test_new_project_source_must_not_equal_stem_or_delivery(tmp_path):
    settings = _operational_settings(tmp_path)

    source_equals_stem = ProjectSettings.from_dict(settings.to_dict())
    source_equals_stem.stem_output_folder = source_equals_stem.source_folder
    stem_result = validate_folder_links_setup(source_equals_stem)
    assert not stem_result.is_valid
    assert any(
        issue.field == "stem_output_folder"
        and issue.severity == "error"
        and "Sumber Naskah" in issue.message
        for issue in stem_result.issues
    )

    source_equals_delivery = ProjectSettings.from_dict(settings.to_dict())
    source_equals_delivery.delivery_folder = source_equals_delivery.source_folder
    delivery_result = validate_folder_links_setup(source_equals_delivery)
    assert not delivery_result.is_valid
    assert any(
        issue.field == "delivery_folder"
        and issue.severity == "error"
        and "Sumber Naskah" in issue.message
        for issue in delivery_result.issues
    )


def test_stem_equal_delivery_is_explicit_warning_not_blocker(tmp_path):
    settings = _operational_settings(tmp_path)
    settings.delivery_folder = settings.stem_output_folder

    result = validate_folder_links_setup(settings)

    assert result.is_valid
    assert not result.errors
    assert any(
        issue.field == "delivery_folder"
        and issue.severity == "warning"
        and "Stem" in issue.message
        and "Setoran" in issue.message
        for issue in result.warnings
    )


def test_existing_legacy_source_output_overlap_warns_but_new_overlap_blocks(tmp_path):
    baseline = _operational_settings(tmp_path)
    baseline.stem_output_folder = baseline.source_folder

    legacy = validate_existing_project_settings_change(baseline, baseline)
    assert legacy.is_valid
    assert any(
        issue.field == "stem_output_folder"
        and issue.severity == "warning"
        and "Sumber Naskah" in issue.message
        for issue in legacy.issues
    )

    clean = _operational_settings(tmp_path / "clean")
    candidate = ProjectSettings.from_dict(clean.to_dict())
    candidate.stem_output_folder = candidate.source_folder
    changed = validate_existing_project_settings_change(clean, candidate)

    assert not changed.is_valid
    assert any(
        issue.field == "stem_output_folder"
        and issue.severity == "error"
        and "Sumber Naskah" in issue.message
        for issue in changed.issues
    )
