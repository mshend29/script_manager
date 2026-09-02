from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_build_requirements_pin_supported_pyinstaller_major() -> None:
    content = (ROOT / "requirements-build.txt").read_text(encoding="utf-8")
    assert "pyinstaller>=6.22,<7" in content.casefold()


def test_pyinstaller_spec_builds_production_entrypoint_with_help_resources() -> None:
    spec = (ROOT / "packaging" / "ScriptManager.spec").read_text(
        encoding="utf-8"
    )

    assert 'project_root / "main.py"' in spec
    assert 'project_root / "resources"' in spec
    assert 'name="ScriptManager"' in spec
    assert "console=False" in spec
    assert "VSVersionInfo(" in spec
    assert "from core.version import APP_NAME, APP_VERSION" in spec
    assert 'StringStruct("FileVersion", APP_VERSION)' in spec
    assert 'StringStruct("ProductVersion", APP_VERSION)' in spec
    assert "version=version_info" in spec
    assert "COLLECT(" in spec


def test_windows_packaging_workflow_builds_and_smoke_tests_frozen_app() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "windows-package.yml"
    ).read_text(encoding="utf-8")

    assert "runs-on: windows-latest" in workflow
    assert 'python-version: "3.13"' in workflow
    assert "requirements-build.txt" in workflow
    assert "packaging/ScriptManager.spec" in workflow
    assert "ScriptManager.exe" in workflow
    assert "--smoke-test" in workflow
    assert "Compress-Archive" in workflow
    assert "actions/upload-artifact@v4" in workflow


def test_main_exposes_noninteractive_packaging_smoke_path() -> None:
    main = (ROOT / "main.py").read_text(encoding="utf-8")

    assert '"--smoke-test" in arguments' in main
    assert "app.processEvents()" in main
    assert "return 0" in main
