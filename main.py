import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from app.main_window import MainWindow
from app.light_runtime import (
    apply_light_theme,
    install_light_window_chrome,
)
from app.theme import APP_STYLESHEET
from core.application_logging import configure_application_logging
from core.resource_paths import application_icon_path
from core.version import APP_VERSION


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


def main():
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

    splash = None
    if not smoke_test:
        splash = create_splash_screen()
        splash.show()
        app.processEvents()

    window = MainWindow()

    if smoke_test:
        # Packaging CI uses this path to prove that the frozen executable can
        # construct the real production MainWindow and all enhanced pages.
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

    # No startup Recent Projects dialog. When no project is open, the PROJECT
    # workspace itself is the Recent-project home screen.
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
