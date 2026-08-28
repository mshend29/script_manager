from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from widgets.context_panel import ContextPanel
from widgets.page_shell import PageShell


HELP_ROOT = Path(__file__).resolve().parents[1] / "resources" / "help"
GETTING_STARTED_FILE = HELP_ROOT / "getting_started.html"
USER_GUIDE_FILE = HELP_ROOT / "user_guide.html"


class HelpPage(PageShell):
    def __init__(self, parent: QWidget | None = None):
        context = ContextPanel("HELP")

        context.add_section_title("GUIDE")

        self.getting_started_button = QPushButton("Getting Started")
        self.getting_started_button.setProperty("primary", True)
        self.getting_started_button.clicked.connect(
            self.show_getting_started
        )
        context.add_widget(self.getting_started_button)

        self.user_guide_button = QPushButton("User Guide")
        self.user_guide_button.setProperty("secondary", True)
        self.user_guide_button.clicked.connect(
            self.show_user_guide
        )
        context.add_widget(self.user_guide_button)
        context.add_stretch()

        workspace = QWidget()
        root = QVBoxLayout(workspace)
        root.setContentsMargins(28, 22, 28, 24)
        root.setSpacing(10)

        self.title = QLabel("Getting Started")
        self.title.setObjectName("PageTitle")
        root.addWidget(self.title)

        self.subtitle = QLabel(
            "Panduan offline untuk memulai workflow Script Manager."
        )
        self.subtitle.setObjectName("PageSubtitle")
        self.subtitle.setWordWrap(True)
        root.addWidget(self.subtitle)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setOpenLinks(False)
        root.addWidget(self.browser, 1)

        super().__init__(context, workspace, parent)
        self.show_getting_started()

    def _set_active_button(self, active: QPushButton) -> None:
        for button in (
            self.getting_started_button,
            self.user_guide_button,
        ):
            is_active = button is active
            button.setProperty("primary", is_active)
            button.setProperty("secondary", not is_active)
            button.style().unpolish(button)
            button.style().polish(button)

    def show_getting_started(self) -> None:
        self._set_active_button(self.getting_started_button)
        self.title.setText("Getting Started")
        self.subtitle.setText(
            "Panduan offline untuk memulai workflow Script Manager."
        )

        try:
            html = GETTING_STARTED_FILE.read_text(encoding="utf-8")
        except OSError as exc:
            self.browser.setPlainText(
                "Getting Started tidak dapat dimuat.\n\n"
                f"{exc}"
            )
            return

        self.browser.setHtml(html)
        self.browser.verticalScrollBar().setValue(0)

    def show_user_guide(self) -> None:
        self._set_active_button(self.user_guide_button)
        self.title.setText("User Guide")
        self.subtitle.setText(
            "Panduan operasional lengkap per area Script Manager."
        )

        try:
            html = USER_GUIDE_FILE.read_text(encoding="utf-8")
        except OSError as exc:
            self.browser.setPlainText(
                "User Guide tidak dapat dimuat.\n\n"
                f"{exc}"
            )
            return

        self.browser.setHtml(html)
        self.browser.verticalScrollBar().setValue(0)
