from __future__ import annotations

import importlib.util
import os

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PYSIDE_AVAILABLE = importlib.util.find_spec("PySide6") is not None

pytestmark = pytest.mark.skipif(
    not PYSIDE_AVAILABLE,
    reason="PySide6 is only installed in the Qt runtime CI job.",
)

if PYSIDE_AVAILABLE:
    from PySide6.QtCore import QUrl
    from PySide6.QtWidgets import QApplication, QFrame

    from pages.help_page import HELP_ARTICLES, HelpPage


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


def _visible_article_titles(page: HelpPage) -> set[str]:
    visible: set[str] = set()
    tree = page.navigation_tree
    for category_index in range(tree.topLevelItemCount()):
        category = tree.topLevelItem(category_index)
        for child_index in range(category.childCount()):
            child = category.child(child_index)
            if not child.isHidden():
                visible.add(child.text(0))
    return visible


def test_help_documentation_layout_is_visible_and_accessible(qapp):
    page = HelpPage()
    page.resize(1100, 700)
    page.show()
    qapp.processEvents()

    sidebar = page.findChild(QFrame, "HelpSidebar")
    assert sidebar is not None
    assert sidebar.isVisible()
    assert sidebar.width() >= 270

    assert page.search_edit.isVisible()
    assert page.search_edit.placeholderText() == "Cari panduan..."
    assert page.search_edit.accessibleName() == "Cari panduan Script Manager"
    assert page.navigation_tree.isVisible()
    assert page.navigation_tree.accessibleName() == "Daftar topik panduan"
    assert page.browser.isVisible()
    assert page.subtitle.wordWrap()

    categories = {
        page.navigation_tree.topLevelItem(index).text(0)
        for index in range(page.navigation_tree.topLevelItemCount())
    }
    assert {
        "Mulai",
        "Proyek",
        "Sumber Naskah",
        "Area Kerja",
        "Folder & Tautan",
        "Pemeliharaan",
        "Panduan Praktis",
        "Referensi",
    }.issubset(categories)
    assert len(HELP_ARTICLES) >= 20

    page.close()
    qapp.processEvents()


def test_help_search_filters_by_task_keywords(qapp):
    page = HelpPage()
    page.show()
    qapp.processEvents()

    page.search_edit.setText("google drive")
    qapp.processEvents()
    visible = _visible_article_titles(page)
    assert "Filesystem vs Google Drive" in visible
    assert "NASKAH" not in visible

    page.search_edit.setText("source revised")
    qapp.processEvents()
    visible = _visible_article_titles(page)
    assert "Revisi Sumber & Sumber Direvisi" in visible

    page.search_edit.clear()
    qapp.processEvents()
    assert len(_visible_article_titles(page)) == len(HELP_ARTICLES)

    page.close()
    qapp.processEvents()


def test_help_article_navigation_updates_context_and_content(qapp):
    page = HelpPage()
    page.show()
    qapp.processEvents()

    page.show_article("source-sync")
    qapp.processEvents()
    assert page._current_article_key == "source-sync"
    assert page.title.text() == "Sinkronkan Sumber"
    assert "Sumber Naskah" in page.breadcrumb.text()
    assert "Sinkronkan Sumber" in page.browser.toPlainText()
    assert page.previous_article_button.isEnabled()
    assert page.next_article_button.isEnabled()

    page._handle_browser_link(QUrl("help://troubleshooting"))
    qapp.processEvents()
    assert page._current_article_key == "troubleshooting"
    assert page.title.text() == "Troubleshooting"
    assert "Panduan Praktis" in page.breadcrumb.text()
    assert "Troubleshooting" in page.browser.toPlainText()

    page.close()
    qapp.processEvents()


def test_help_quick_access_preserves_existing_help_surfaces(qapp):
    page = HelpPage()
    page.show()
    qapp.processEvents()

    page.show_getting_started()
    assert page._current_article_key == "getting-started"
    assert page.title.text() == "Mulai Cepat"

    page.show_user_guide()
    assert page._current_article_key == "guide-overview"
    assert page.title.text() == "Cara Membaca Panduan"

    page.show_keyboard_shortcuts()
    assert page._current_article_key == "keyboard-shortcuts"
    assert page.title.text() == "Pintasan Keyboard"

    assert page.check_updates_button.isVisible()
    assert page.report_problem_button.isVisible()
    assert page.about_button.isVisible()

    page.close()
    qapp.processEvents()
