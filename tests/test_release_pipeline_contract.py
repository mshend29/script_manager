from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_workflow_is_tag_gated_and_version_checked() -> None:
    source = (
        ROOT / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")

    assert 'tags:' in source
    assert '"v*.*.*"' in source
    assert "permissions:" in source
    assert "contents: write" in source
    assert "Validate release version" in source
    assert "APP_VERSION" in source
    assert "github.ref_name" in source


def test_release_builds_both_windows_assets_and_checksums() -> None:
    source = (
        ROOT / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")

    assert "packaging/ScriptManager.spec" in source
    assert "packaging\\ScriptManager.iss" in source
    assert "--smoke-test" in source
    assert "ScriptManager.Project" in source
    assert "SHA256" in source
    assert "gh release create" in source
    assert "--generate-notes" in source


def test_release_version_strategy_has_explicit_1_0_gate() -> None:
    source = (ROOT / "RELEASING.md").read_text(encoding="utf-8")

    assert "core/version.py -> APP_VERSION" in source
    assert "**Patch**" in source
    assert "**Minor**" in source
    assert "**1.0.0**" in source
    assert "Phase 9 release-readiness checklist is complete" in source
    assert "Check for Updates" in source
