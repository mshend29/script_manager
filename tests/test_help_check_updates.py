from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_application_version_is_centralized_and_exposed_to_qt():
    version = (ROOT / "core" / "version.py").read_text(encoding="utf-8")
    main = (ROOT / "main.py").read_text(encoding="utf-8")

    assert 'APP_VERSION = "0.1.0"' in version
    assert "GITHUB_LATEST_RELEASE_API" in version
    assert "app.setApplicationVersion(APP_VERSION)" in main


def test_check_updates_is_wired_to_help_and_background_worker():
    header = (ROOT / "widgets" / "page_header.py").read_text(encoding="utf-8")
    page = (ROOT / "pages" / "help_page.py").read_text(encoding="utf-8")
    main = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")
    worker = (
        ROOT / "app" / "update_check_worker.py"
    ).read_text(encoding="utf-8")

    assert 'HeaderAction("help.check_updates", "Check for Updates")' in header
    assert 'QPushButton("Check for Updates")' in page
    assert '"help.check_updates": self.check_for_updates' in main
    assert "def check_for_updates" in main
    assert "QThread(self)" in main
    assert "UpdateCheckWorker()" in main
    assert "worker.moveToThread(thread)" in main
    assert "class UpdateCheckWorker" in worker


def test_help_page_has_all_update_check_states():
    page = (ROOT / "pages" / "help_page.py").read_text(encoding="utf-8")

    for expected in (
        "Checking for updates",
        "Update available",
        "You are up to date",
        "No release published yet",
        "Update check failed",
        "Open Release Page",
    ):
        assert expected in page


def test_check_updates_opens_release_page_only_by_user_action():
    page = (ROOT / "pages" / "help_page.py").read_text(encoding="utf-8")
    main = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")

    assert "release_requested = Signal(str)" in page
    assert "self.release_requested.emit(self._release_url)" in page
    assert "help_page.release_requested.connect(self.open_update_release)" in main
    assert "QDesktopServices.openUrl(QUrl(target))" in main
