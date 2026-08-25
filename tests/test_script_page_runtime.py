from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from pages.script_page import ScriptPage


def test_script_page_constructs_without_shiboken_parent_error():
    app = QApplication.instance() or QApplication([])
    page = ScriptPage()

    assert page.table.model() is page.table_model
    assert page.table_model.parent() is page.table

    page.close()
    app.processEvents()
