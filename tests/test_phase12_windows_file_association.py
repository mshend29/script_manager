from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_main_smoke_mode_can_exercise_project_open_path() -> None:
    source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "project_args = [" in source
    assert "project_open_ok = window.open_project_path(" in source
    assert "show_errors=not smoke_test" in source
    assert "if project_args and not project_open_ok:" in source
    assert "return 30" in source

    # The project path must be processed before the smoke-test early exit so
    # frozen CI exercises the same argv route used by Explorer file opening.
    assert source.index("project_args = [") < source.index("if smoke_test:")


def test_windows_package_opens_smproj_with_spaces_and_unicode() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "windows-package.yml"
    ).read_text(encoding="utf-8")

    assert "Create smproj path smoke fixture" in workflow
    assert "Script Manager Association – Uji" in workflow
    assert "ASSOC_SMOKE_PROJECT" in workflow
    assert '"$env:ASSOC_SMOKE_PROJECT" --smoke-test' in workflow
    assert "Frozen .smproj path-open smoke failed" in workflow
    assert "Installed .smproj path-open smoke failed" in workflow


def test_installer_association_quotes_project_argument() -> None:
    installer = (ROOT / "packaging" / "ScriptManager.iss").read_text(
        encoding="utf-8"
    )

    assert 'ValueData: """{app}\\{#MyAppExeName}"" ""%1"""' in installer
    assert 'ValueData: "Script Manager Project"' in installer
