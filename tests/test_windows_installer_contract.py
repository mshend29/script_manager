from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_inno_installer_registers_smproj_per_user() -> None:
    source = (ROOT / "packaging" / "ScriptManager.iss").read_text(
        encoding="utf-8"
    )

    assert "PrivilegesRequired=lowest" in source
    assert "DefaultDirName={localappdata}\\Programs\\Script Manager" in source
    assert 'Subkey: "Software\\Classes\\.smproj"' in source
    assert 'ValueData: "{#MyAppProgId}"' in source
    assert 'ScriptManager.Project' in source
    assert "\\shell\\open\\command" in source
    assert '""%1""' in source
    assert "ChangesAssociations=yes" in source


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
    assert "Upload Windows installer" in workflow
