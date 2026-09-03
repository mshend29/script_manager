from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW = ROOT / "app" / "main_window.py"


def _method(path: Path, class_name: str, method_name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return item
    raise AssertionError(f"{class_name}.{method_name} not found")


def _called_attributes(function: ast.FunctionDef) -> set[str]:
    return {
        node.func.attr
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    }


def test_all_data_workspaces_expose_full_database_refresh_contract() -> None:
    pages = {
        "ScriptPage": ROOT / "pages" / "script_page.py",
        "DialogPage": ROOT / "pages" / "dialog_page.py",
        "TrackingPage": ROOT / "pages" / "tracking_page.py",
        "DataPage": ROOT / "pages" / "data_page.py",
    }

    for class_name, path in pages.items():
        refresh = _method(path, class_name, "refresh_from_database")
        assert "reload" in _called_attributes(refresh)


def test_main_window_source_apply_emits_project_data_revision() -> None:
    applied = _method(
        MAIN_WINDOW,
        "MainWindow",
        "_source_sync_applied",
    )
    calls = _called_attributes(applied)

    assert "mark_changed" in calls
    assert "emit" in calls
    assert "_refresh_current_data_page" not in calls


def test_tab_navigation_uses_lazy_dirty_refresh_helper() -> None:
    set_page = _method(MAIN_WINDOW, "MainWindow", "set_page")
    calls = _called_attributes(set_page)

    assert "_refresh_data_page_if_needed" in calls
    assert "set_database" not in calls


def test_data_revision_refreshes_visible_page_and_dashboard() -> None:
    changed = _method(
        MAIN_WINDOW,
        "MainWindow",
        "_project_data_revision_changed",
    )
    calls = _called_attributes(changed)

    assert "refresh_project_page" in calls
    assert "_refresh_data_page_if_needed" in calls


def test_workspace_mutation_keeps_origin_clean_and_siblings_dirty() -> None:
    changed = _method(
        MAIN_WINDOW,
        "MainWindow",
        "_workspace_data_changed",
    )
    calls = _called_attributes(changed)

    assert "mark_changed" in calls
    assert "mark_clean" in calls
    assert "emit" in calls


def test_mutating_pages_emit_data_changed_after_successful_write() -> None:
    sources = {
        "dialog": (ROOT / "pages" / "dialog_page.py").read_text(
            encoding="utf-8"
        ),
        "tracking": (ROOT / "pages" / "tracking_page.py").read_text(
            encoding="utf-8"
        ),
        "data": (ROOT / "pages" / "data_page.py").read_text(
            encoding="utf-8"
        ),
    }

    assert "data_changed = Signal()" in sources["dialog"]
    assert "self.data_changed.emit()" in sources["dialog"]

    assert "data_changed = Signal()" in sources["tracking"]
    assert "self.data_changed.emit()" in sources["tracking"]

    assert "data_changed = Signal()" in sources["data"]
    assert sources["data"].count("self.data_changed.emit()") >= 6


def test_script_full_refresh_reloads_episode_filters_not_rows_only() -> None:
    source = (ROOT / "pages" / "script_page.py").read_text(
        encoding="utf-8"
    )
    refresh = _method(
        ROOT / "pages" / "script_page.py",
        "ScriptPage",
        "refresh_from_database",
    )

    calls = _called_attributes(refresh)
    assert "reload" in calls
    assert "refresh_rows" not in calls
    assert "newly added episodes" in source
