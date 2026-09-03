from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW = ROOT / "app" / "main_window.py"
CONTROLLER = ROOT / "app" / "source_sync_controller.py"
WORKER = ROOT / "app" / "source_sync_worker.py"


def _method(path: Path, class_name: str, method_name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return item
    raise AssertionError(f"{class_name}.{method_name} not found in {path}")


def _called_attributes(function: ast.FunctionDef) -> set[str]:
    return {
        node.func.attr
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    }


def _called_names(function: ast.FunctionDef) -> set[str]:
    return {
        node.func.id
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
    }


def _is_queued_connection(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "QueuedConnection"
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "ConnectionType"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "Qt"
    )


def _slot_signature(function: ast.FunctionDef) -> tuple[str, ...] | None:
    for decorator in function.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        if not isinstance(decorator.func, ast.Name) or decorator.func.id != "Slot":
            continue

        values: list[str] = []
        for arg in decorator.args:
            if isinstance(arg, ast.Name):
                values.append(arg.id)
            elif isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                values.append("str")
            else:
                values.append("?")
        return tuple(values)
    return None


def test_source_prepare_and_apply_run_in_worker_not_main_window() -> None:
    main_run = _method(
        MAIN_WINDOW,
        "MainWindow",
        "_run_source_sync",
    )
    worker_run = _method(
        WORKER,
        "SourceSyncWorker",
        "run",
    )

    main_attributes = _called_attributes(main_run)
    worker_attributes = _called_attributes(worker_run)

    assert "prepare" not in main_attributes
    assert "apply" not in main_attributes
    assert "start_prepare" in main_attributes
    assert {"prepare", "apply"} <= worker_attributes


def test_source_sync_controller_owns_qthread_and_worker_lifecycle() -> None:
    start = _method(
        CONTROLLER,
        "SourceSyncController",
        "_start",
    )

    assert {"QThread", "SourceSyncWorker"} <= _called_names(start)
    attributes = _called_attributes(start)
    assert {"moveToThread", "start", "connect"} <= attributes

    main_source = MAIN_WINDOW.read_text(encoding="utf-8")
    assert "_source_sync_thread" not in main_source
    assert "_source_sync_worker" not in main_source
    assert "SourceSyncWorker" not in main_source


def test_worker_results_are_queued_to_controller_slots_not_lambdas() -> None:
    start = _method(
        CONTROLLER,
        "SourceSyncController",
        "_start",
    )

    completed_calls: list[ast.Call] = []
    failed: ast.Call | None = None

    for node in ast.walk(start):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "connect":
            continue

        signal = node.func.value
        if not (
            isinstance(signal, ast.Attribute)
            and isinstance(signal.value, ast.Name)
            and signal.value.id == "worker"
        ):
            continue

        if signal.attr == "completed":
            completed_calls.append(node)
        elif signal.attr == "failed":
            failed = node

    assert len(completed_calls) == 2
    assert failed is not None

    targets = {
        call.args[0].attr
        for call in completed_calls
        if (
            call.args
            and isinstance(call.args[0], ast.Attribute)
            and isinstance(call.args[0].value, ast.Name)
            and call.args[0].value.id == "self"
        )
    }
    assert targets == {"_prepare_completed", "_apply_completed"}

    for call in [*completed_calls, failed]:
        assert len(call.args) >= 2
        assert not isinstance(call.args[0], ast.Lambda)
        assert _is_queued_connection(call.args[1])


def test_controller_worker_result_handlers_are_qt_slots() -> None:
    assert _slot_signature(
        _method(CONTROLLER, "SourceSyncController", "_prepare_completed")
    ) == ("object",)
    assert _slot_signature(
        _method(CONTROLLER, "SourceSyncController", "_apply_completed")
    ) == ("object",)
    assert _slot_signature(
        _method(CONTROLLER, "SourceSyncController", "_worker_failed")
    ) == ("object",)


def test_main_window_receives_contextual_controller_signals() -> None:
    assert _slot_signature(
        _method(MAIN_WINDOW, "MainWindow", "_source_sync_prepared")
    ) == ("str", "object")
    assert _slot_signature(
        _method(MAIN_WINDOW, "MainWindow", "_source_sync_applied")
    ) == ("str", "object")
    assert _slot_signature(
        _method(MAIN_WINDOW, "MainWindow", "_source_sync_failed")
    ) == ("str", "str", "object")


def test_controller_defers_apply_until_prepare_thread_finishes() -> None:
    queue = _method(
        CONTROLLER,
        "SourceSyncController",
        "apply_after_prepare",
    )
    finished = _method(
        CONTROLLER,
        "SourceSyncController",
        "_thread_finished",
    )

    queue_source = ast.unparse(queue)
    finished_source = ast.unparse(finished)

    assert "self.is_running" in queue_source
    assert "self._pending_report = report" in queue_source
    assert (
        'operation="apply"' in finished_source
        or "operation='apply'" in finished_source
    )


def test_project_close_is_guarded_while_source_sync_runs() -> None:
    close_event = _method(
        MAIN_WINDOW,
        "MainWindow",
        "closeEvent",
    )

    calls = _called_attributes(close_event)
    assert "_source_sync_running" in calls
    assert "ignore" in calls
