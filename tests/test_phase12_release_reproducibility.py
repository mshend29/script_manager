from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_package_generates_release_candidate_checksums() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "windows-package.yml"
    ).read_text(encoding="utf-8")

    assert "Generate release candidate checksums" in workflow
    assert "Get-FileHash -Algorithm SHA256" in workflow
    assert "ScriptManager-$version-SHA256.txt" in workflow
    assert "Upload release candidate checksums" in workflow
    assert "ScriptManager-windows-checksums" in workflow


def test_release_workflow_matches_machine_wide_installer_contract() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")

    assert 'python -m pip install -r requirements-release.txt' in workflow
    assert 'choco install innosetup --version=6.7.1' in workflow
    assert '--diagnostics-smoke-test' in workflow
    assert '[Microsoft.Win32.Registry]::LocalMachine.OpenSubKey(' in workflow
    assert 'Software\\Classes\\.smproj' in workflow
    assert '[Microsoft.Win32.Registry]::CurrentUser.OpenSubKey(' not in workflow
    assert 'Get-FileHash -Algorithm SHA256' in workflow
    assert 'gh release create' in workflow
    assert 'scripts/verify_published_release.py' in workflow


def test_release_tag_must_match_application_version() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")

    assert '$expectedTag = "v$version"' in workflow
    assert 'does not match APP_VERSION' in workflow
