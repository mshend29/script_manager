from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_verifier_uses_real_update_service_contract() -> None:
    source = (
        ROOT / "scripts" / "verify_published_release.py"
    ).read_text(encoding="utf-8")

    assert "UpdateService(" in source
    assert "current_version=APP_VERSION" in source
    assert "UpdateStatus.UP_TO_DATE" in source
    assert "result.latest_version == APP_VERSION" in source
    assert "time.sleep" in source


def test_release_workflow_verifies_published_release_after_publish() -> None:
    source = (
        ROOT / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")

    publish_index = source.index("Publish GitHub Release")
    verify_index = source.index("Verify published release through updater")

    assert verify_index > publish_index
    assert "python scripts/verify_published_release.py" in source
