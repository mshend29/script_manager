import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox, QSplashScreen

from app.application_window import ApplicationWindow
from app.google_drive_readiness_controller import GoogleDriveReadinessController
from app.main_window import MainWindow
from app.light_runtime import (
    apply_light_theme,
    install_light_window_chrome,
)
from app.theme import APP_STYLESHEET
from core.application_logging import (
    configure_application_logging,
    record_fatal_startup_error,
)
from core.resource_paths import application_icon_path
from core.version import APP_VERSION
from services.problem_report_service import ProblemReportService


def create_splash_screen() -> QSplashScreen:
    pixmap = QPixmap(720, 420)
    pixmap.fill(QColor("#F6F7F9"))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#4F46E5"))
    painter.drawRoundedRect(292, 94, 136, 136, 30, 30)

    painter.setPen(QColor("#FFFFFF"))
    mark_font = QFont("Segoe UI", 34, QFont.Weight.Bold)
    painter.setFont(mark_font)
    painter.drawText(
        292,
        94,
        136,
        136,
        Qt.AlignmentFlag.AlignCenter,
        "SM",
    )

    painter.setPen(QColor("#181B20"))
    title_font = QFont("Segoe UI", 23, QFont.Weight.Bold)
    painter.setFont(title_font)
    painter.drawText(
        0,
        250,
        720,
        44,
        Qt.AlignmentFlag.AlignCenter,
        "Script Manager",
    )

    painter.setPen(QColor("#717784"))
    subtitle_font = QFont("Segoe UI", 10)
    painter.setFont(subtitle_font)
    painter.drawText(
        0,
        302,
        720,
        28,
        Qt.AlignmentFlag.AlignCenter,
        "Loading production workspace…",
    )
    painter.end()

    splash = QSplashScreen(pixmap)
    splash.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    return splash


def _show_startup_failure(log_path: Path) -> None:
    message = (
        "Script Manager gagal memulai.\n\n"
        "Detail teknis telah disimpan di:\n"
        f"{log_path}\n\n"
        "Jika masalah berulang, lampirkan file log tersebut saat melaporkan masalah."
    )

    app = QApplication.instance()
    if app is not None:
        QMessageBox.critical(None, "Script Manager", message)
        return

    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, "Script Manager", 0x10)
            return
        except Exception:
            pass

    sys.stderr.write(message + "\n")


def _run_application() -> int:
    configure_application_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Script Manager")
    app.setApplicationVersion(APP_VERSION)
    apply_light_theme(app)
    install_light_window_chrome(app)

    icon_path = application_icon_path()
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    app.setStyleSheet(APP_STYLESHEET)

    arguments = [str(value) for value in sys.argv[1:]]
    smoke_test = "--smoke-test" in arguments
    diagnostics_smoke_test = "--diagnostics-smoke-test" in arguments

    if diagnostics_smoke_test:
        environment = ProblemReportService().build().environment
        if environment.get("Runtime") != "Packaged (PyInstaller)":
            return 20
        if environment.get("PySide6") in {"", "unknown", "not installed"}:
            return 21
        if "Script Manager" not in environment.get("Diagnostic log", ""):
            return 22
        return 0

    splash = None
    if not smoke_test:
        splash = create_splash_screen()
        splash.show()
        app.processEvents()

    # MainWindow remains the stable production workspace base. Phase 11 adds
    # only New Project orchestration in ApplicationWindow.
    _workspace_base = MainWindow
    window = ApplicationWindow()

    if smoke_test:
        # Packaging CI uses this path to prove that the frozen executable can
        # construct the real production MainWindow and all enhanced pages.
        # First-run prerequisite dialogs are intentionally not invoked here.
        app.processEvents()
        window.close()
        app.processEvents()
        return 0

    project_args = [
        value
        for value in arguments
        if not value.startswith("--")
    ]
    if project_args:
        candidate = Path(project_args[0]).expanduser()
        if candidate.exists():
            window.open_project_path(candidate)

    # Maximized while preserving native title bar/minimize/maximize/close.
    window.showMaximized()
    app.processEvents()

    if splash is not None:
        splash.finish(window)

    # Phase 12 keeps Google Drive readiness out of the core workspace shell.
    # The Help action is always available. An incomplete setup receives one
    # first-run notice per application version, after the main window is shown.
    drive_readiness = GoogleDriveReadinessController(window)
    drive_readiness.show_first_run_if_needed()

    # No startup Recent Projects dialog. When no project is open, the PROJECT
    # workspace itself is the Recent-project home screen.
    return app.exec()


def main() -> int:
    try:
        return _run_application()
    except Exception as exc:
        log_path = record_fatal_startup_error(exc)
        _show_startup_failure(log_path)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
