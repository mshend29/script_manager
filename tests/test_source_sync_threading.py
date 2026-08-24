from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _method(path: Path, class_name: str, method_name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return item
    raise AssertionError(f"{class_name}.{method_name} not found in {path}")


def _called_attributes(function: ast.FunctionDef) -> set[str]:
    result: set[str] = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            result.add(node.func.attr)
    return result


def _called_names(function: ast.FunctionDef) -> set[str]:
    result: set[str] = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            result.add(node.func.id)
    return result


def test_source_sync_engine_runs_in_worker_not_main_window():
    main_run = _method(
        ROOT / "app" / "main_window.py",
        "MainWindow",
        "_run_source_sync",
    )
    worker_run = _method(
        ROOT / "app" / "source_sync_worker.py",
        "SourceSyncWorker",
        "run",
    )

    main_attributes = _called_attributes(main_run)
    worker_attributes = _called_attributes(worker_run)

    assert "synchronize" not in main_attributes
    assert "synchronize" in worker_attributes


def test_main_window_starts_worker_on_qthread():
    main_run = _method(
        ROOT / "app" / "main_window.py",
        "MainWindow",
        "_run_source_sync",
    )

    assert {"QThread", "SourceSyncWorker"} <= _called_names(main_run)
    attributes = _called_attributes(main_run)
    assert {"moveToThread", "start", "connect"} <= attributes


def test_project_close_is_guarded_while_source_sync_runs():
    close_event = _method(
        ROOT / "app" / "main_window.py",
        "MainWindow",
        "closeEvent",
    )

    calls = _called_attributes(close_event)
    assert "_source_sync_running" in calls
    assert "ignore" in calls
