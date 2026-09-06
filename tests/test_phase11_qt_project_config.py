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
    from PySide6.QtWidgets import QApplication

    from widgets.project_configuration import (
        AudioOutputSection,
        DriveLinksSection,
        ProjectConfigurationSections,
        ProjectIdentitySection,
        SourceConfigurationSection,
    )


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


def test_reusable_configuration_sections_roundtrip_settings(qapp, tmp_path):
    original = ProjectSettings(
        project_name="AA23",
        project_code="A23",
        client_name="Client A",
        start_date="2026-09-06",
        source_folder=str(tmp_path / "source"),
        stem_output_folder=str(tmp_path / "stem"),
        delivery_folder=str(tmp_path / "delivery"),
        audio_sample_rate=96000,
        audio_bit_depth=32,
        audio_channels=2,
        episode_before="第",
        episode_after="集",
        main_drive_url="https://drive.google.com/main",
        material_drive_url="https://drive.google.com/material",
        delivery_drive_url="https://drive.google.com/delivery",
    )

    sections = ProjectConfigurationSections(
        identity=ProjectIdentitySection(original),
        source=SourceConfigurationSection(original),
        audio=AudioOutputSection(original),
        links=DriveLinksSection(original),
    )
    restored = sections.to_settings()

    assert restored.to_persistent_dict() == original.normalized().to_persistent_dict()

    replacement = ProjectSettings(
        project_name="BB01",
        project_code="BB",
        client_name="Client B",
        source_folder=str(tmp_path / "other-source"),
        stem_output_folder=str(tmp_path / "other-stem"),
        delivery_folder=str(tmp_path / "other-delivery"),
        audio_sample_rate=44100,
        audio_bit_depth=16,
        audio_channels=1,
        main_drive_url="https://example.com/main",
    )
    sections.load_settings(replacement)
    reloaded = sections.to_settings()

    assert reloaded.project_name == "BB01"
    assert reloaded.project_code == "BB"
    assert reloaded.client_name == "Client B"
    assert reloaded.source_folder.endswith("other-source")
    assert reloaded.stem_output_folder.endswith("other-stem")
    assert reloaded.delivery_folder.endswith("other-delivery")
    assert reloaded.audio_sample_rate == 44100
    assert reloaded.audio_bit_depth == 16
    assert reloaded.audio_channels == 1
    assert reloaded.main_drive_url == "https://example.com/main"
