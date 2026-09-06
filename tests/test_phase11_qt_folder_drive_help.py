from __future__ import annotations

import importlib.util
import os

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PYSIDE_AVAILABLE = importlib.util.find_spec("PySide6") is not None

pytestmark = pytest.mark.skipif(
    not PYSIDE_AVAILABLE,
    reason="PySide6 is only installed in the Qt runtime CI job.",
)

if PYSIDE_AVAILABLE:
    from PySide6.QtWidgets import QApplication

    import dialogs.new_project_dialog as new_project_dialog_module
    import dialogs.project_settings_dialog as project_settings_dialog_module
    from core.project_settings import ProjectSettings
    from dialogs.new_project_dialog import NewProjectDialog
    from dialogs.project_settings_dialog import ProjectSettingsDialog
    from widgets.folder_drive_help import (
        FOLDER_DRIVE_HELP_TEXT,
        FolderDriveHelpDialog,
    )


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


def test_folder_drive_help_contains_phase11_minimum_content(qapp):
    text = FOLDER_DRIVE_HELP_TEXT

    assert "Folder filesystem" in text
    assert "Google Drive Desktop" in text
    assert r"G:\My Drive\Client\AA23\Scripts" in text
    assert "Tautan browser" in text
    assert "https://drive.google.com/drive/folders/..." in text
    assert "tidak digunakan aplikasi untuk membaca file" in text
    assert "harus tersedia dan tersinkron" in text
    assert "Jangan masukkan URL browser ke field Folder" in text

    dialog = FolderDriveHelpDialog()
    assert dialog.windowTitle() == "Bantuan Folder & Google Drive"
    assert dialog.isModal()
    dialog.close()
    qapp.processEvents()


def test_wizard_and_settings_help_buttons_use_same_reusable_helper(
    qapp,
    monkeypatch,
):
    calls: list[object] = []

    monkeypatch.setattr(
        new_project_dialog_module,
        "show_folder_drive_help",
        lambda parent: calls.append(parent),
    )
    wizard = NewProjectDialog()
    assert wizard.help_button.accessibleName() == "Bantuan folder dan Google Drive"
    wizard.help_button.click()
    qapp.processEvents()
    assert calls == [wizard]

    monkeypatch.setattr(
        project_settings_dialog_module,
        "show_folder_drive_help",
        lambda parent: calls.append(parent),
    )
    settings_dialog = ProjectSettingsDialog(ProjectSettings())
    assert settings_dialog.help_button.accessibleName() == (
        "Bantuan folder dan Google Drive"
    )
    settings_dialog.help_button.click()
    qapp.processEvents()
    assert calls == [wizard, settings_dialog]

    wizard.close()
    settings_dialog.close()
    qapp.processEvents()
