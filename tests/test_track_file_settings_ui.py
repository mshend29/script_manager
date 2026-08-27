from __future__ import annotations

from pathlib import Path

from core.project_settings import ProjectSettings


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_project_settings_roundtrip_track_file_configuration(tmp_path):
    settings = ProjectSettings(
        project_name="AA23",
        stem_output_folder=str(tmp_path / "output"),
        delivery_folder=str(tmp_path / "setoran"),
        audio_format="wav",
        audio_sample_rate=48000,
        audio_bit_depth=24,
        audio_channels=1,
    ).normalized()

    restored = ProjectSettings.from_dict(settings.to_dict())
    assert restored.stem_output_folder.endswith("output")
    assert restored.delivery_folder.endswith("setoran")
    assert restored.audio_sample_rate == 48000
    assert restored.audio_bit_depth == 24
    assert restored.audio_channels == 1


def test_project_settings_dialog_exposes_drive_desktop_delivery_path_and_audio_spec():
    source = _read("dialogs/project_settings_dialog.py")

    assert "Stem / Mixdown / Export Folder" in source
    assert "Setoran Folder (Google Drive Desktop)" in source
    assert 'track_form.addRow("Audio Format"' in source
    assert 'track_form.addRow("Sample Rate"' in source
    assert 'track_form.addRow("Bit Depth"' in source
    assert 'track_form.addRow("Channels"' in source
    assert "settings.stem_output_folder" in source
    assert "settings.delivery_folder" in source


def test_ribbon_group_titles_use_compact_vertical_spacing():
    ribbon = _read("app/ribbon.py")
    theme = _read("app/theme.py")

    assert "root.setContentsMargins(9, 4, 9, 2)" in ribbon
    assert "padding: 0px 2px; margin: 0px;" in theme
    assert "min-height: 72px" in theme
