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


def test_project_settings_dialog_uses_two_tabs_and_constrained_wav_spec():
    source = _read("dialogs/project_settings_dialog.py")

    assert "QTabWidget" in source
    assert 'self.tabs.addTab(self._build_project_tab(settings), "Project")' in source
    assert '"Track Output & Delivery"' in source
    assert "filesystem path" in source
    assert "Google Drive Desktop" in source

    assert "Stem / Mixdown / Export Folder" in source
    assert "Setoran Folder (Google Drive Desktop)" in source
    assert 'format_value = QLabel("WAV")' in source
    assert "QSpinBox" not in source
    assert '("44.100 Hz", 44100)' in source
    assert '("48.000 Hz", 48000)' in source
    assert '("96.000 Hz", 96000)' in source
    assert '("192.000 Hz", 192000)' in source
    assert '("16-bit", 16)' in source
    assert '("24-bit", 24)' in source
    assert '("32-bit", 32)' in source
    assert '("Mono", 1)' in source
    assert '("Stereo", 2)' in source


def test_project_settings_source_filename_helper_replaces_manual_test_filename():
    source = _read("dialogs/project_settings_dialog.py")

    assert 'QPushButton("Get Source Filenames")' in source
    assert "read_source_filenames(self.source_folder.text())" in source
    assert "self.source_filename_example" in source
    assert 'QPushButton("Copy")' in source
    assert "Episode Preview:" in source
    assert 'QGroupBox("Episode Delimiter")' in source
    assert "filename_sample" not in source
    assert '"Test Filename"' not in source


def test_project_settings_normalizes_only_supported_wav_options():
    settings = ProjectSettings(
        audio_format="mp3",
        audio_sample_rate=88200,
        audio_bit_depth=20,
        audio_channels=6,
    ).normalized()

    assert settings.audio_format == "WAV"
    assert settings.audio_sample_rate == 48000
    assert settings.audio_bit_depth == 24
    assert settings.audio_channels == 1


def test_phase10_shell_uses_compact_navigation_and_header_spacing():
    sidebar = _read("widgets/sidebar_nav.py")
    header = _read("widgets/page_header.py")

    assert "root.setContentsMargins(10, 14, 10, 10)" in sidebar
    assert "root.setSpacing(6)" in sidebar
    assert "root.setContentsMargins(20, 10, 16, 10)" in header
    assert "self.setFixedHeight(78)" in header
