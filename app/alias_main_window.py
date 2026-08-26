from __future__ import annotations

from app.main_window import MainWindow
from pages.alias_data_page import AliasAwareDataPage


class AliasMainWindow(MainWindow):
    """MainWindow variant that installs the alias-aware DATA workspace."""

    def __init__(self):
        super().__init__()

        old_page = self.pages["DATA"]
        index = self.page_stack.indexOf(old_page)
        data_page = AliasAwareDataPage()

        self.page_stack.insertWidget(index, data_page)
        self.page_stack.removeWidget(old_page)
        old_page.deleteLater()
        self.pages["DATA"] = data_page

        data_page.tracking_navigation_requested.connect(self.open_tracking_scope)
