from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "packaging" / "ScriptManager.spec"
WINDOWS_WORKFLOW = ROOT / ".github" / "workflows" / "windows-package.yml"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
RELEASE_REQUIREMENTS = ROOT / "requirements-release.txt"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_release_dependencies_are_exactly_pinned() -> None:
    lines = [
        line.strip()
        for line in _text(RELEASE_REQUIREMENTS).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert lines == [
        "PySide6==6.11.2",
        "openpyxl==3.1.5",
        "pyinstaller==6.22.2",
    ]


def test_frozen_spec_is_windowed_versioned_and_resource_complete() -> None:
    text = _text(SPEC)

    assert 'name="ScriptManager"' in text
    assert "console=False" in text
    assert "version=version_info" in text
    assert 'StringStruct("ProductVersion", APP_VERSION)' in text
    assert '(str(project_root / "resources"), "resources")' in text
    assert 'project_root / "tests"' not in text
    assert "upx=False" in text
    assert "upx=True" not in text


def test_package_and_release_workflows_share_exact_dependency_lock() -> None:
    windows = _text(WINDOWS_WORKFLOW)
    release = _text(RELEASE_WORKFLOW)

    assert "pip install -r requirements-release.txt" in windows
    assert "pip install -r requirements-release.txt" in release
    assert "requirements-release.txt" in windows


def test_windows_package_still_runs_frozen_and_installer_smokes() -> None:
    text = _text(WINDOWS_WORKFLOW)

    assert "python -m PyInstaller --clean --noconfirm packaging/ScriptManager.spec" in text
    assert "ScriptManager.exe\" --smoke-test" in text
    assert "Build Windows installer" in text
    assert "Silent install and association smoke test" in text
    assert '"/SKIPDRIVEPREREQ=1"' in text
