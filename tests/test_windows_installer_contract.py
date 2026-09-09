from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_inno_installer_registers_smproj_machine_wide() -> None:
    source = (ROOT / "packaging" / "ScriptManager.iss").read_text(
        encoding="utf-8"
    )

    assert "PrivilegesRequired=admin" in source
    assert "DefaultDirName={autopf}\\Script Manager" in source
    assert 'Root: HKA; Subkey: "Software\\Classes\\.smproj"' in source
    assert 'ValueData: "{#MyAppProgId}"' in source
    assert 'ValueData: "Script Manager Project"' in source
    assert 'ScriptManager.Project' in source
    assert "\\shell\\open\\command" in source
    assert '""%1""' in source
    assert "ChangesAssociations=yes" in source


def test_installer_exposes_product_support_and_update_links() -> None:
    source = (ROOT / "packaging" / "ScriptManager.iss").read_text(
        encoding="utf-8"
    )

    assert "https://github.com/mshend29/script_manager" in source
    assert "https://github.com/mshend29/script_manager/issues" in source
    assert "https://github.com/mshend29/script_manager/releases" in source
    assert "AppPublisherURL={#MyAppPublisherUrl}" in source
    assert "AppSupportURL={#MyAppSupportUrl}" in source
    assert "AppUpdatesURL={#MyAppUpdatesUrl}" in source


def test_windows_workflow_builds_and_smoke_tests_installer() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "windows-package.yml"
    ).read_text(encoding="utf-8")

    assert "choco install innosetup" in workflow
    assert "ScriptManager.iss" in workflow
    assert "installer-dist" in workflow
    assert "Silent install and association smoke test" in workflow
    assert "Software\\Classes\\.smproj" in workflow
    assert "ScriptManager.Project" in workflow
    assert "Script Manager Project" in workflow
    assert "Upload Windows installer" in workflow
