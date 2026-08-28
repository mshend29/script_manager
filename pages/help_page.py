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

    def show_getting_started(self) -> None:
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
