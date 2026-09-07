from __future__ import annotations

from core.project_settings import (
    PROJECT_SETTINGS_FIELD_GROUPS,
    ProjectSettings,
)


def _persistent_contract_fields() -> set[str]:
    return {
        field
        for fields in PROJECT_SETTINGS_FIELD_GROUPS.values()
        for field in fields
    }


def test_persistent_field_groups_cover_complete_project_settings_contract():
    persistent = ProjectSettings().to_persistent_dict()

    assert set(persistent) == _persistent_contract_fields()
    assert "project_folder" not in persistent


def test_default_persistent_values_roundtrip_without_drift():
    defaults = ProjectSettings()
    restored = ProjectSettings.from_dict(
        defaults.to_persistent_dict()
    ).normalized()

    assert restored.to_persistent_dict() == defaults.normalized().to_persistent_dict()
    assert restored.audio_format == "WAV"
    assert restored.audio_sample_rate == 48000
    assert restored.audio_bit_depth == 24
    assert restored.audio_channels == 1


def test_normalization_is_identical_before_and_after_persistence(tmp_path):
    raw = ProjectSettings(
        project_name="  Proyek Unicode 東京  ",
        project_code="  RT01  ",
        client_name="  Client A  ",
        start_date="  2026-09-07  ",
        project_folder="  /runtime/only.smproj  ",
        source_folder=f"  {tmp_path / 'Sumber Naskah 中文'}  ",
        stem_output_folder=f"  {tmp_path / 'Stem Export'}  ",
        delivery_folder=f"  {tmp_path / 'Setoran 東京'}  ",
        audio_format="MP3",
        audio_sample_rate=12345,
        audio_bit_depth=20,
        audio_channels=6,
        episode_before="  EP  ",
        episode_after="  _SCRIPT  ",
        main_drive_url="  https://drive.google.com/drive/folders/main  ",
        material_drive_url="  https://example.test/material  ",
        delivery_drive_url="  https://example.test/delivery  ",
    )

    normalized = raw.normalized()
    restored = ProjectSettings.from_dict(
        normalized.to_persistent_dict()
    ).normalized()

    assert restored.to_persistent_dict() == normalized.to_persistent_dict()
    assert restored.project_name == "Proyek Unicode 東京"
    assert restored.project_code == "RT01"
    assert restored.client_name == "Client A"
    assert restored.audio_format == "WAV"
    assert restored.audio_sample_rate == 48000
    assert restored.audio_bit_depth == 24
    assert restored.audio_channels == 1
    assert restored.episode_before == "EP"
    assert restored.episode_after == "_SCRIPT"


def test_runtime_project_file_never_leaks_into_persistent_settings():
    settings = ProjectSettings(
        project_name="Runtime Contract",
        project_folder="X:/Projects/Runtime Contract.smproj",
    )

    payload = settings.to_persistent_dict()
    restored = ProjectSettings.from_dict(payload)

    assert "project_folder" not in payload
    assert restored.project_folder == ""
