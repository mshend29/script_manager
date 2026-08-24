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


def _worker_connect_call(
    function: ast.FunctionDef,
    signal_name: str,
) -> ast.Call:
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "connect":
            continue
        signal = node.func.value
        if (
            isinstance(signal, ast.Attribute)
            and signal.attr == signal_name
            and isinstance(signal.value, ast.Name)
            and signal.value.id == "worker"
        ):
            return node
    raise AssertionError(f"worker.{signal_name}.connect(...) not found")


def _is_self_method(node: ast.AST, method_name: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == method_name
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


def _is_queued_connection(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "QueuedConnection"
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "ConnectionType"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "Qt"
    )


def _has_slot_object_decorator(function: ast.FunctionDef) -> bool:
    for decorator in function.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        if not isinstance(decorator.func, ast.Name) or decorator.func.id != "Slot":
            continue
        if (
            len(decorator.args) == 1
            and isinstance(decorator.args[0], ast.Name)
            and decorator.args[0].id == "object"
        ):
            return True
    return False


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


def test_worker_results_are_queued_to_main_window_slots_not_lambdas():
    main_path = ROOT / "app" / "main_window.py"
    main_run = _method(main_path, "MainWindow", "_run_source_sync")

    completed = _worker_connect_call(main_run, "completed")
    failed = _worker_connect_call(main_run, "failed")

    assert len(completed.args) >= 2
    assert len(failed.args) >= 2

    assert _is_self_method(completed.args[0], "_source_sync_completed")
    assert _is_self_method(failed.args[0], "_source_sync_failed")
    assert not isinstance(completed.args[0], ast.Lambda)
    assert not isinstance(failed.args[0], ast.Lambda)

    assert _is_queued_connection(completed.args[1])
    assert _is_queued_connection(failed.args[1])


def test_source_sync_result_handlers_are_qt_object_slots():
    main_path = ROOT / "app" / "main_window.py"
    completed = _method(main_path, "MainWindow", "_source_sync_completed")
    failed = _method(main_path, "MainWindow", "_source_sync_failed")

    assert _has_slot_object_decorator(completed)
    assert _has_slot_object_decorator(failed)


def test_project_close_is_guarded_while_source_sync_runs():
    close_event = _method(
        ROOT / "app" / "main_window.py",
        "MainWindow",
        "closeEvent",
    )

    calls = _called_attributes(close_event)
    assert "_source_sync_running" in calls
    assert "ignore" in calls
