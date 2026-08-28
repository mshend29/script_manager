from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
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
KEYBOARD_SHORTCUTS_FILE = HELP_ROOT / "keyboard_shortcuts.html"
REPORT_PROBLEM_FILE = HELP_ROOT / "report_problem.html"


class HelpPage(PageShell):
    action_requested = Signal(str)
    release_requested = Signal(str)
    issue_requested = Signal(str)

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

        self.keyboard_shortcuts_button = QPushButton("Keyboard Shortcuts")
        self.keyboard_shortcuts_button.setProperty("secondary", True)
        self.keyboard_shortcuts_button.clicked.connect(
            self.show_keyboard_shortcuts
        )
        context.add_widget(self.keyboard_shortcuts_button)

        context.add_section_title("APPLICATION")
        self.check_updates_button = QPushButton("Check for Updates")
        self.check_updates_button.setProperty("secondary", True)
        self.check_updates_button.clicked.connect(
            lambda: self.action_requested.emit("help.check_updates")
        )
        context.add_widget(self.check_updates_button)

        context.add_section_title("SUPPORT")
        self.report_problem_button = QPushButton("Report a Problem")
        self.report_problem_button.setProperty("secondary", True)
        self.report_problem_button.clicked.connect(
            lambda: self.action_requested.emit("help.report_problem")
        )
        context.add_widget(self.report_problem_button)
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

        self.open_release_button = QPushButton("Open Release Page")
        self.open_release_button.setProperty("primary", True)
        self.open_release_button.hide()
        self.open_release_button.clicked.connect(
            self._open_release_clicked
        )
        root.addWidget(self.open_release_button)

        self.open_issue_button = QPushButton("Open GitHub Issue")
        self.open_issue_button.setProperty("primary", True)
        self.open_issue_button.hide()
        self.open_issue_button.clicked.connect(
            self._open_issue_clicked
        )
        root.addWidget(self.open_issue_button)

        self.copy_report_button = QPushButton("Copy Report Template")
        self.copy_report_button.setProperty("secondary", True)
        self.copy_report_button.hide()
        self.copy_report_button.clicked.connect(
            self._copy_report_clicked
        )
        root.addWidget(self.copy_report_button)

        self._release_url = ""
        self._issue_url = ""
        self._problem_report_text = ""

        super().__init__(context, workspace, parent)
        self.show_getting_started()

    def _set_active_button(self, active: QPushButton) -> None:
        for button in (
            self.getting_started_button,
            self.user_guide_button,
            self.keyboard_shortcuts_button,
            self.check_updates_button,
            self.report_problem_button,
        ):
            is_active = button is active
            button.setProperty("primary", is_active)
            button.setProperty("secondary", not is_active)
            button.style().unpolish(button)
            button.style().polish(button)

    def show_getting_started(self) -> None:
        self._hide_release_button()
        self._hide_problem_buttons()
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
        self._hide_release_button()
        self._hide_problem_buttons()
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

    def show_keyboard_shortcuts(self) -> None:
        self._hide_release_button()
        self._hide_problem_buttons()
        self._set_active_button(self.keyboard_shortcuts_button)
        self.title.setText("Keyboard Shortcuts")
        self.subtitle.setText(
            "Daftar shortcut keyboard yang aktif di Script Manager."
        )

        try:
            html = KEYBOARD_SHORTCUTS_FILE.read_text(encoding="utf-8")
        except OSError as exc:
            self.browser.setPlainText(
                "Keyboard Shortcuts tidak dapat dimuat.\n\n"
                f"{exc}"
            )
            return

        self.browser.setHtml(html)
        self.browser.verticalScrollBar().setValue(0)

    def show_update_checking(self, current_version: str) -> None:
        self._hide_problem_buttons()
        self._set_active_button(self.check_updates_button)
        self._hide_release_button()
        self.check_updates_button.setEnabled(False)
        self.title.setText("Check for Updates")
        self.subtitle.setText(
            f"Current version: {current_version}"
        )
        self.browser.setHtml(
            "<h2>Checking for updates…</h2>"
            "<p>Script Manager sedang memeriksa GitHub Releases. "
            "Pemeriksaan berjalan di background sehingga UI tetap responsif.</p>"
        )

    def show_update_result(self, result) -> None:
        self._hide_problem_buttons()
        self._set_active_button(self.check_updates_button)
        self.check_updates_button.setEnabled(True)

        status = str(getattr(result, "status", ""))
        current = escape(str(getattr(result, "current_version", "") or ""))
        latest = escape(str(getattr(result, "latest_version", "") or ""))
        name = escape(str(getattr(result, "release_name", "") or ""))
        published = escape(str(getattr(result, "published_at", "") or ""))
        release_url = str(getattr(result, "release_url", "") or "").strip()

        self.title.setText("Check for Updates")
        self.subtitle.setText(f"Current version: {current}")

        if status.endswith("UPDATE_AVAILABLE"):
            heading = "Update available"
            body = (
                f"<p>Versi terbaru: <b>{latest}</b></p>"
                f"<p>{name}</p>"
                "<p>Gunakan tombol <b>Open Release Page</b> untuk "
                "membuka halaman rilis dan mengunduh update secara manual.</p>"
            )
            self._show_release_button(release_url)
        elif status.endswith("UP_TO_DATE"):
            heading = "You are up to date"
            body = (
                f"<p>Versi terbaru yang dipublikasikan adalah "
                f"<b>{latest}</b>.</p>"
            )
            self._show_release_button(release_url)
        else:
            heading = "No release published yet"
            body = (
                "<p>Repository belum memiliki GitHub Release. "
                "Ini bukan error; update checker akan mulai membandingkan "
                "versi setelah release pertama dipublikasikan.</p>"
            )
            self._hide_release_button()

        if published:
            body += f"<p>Published: {published}</p>"

        self.browser.setHtml(f"<h2>{heading}</h2>{body}")

    def show_update_error(self, message: str, current_version: str) -> None:
        self._hide_problem_buttons()
        self._set_active_button(self.check_updates_button)
        self.check_updates_button.setEnabled(True)
        self._hide_release_button()
        self.title.setText("Check for Updates")
        self.subtitle.setText(
            f"Current version: {escape(str(current_version))}"
        )
        self.browser.setHtml(
            "<h2>Update check failed</h2>"
            f"<p>{escape(str(message))}</p>"
            "<p>Project dan data lokal tidak diubah.</p>"
        )

    def show_report_problem(self, report) -> None:
        self._hide_release_button()
        self._set_active_button(self.report_problem_button)
        self.title.setText("Report a Problem")
        self.subtitle.setText(
            "Buat laporan bug dengan environment info yang privacy-safe."
        )

        environment = dict(getattr(report, "environment", {}) or {})
        rows = "".join(
            "<tr>"
            f"<td>{escape(str(key))}</td>"
            f"<td>{escape(str(value))}</td>"
            "</tr>"
            for key, value in environment.items()
        )

        try:
            html = REPORT_PROBLEM_FILE.read_text(encoding="utf-8")
        except OSError as exc:
            self.browser.setPlainText(
                "Report a Problem tidak dapat dimuat.\n\n"
                f"{exc}"
            )
            self._hide_problem_buttons()
            return

        self.browser.setHtml(
            html.replace("{{ENVIRONMENT_ROWS}}", rows)
        )
        self.browser.verticalScrollBar().setValue(0)

        self._issue_url = str(
            getattr(report, "issue_url", "") or ""
        ).strip()
        self._problem_report_text = str(
            getattr(report, "body", "") or ""
        )

        self.open_issue_button.setVisible(bool(self._issue_url))
        self.copy_report_button.setVisible(
            bool(self._problem_report_text)
        )
        self.copy_report_button.setText("Copy Report Template")

    def _hide_problem_buttons(self) -> None:
        self._issue_url = ""
        self._problem_report_text = ""
        if hasattr(self, "open_issue_button"):
            self.open_issue_button.hide()
        if hasattr(self, "copy_report_button"):
            self.copy_report_button.hide()

    def _open_issue_clicked(self) -> None:
        if self._issue_url:
            self.issue_requested.emit(self._issue_url)

    def _copy_report_clicked(self) -> None:
        if not self._problem_report_text:
            return

        QApplication.clipboard().setText(
            self._problem_report_text
        )
        self.copy_report_button.setText("Copied")

    def _show_release_button(self, url: str) -> None:
        self._release_url = str(url or "").strip()
        self.open_release_button.setVisible(bool(self._release_url))

    def _hide_release_button(self) -> None:
        self._release_url = ""
        if hasattr(self, "open_release_button"):
            self.open_release_button.hide()

    def _open_release_clicked(self) -> None:
        if self._release_url:
            self.release_requested.emit(self._release_url)
