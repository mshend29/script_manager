from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_package_checks_install_over_existing_and_uninstall_safety() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "windows-package.yml"
    ).read_text(encoding="utf-8")

    assert "ASSOC_SENTINEL_ROOT" in workflow
    assert "source-sentinel.xlsx" in workflow
    assert "audio-sentinel.wav" in workflow
    assert "delivery-sentinel.txt" in workflow
    assert "backup-sentinel.smproj.bak" in workflow

    assert "Install-over-existing smoke failed" in workflow
    assert "Installed runtime failed after install-over-existing" in workflow
    assert "External .smproj was removed by uninstall" in workflow
    assert "External user-data sentinel was removed by uninstall" in workflow
    assert "ScriptManager.Project registration remains after uninstall" in workflow


def test_installer_defaults_to_program_files_and_machine_wide_registration() -> None:
    installer = (ROOT / "packaging" / "ScriptManager.iss").read_text(
        encoding="utf-8"
    )

    assert "DefaultDirName={autopf}\\Script Manager" in installer
    assert "PrivilegesRequired=admin" in installer
    assert 'Name: "{autoprograms}\\{#MyAppName}"' in installer
    assert 'Name: "{autodesktop}\\{#MyAppName}"' in installer
    assert 'Root: HKA; Subkey: "Software\\Classes\\.smproj"' in installer


def test_installer_keeps_project_and_external_data_outside_install_tree() -> None:
    installer = (ROOT / "packaging" / "ScriptManager.iss").read_text(
        encoding="utf-8"
    )

    # Release installer owns only its application files/registration. Project,
    # source, audio, delivery and backup paths must never be uninstall targets.
    assert "[UninstallDelete]" not in installer
    assert "*.smproj" not in installer
    assert "source_folder" not in installer
    assert "stem_output_folder" not in installer
    assert "delivery_folder" not in installer
