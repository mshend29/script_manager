from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "packaging" / "ScriptManager.iss"
WINDOWS_WORKFLOW = ROOT / ".github" / "workflows" / "windows-package.yml"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_installer_uses_only_official_google_drive_download_endpoint() -> None:
    text = _text(INSTALLER)

    assert (
        "https://dl.google.com/drive-file-stream/GoogleDriveSetup.exe"
        in text
    )
    assert "DownloadTemporaryFile(" in text
    assert "GoogleDriveSetup.exe" in text
    assert "Source: \"GoogleDriveSetup.exe\"" not in text
    assert "Source: \"..\\GoogleDriveSetup.exe\"" not in text


def test_google_drive_install_requires_interactive_wizard_choice() -> None:
    text = _text(INSTALLER)

    assert "Install Google Drive & Lanjut" in text
    assert "Saya akan mengaturnya sendiri" in text
    assert "NextButtonClick" in text
    assert "SelectedValueIndex = 0" in text
    assert "--silent --gsuite_shortcuts=false" in text


def test_silent_setup_never_triggers_google_drive_download() -> None:
    text = _text(INSTALLER)

    assert "WizardSilent" in text
    assert "SKIPDRIVEPREREQ" in text
    assert "SkipGoogleDrivePrerequisite" in text


def test_installer_detection_uses_documented_google_uninstall_guid() -> None:
    text = _text(INSTALLER)

    assert "{6BBAE539-2232-434A-A4E5-9A33560C6283}" in text
    assert "RegKeyExists(HKLM32" in text
    assert "RegKeyExists(HKLM64" in text
    assert "G:\\" not in text


def test_windows_package_smoke_uses_explicit_external_prerequisite_bypass() -> None:
    text = _text(WINDOWS_WORKFLOW)

    assert "pull_request:" in text
    assert '"packaging/**"' in text
    assert '"/SKIPDRIVEPREREQ=1"' in text
    assert "ScriptManager.exe\" --smoke-test" in text
    assert ".smproj association was not registered" in text


def test_release_smoke_uses_same_prerequisite_bypass() -> None:
    text = _text(RELEASE_WORKFLOW)

    assert '"/SKIPDRIVEPREREQ=1"' in text
    assert "Publish GitHub Release" in text
    assert "verify_published_release.py" in text
