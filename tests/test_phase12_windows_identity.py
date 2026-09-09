from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pyinstaller_windows_identity_is_script_manager() -> None:
    spec = (ROOT / "packaging" / "ScriptManager.spec").read_text(
        encoding="utf-8"
    )

    for expected in (
        'StringStruct("CompanyName", "Script Manager")',
        'StringStruct("FileDescription", APP_NAME)',
        'StringStruct("InternalName", "ScriptManager")',
        'StringStruct("OriginalFilename", "ScriptManager.exe")',
        'StringStruct("ProductName", APP_NAME)',
        'StringStruct("ProductVersion", APP_VERSION)',
        'name="ScriptManager"',
        'console=False',
    ):
        assert expected in spec


def test_installer_identity_and_support_links_are_consistent() -> None:
    installer = (ROOT / "packaging" / "ScriptManager.iss").read_text(
        encoding="utf-8"
    )

    assert '#define MyAppName "Script Manager"' in installer
    assert '#define MyAppExeName "ScriptManager.exe"' in installer
    assert '#define MyAppPublisher "Script Manager"' in installer
    assert 'AppPublisherURL={#MyAppPublisherUrl}' in installer
    assert 'AppSupportURL={#MyAppSupportUrl}' in installer
    assert 'AppUpdatesURL={#MyAppUpdatesUrl}' in installer
    assert 'UninstallDisplayName={#MyAppName}' in installer
    assert 'UninstallDisplayIcon={app}\\{#MyAppExeName}' in installer
    assert 'ValueData: "Script Manager Project"' in installer

    for expected in (
        'VersionInfoVersion={#MyAppVersion}',
        'VersionInfoCompany={#MyAppPublisher}',
        'VersionInfoDescription={#MyAppName} Setup',
        'VersionInfoProductName={#MyAppName}',
        'VersionInfoProductVersion={#MyAppVersion}',
        'VersionInfoProductTextVersion={#MyAppVersion}',
    ):
        assert expected in installer


def test_windows_package_validates_real_exe_and_installer_version_resources() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "windows-package.yml"
    ).read_text(encoding="utf-8")

    assert "Verify Windows application identity" in workflow
    assert "$exe.VersionInfo" in workflow
    assert '$info.ProductName -ne "Script Manager"' in workflow
    assert '$info.FileDescription -ne "Script Manager"' in workflow
    assert '$info.OriginalFilename -ne "ScriptManager.exe"' in workflow
    assert "$info.ProductVersion -notlike" in workflow
    assert "$info.FileVersion -notlike" in workflow

    assert "Verify Windows installer identity" in workflow
    assert '(Get-Item $env:INSTALLER_EXE).VersionInfo' in workflow
    assert 'Unexpected installer ProductName' in workflow
    assert 'Unexpected installer FileDescription' in workflow
    assert 'Unexpected installer CompanyName' in workflow
    assert 'Unexpected installer ProductVersion' in workflow
    assert 'Unexpected installer FileVersion' in workflow
