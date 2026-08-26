from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_unresolved_has_review_mode_and_manual_narration_actions():
    source = _read("pages/data_page.py")

    assert '["EPS", "ISSUE", "CHARACTER", "TALENT", "DIALOG", "SOURCE"]' in source
    assert 'addItem("Needs Review", "review")' in source
    assert 'addItem("Narration / Non-Dialogue", "narration")' in source
    assert 'addAction("Mark as Narration / Non-Dialogue")' in source
    assert 'addAction("Restore to Needs Review")' in source
    assert "self._review_service.mark_non_dialogue" in source
    assert "self._review_service.restore_to_review" in source


def test_validation_is_detailed_filterable_and_actionable():
    source = _read("pages/data_page.py")

    assert '["SEVERITY", "CATEGORY", "EPS", "ENTITY", "CODE", "MESSAGE", "ACTION"]' in source
    assert 'addItem("All Severity", None)' in source
    assert 'addItem("All Categories", None)' in source
    assert 'addItem("All Episodes", None)' in source
    assert 'setPlaceholderText("Search validation…")' in source
    assert "ACTION_REVIEW" in source
    assert "ACTION_SOURCES" in source
    assert "ACTION_TRACKING" in source
    assert "self._refresh_validation()" in source


def test_overview_distinguishes_review_system_and_workflow_health():
    source = _read("pages/data_page.py")

    assert '("non_dialogue", "Narration / Non-Dialogue")' in source
    assert '("needs_review", "Needs Review")' in source
    assert '("system_errors", "System Errors")' in source
    assert '("workflow_warnings", "Workflow Warnings")' in source
    assert '"✓ Project data healthy."' in source
