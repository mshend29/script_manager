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


def test_project_settings_dialog_uses_reusable_sections_and_constrained_wav_spec():
    dialog = _read("dialogs/project_settings_dialog.py")
    widgets = _read("widgets/project_configuration.py")

    assert "QTabWidget" in dialog
    assert "ProjectIdentitySection" in dialog
    assert "SourceConfigurationSection" in dialog
    assert "AudioOutputSection" in dialog
    assert "DriveLinksSection" in dialog
    assert "ProjectConfigurationSections" in dialog
    assert "Proyek" in dialog
    assert "Output Track & Setoran" in dialog
    assert "filesystem path" in dialog
    assert "Google Drive Desktop" in dialog

    assert "Stem / Mixdown / Export" in widgets
    assert "Folder Setoran" in widgets
    assert "Google Drive Desktop" in widgets
    assert 'self.format_value = QLabel("WAV")' in widgets
    assert "QSpinBox" not in widgets
    assert '44100: "44.100 Hz"' in widgets
    assert '48000: "48.000 Hz"' in widgets
    assert '96000: "96.000 Hz"' in widgets
    assert '192000: "192.000 Hz"' in widgets
    assert '16: "16-bit"' in widgets
    assert '24: "24-bit"' in widgets
    assert '32: "32-bit"' in widgets
    assert '1: "Mono"' in widgets
    assert '2: "Stereo"' in widgets


def test_project_settings_source_filename_helper_is_reusable():
    widgets = _read("widgets/project_configuration.py")

    assert "Baca Nama File Sumber" in widgets
    assert "read_source_filenames(self.source_folder.text())" in widgets
    assert "self.source_filename_example" in widgets
    assert "Salin" in widgets
    assert "Pratinjau Episode:" in widgets
    assert "Pemisah Episode" in widgets
    assert "extract_episode_number(" in widgets
    assert "filename_sample" not in widgets
    assert '"Test Filename"' not in widgets


def test_new_project_and_settings_share_the_same_configuration_sections():
    new_dialog = _read("dialogs/new_project_dialog.py")
    settings_dialog = _read("dialogs/project_settings_dialog.py")

    for section in (
        "ProjectIdentitySection",
        "SourceConfigurationSection",
        "AudioOutputSection",
        "DriveLinksSection",
        "ProjectConfigurationSections",
    ):
        assert section in new_dialog
        assert section in settings_dialog


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
