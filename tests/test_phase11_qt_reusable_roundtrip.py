from __future__ import annotations

import importlib.util
import os

import pytest

from core.project_manager import ProjectManager
from core.project_settings import ProjectSettings


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PYSIDE_AVAILABLE = importlib.util.find_spec("PySide6") is not None

pytestmark = pytest.mark.skipif(
    not PYSIDE_AVAILABLE,
    reason="PySide6 is only installed in the Qt runtime CI job.",
)

if PYSIDE_AVAILABLE:
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QApplication

    from dialogs.project_settings_dialog import ProjectSettingsDialog
    from dialogs.transactional_new_project_dialog import TransactionalNewProjectDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


def _set_combo_data(combo, value: int) -> None:
    index = combo.findData(value)
    assert index >= 0
    combo.setCurrentIndex(index)


def test_new_project_and_project_settings_share_default_values(qapp):
    defaults = ProjectSettings().normalized().to_persistent_dict()

    wizard = TransactionalNewProjectDialog()
    settings_dialog = ProjectSettingsDialog(ProjectSettings())
    qapp.processEvents()

    assert wizard.sections.to_settings().to_persistent_dict() == defaults
    assert settings_dialog._collect_candidate().to_persistent_dict() == defaults

    wizard.close()
    settings_dialog.close()
    qapp.processEvents()


def test_new_project_smproj_reopen_settings_roundtrip_is_identical(qapp, tmp_path):
    project_parent = tmp_path / "Project Files"
    source = tmp_path / "Sumber Naskah 中文"
    stem = tmp_path / "Stem Export Audio"
    delivery = tmp_path / "Setoran 東京"
    for folder in (project_parent, source, stem, delivery):
        folder.mkdir()

    wizard = TransactionalNewProjectDialog()
    wizard.project_name.setText("  Proyek Roundtrip 東京  ")
    wizard.project_code.setText("  RT01  ")
    wizard.project_code.textEdited.emit("  RT01  ")
    wizard.client_name.setText("  Client Utama  ")
    wizard.start_date.setDate(QDate(2026, 9, 7))
    wizard.location_edit.setText(str(project_parent))

    wizard.source_folder.setText(f"  {source}  ")
    wizard.episode_before.setText("  EP  ")
    wizard.episode_after.setText("  _SCRIPT  ")

    wizard.stem_output_folder.setText(f"  {stem}  ")
    wizard.delivery_folder.setText(f"  {delivery}  ")
    _set_combo_data(wizard.audio_sample_rate, 96000)
    _set_combo_data(wizard.audio_bit_depth, 32)
    _set_combo_data(wizard.audio_channels, 2)

    wizard.main_drive_url.setText(
        "  https://drive.google.com/drive/folders/main  "
    )
    wizard.material_drive_url.setText(
        "  https://drive.google.com/drive/folders/material  "
    )
    wizard.delivery_drive_url.setText(
        "  https://drive.google.com/drive/folders/delivery  "
    )

    new_project_settings = wizard.sections.to_settings()
    expected = new_project_settings.to_persistent_dict()

    assert new_project_settings.project_name == "Proyek Roundtrip 東京"
    assert new_project_settings.project_code == "RT01"
    assert new_project_settings.client_name == "Client Utama"
    assert new_project_settings.start_date == "2026-09-07"
    assert new_project_settings.source_folder == str(source)
    assert new_project_settings.stem_output_folder == str(stem)
    assert new_project_settings.delivery_folder == str(delivery)
    assert new_project_settings.episode_before == "EP"
    assert new_project_settings.episode_after == "_SCRIPT"
    assert new_project_settings.audio_format == "WAV"
    assert new_project_settings.audio_sample_rate == 96000
    assert new_project_settings.audio_bit_depth == 32
    assert new_project_settings.audio_channels == 2

    manager = ProjectManager()
    created = manager.create(new_project_settings, project_parent)
    assert created.project_file.name == "RT01 - Proyek Roundtrip 東京.smproj"

    reopened = ProjectManager().open(created.project_file)
    assert reopened.settings.to_persistent_dict() == expected
    assert reopened.settings.project_folder == str(created.project_file)
    assert reopened.project_id == created.project_id
    assert reopened.created_at == created.created_at

    settings_dialog = ProjectSettingsDialog(reopened.settings)
    qapp.processEvents()
    settings_candidate = settings_dialog._collect_candidate()

    assert settings_candidate.to_persistent_dict() == expected
    assert settings_candidate.project_folder == str(created.project_file)
    assert settings_dialog.project_file is not None
    assert settings_dialog.project_file.edit.isReadOnly() is True
    assert settings_dialog.project_file.text() == str(created.project_file)

    # Explicit category-level assertions make any future drift easy to locate.
    for field in (
        "project_name",
        "project_code",
        "client_name",
        "start_date",
        "source_folder",
        "stem_output_folder",
        "delivery_folder",
        "audio_format",
        "audio_sample_rate",
        "audio_bit_depth",
        "audio_channels",
        "episode_before",
        "episode_after",
        "main_drive_url",
        "material_drive_url",
        "delivery_drive_url",
    ):
        assert getattr(settings_candidate, field) == getattr(new_project_settings, field)

    wizard.close()
    settings_dialog.close()
    qapp.processEvents()
