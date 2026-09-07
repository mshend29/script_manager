from __future__ import annotations

from core.project_settings import ProjectSettings
from services.audio_setup_validation import (
    create_audio_output_folder,
    validate_audio_setup,
)


def _settings(stem, delivery, **overrides) -> ProjectSettings:
    values = {
        "stem_output_folder": str(stem),
        "delivery_folder": str(delivery),
    }
    values.update(overrides)
    return ProjectSettings(**values)


def test_audio_setup_requires_both_output_folders(tmp_path):
    result = validate_audio_setup(ProjectSettings())

    assert result.is_valid is False
    assert {issue.field for issue in result.errors} >= {
        "stem_output_folder",
        "delivery_folder",
    }


def test_audio_setup_missing_folders_offer_explicit_create(tmp_path):
    stem = tmp_path / "outputs" / "stem"
    delivery = tmp_path / "delivery"

    result = validate_audio_setup(_settings(stem, delivery))

    assert result.is_valid is False
    assert result.stem_folder.can_create is True
    assert result.delivery_folder.can_create is True
    assert stem.exists() is False
    assert delivery.exists() is False

    create_audio_output_folder(stem)
    create_audio_output_folder(delivery)

    assert stem.is_dir()
    assert delivery.is_dir()

    valid = validate_audio_setup(
        _settings(stem, delivery),
        verify_writable=True,
    )
    assert valid.is_valid is True
    assert not list(stem.glob(".script_manager_audio_write_test_*"))
    assert not list(delivery.glob(".script_manager_audio_write_test_*"))


def test_audio_setup_rejects_browser_url_and_file_path(tmp_path):
    delivery = tmp_path / "delivery"
    delivery.mkdir()
    not_folder = tmp_path / "stem.wav"
    not_folder.write_bytes(b"x")

    url_result = validate_audio_setup(
        _settings("https://drive.google.com/drive/folders/example", delivery)
    )
    assert url_result.is_valid is False
    assert any(
        issue.field == "stem_output_folder" and "URL browser" in issue.message
        for issue in url_result.errors
    )

    file_result = validate_audio_setup(_settings(not_folder, delivery))
    assert file_result.is_valid is False
    assert any(
        issue.field == "stem_output_folder" and "bukan folder" in issue.message
        for issue in file_result.errors
    )


def test_audio_setup_rejects_unsupported_audio_options(tmp_path):
    stem = tmp_path / "stem"
    delivery = tmp_path / "delivery"
    stem.mkdir()
    delivery.mkdir()

    result = validate_audio_setup(
        _settings(
            stem,
            delivery,
            audio_format="MP3",
            audio_sample_rate=12345,
            audio_bit_depth=20,
            audio_channels=6,
        )
    )

    assert result.is_valid is False
    fields = {issue.field for issue in result.errors}
    assert {
        "audio_format",
        "audio_sample_rate",
        "audio_bit_depth",
        "audio_channels",
    }.issubset(fields)


def test_audio_setup_keeps_project_defaults_supported(tmp_path):
    stem = tmp_path / "stem"
    delivery = tmp_path / "delivery"
    stem.mkdir()
    delivery.mkdir()

    settings = _settings(stem, delivery)
    result = validate_audio_setup(settings)

    assert result.is_valid is True
    assert settings.audio_format == "WAV"
    assert settings.audio_sample_rate == 48000
    assert settings.audio_bit_depth == 24
    assert settings.audio_channels == 1
