from __future__ import annotations

from core.project_settings import ProjectSettings
from services.folder_links_setup_validation import validate_folder_links_setup


def _settings(tmp_path, **overrides) -> ProjectSettings:
    source = tmp_path / "source"
    stem = tmp_path / "stem"
    delivery = tmp_path / "delivery"
    source.mkdir(exist_ok=True)
    stem.mkdir(exist_ok=True)
    delivery.mkdir(exist_ok=True)
    values = {
        "source_folder": str(source),
        "stem_output_folder": str(stem),
        "delivery_folder": str(delivery),
    }
    values.update(overrides)
    return ProjectSettings(**values)


def test_folder_links_allows_all_browser_links_to_be_empty(tmp_path):
    result = validate_folder_links_setup(_settings(tmp_path))

    assert result.is_valid is True
    assert result.errors == ()


def test_folder_links_accepts_http_and_https_links_without_network(tmp_path):
    settings = _settings(
        tmp_path,
        main_drive_url="https://drive.google.com/drive/folders/main",
        material_drive_url="http://example.test/material",
        delivery_drive_url="https://example.test/delivery",
    )

    result = validate_folder_links_setup(settings)

    assert result.is_valid is True


def test_folder_links_rejects_invalid_nonempty_url_values(tmp_path):
    result = validate_folder_links_setup(
        _settings(
            tmp_path,
            main_drive_url="G:/Client/AA23",
            material_drive_url="drive.google.com/folders/material",
        )
    )

    assert result.is_valid is False
    fields = {issue.field for issue in result.errors}
    assert "main_drive_url" in fields
    assert "material_drive_url" in fields


def test_folder_links_rejects_browser_url_in_operational_folder(tmp_path):
    settings = _settings(tmp_path)
    settings.source_folder = "https://drive.google.com/drive/folders/scripts"

    result = validate_folder_links_setup(settings)

    assert result.is_valid is False
    assert any(
        issue.field == "source_folder" and "filesystem path" in issue.message
        for issue in result.errors
    )


def test_folder_links_requires_operational_folder_values(tmp_path):
    settings = _settings(tmp_path)
    settings.delivery_folder = ""

    result = validate_folder_links_setup(settings)

    assert result.is_valid is False
    assert any(
        issue.field == "delivery_folder" for issue in result.errors
    )
