from __future__ import annotations

import ast
import importlib.util
import os
from pathlib import Path

import pytest


def test_script_model_is_not_parented_to_uninitialized_script_page():
    source_path = Path("pages/script_page.py")
    tree = ast.parse(source_path.read_text(encoding="utf-8"))

    script_page = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ScriptPage"
    )
    init_method = next(
        node
        for node in script_page.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )

    model_calls = [
        node
        for node in ast.walk(init_method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ScriptTableModel"
    ]

    assert len(model_calls) == 1
    call = model_calls[0]
    assert len(call.args) == 1
    parent = call.args[0]
    assert isinstance(parent, ast.Attribute)
    assert isinstance(parent.value, ast.Name)
    assert parent.value.id == "self"
    assert parent.attr == "table"


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None,
    reason="PySide6 is not installed in the lightweight CI environment",
)
def test_script_page_constructs_without_shiboken_parent_error():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from pages.script_page import ScriptPage

    app = QApplication.instance() or QApplication([])
    page = ScriptPage()

    assert page.table.model() is page.table_model
    assert page.table_model.parent() is page.table

    page.close()
    app.processEvents()
