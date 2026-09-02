from pathlib import Path


def test_workflow_has_fast_and_qt_runtime_jobs() -> None:
    workflow = Path(".github/workflows/tests.yml").read_text(
        encoding="utf-8"
    )

    assert "test:" in workflow
    assert "qt-runtime:" in workflow
    assert "QT_QPA_PLATFORM: offscreen" in workflow
    assert "python -m pip install -r requirements-dev.txt" in workflow
    assert "tests/test_script_page_runtime.py" in workflow
    assert "tests/test_qt_runtime_smoke.py" in workflow

    # Keep the existing lightweight engine job independent from PySide6 so
    # core regression feedback remains fast.
    fast_job = workflow.split("qt-runtime:", 1)[0]
    assert "python -m pip install pytest openpyxl" in fast_job
    assert "requirements-dev.txt" not in fast_job
