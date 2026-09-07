from __future__ import annotations

import importlib.util
import os

import pytest

from core.project_settings import ProjectSettings


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PYSIDE_AVAILABLE = importlib.util.find_spec("PySide6") is not None

pytestmark = pytest.mark.skipif(
    not PYSIDE_AVAILABLE,
    reason="PySide6 is only installed in the Qt runtime CI job.",
)

if PYSIDE_AVAILABLE:
    from PySide6.QtWidgets import QApplication, QDialog

    from dialogs.project_settings_dialog import ProjectSettingsDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


def _settings(tmp_path) -> ProjectSettings:
    return ProjectSettings(
        project_name="Cinta di Ujung Senja",
        project_code="AA23",
        client_name="Client A",
        start_date="2026-09-07",
        project_folder=str(tmp_path / "AA23 - Cinta di Ujung Senja.smproj"),
        source_folder=str(tmp_path / "source"),
        episode_before="EP",
        episode_after="_",
        stem_output_folder=str(tmp_path / "stem"),
        delivery_folder=str(tmp_path / "delivery"),
        audio_format="WAV",
        audio_sample_rate=96000,
        audio_bit_depth=32,
        audio_channels=2,
        main_drive_url="https://drive.google.com/drive/folders/main",
        material_drive_url="https://drive.google.com/drive/folders/material",
        delivery_drive_url="https://drive.google.com/drive/folders/delivery",
    )


def test_project_settings_has_four_tabs_aligned_with_new_project(qapp, tmp_path):
    settings = _settings(tmp_path)
    dialog = ProjectSettingsDialog(settings)
    dialog.show()
    qapp.processEvents()

    assert dialog.tabs.count() == 4
    assert [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())] == [
        "Proyek",
        "Sumber Naskah",
        "Audio & Setoran",
        "Tautan Drive",
    ]

    assert dialog.project_name.text() == settings.project_name
    assert dialog.project_code.text() == settings.project_code
    assert dialog.client_name.text() == settings.client_name
    assert dialog.project_file.text() == settings.project_folder
    assert dialog.project_file.edit.isReadOnly() is True
    assert dialog.project_file.browse_button.isEnabled() is False

    assert dialog.source_folder.text() == settings.source_folder
    assert dialog.episode_before.text() == "EP"
    assert dialog.episode_after.text() == "_"
    assert dialog.stem_output_folder.text() == settings.stem_output_folder
    assert dialog.delivery_folder.text() == settings.delivery_folder
    assert dialog.audio_sample_rate.currentData() == 96000
    assert dialog.audio_bit_depth.currentData() == 32
    assert dialog.audio_channels.currentData() == 2
    assert dialog.main_drive_url.text() == settings.main_drive_url
    assert dialog.material_drive_url.text() == settings.material_drive_url
    assert dialog.delivery_drive_url.text() == settings.delivery_drive_url

    dialog.close()
    qapp.processEvents()


def test_source_tab_keeps_filename_revalidation_and_settings_roundtrip(qapp, tmp_path):
    settings = _settings(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    (source / "AA23_EP001_SCRIPT.xlsx").write_bytes(b"filename-only")
    (source / "AA23_EP002_SCRIPT.xlsm").write_bytes(b"filename-only")

    dialog = ProjectSettingsDialog(settings)
    dialog.tabs.setCurrentIndex(1)
    result = dialog.source_section.validate_source_filenames()

    assert result.is_valid
    assert result.file_count == 2
    assert result.episode_numbers == (1, 2)
    assert "2 file sumber" in dialog.source_pattern_status.text()

    dialog.project_name.setText("Nama Revisi")
    dialog.audio_sample_rate.setCurrentIndex(
        dialog.audio_sample_rate.findData(48000)
    )
    dialog.main_drive_url.setText("https://example.com/project")
    dialog._accept_settings()
    qapp.processEvents()

    assert dialog.result() == QDialog.DialogCode.Accepted
    restored = dialog.result_settings
    assert restored.project_name == "Nama Revisi"
    assert restored.project_code == settings.project_code
    assert restored.project_folder == settings.project_folder
    assert restored.source_folder == settings.source_folder
    assert restored.episode_before == "EP"
    assert restored.episode_after == "_"
    assert restored.audio_sample_rate == 48000
    assert restored.audio_bit_depth == 32
    assert restored.audio_channels == 2
    assert restored.main_drive_url == "https://example.com/project"
    assert restored.material_drive_url == settings.material_drive_url
    assert restored.delivery_drive_url == settings.delivery_drive_url
