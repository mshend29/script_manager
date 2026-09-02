import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.theme import APP_STYLESHEET
from core.version import APP_VERSION


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Script Manager")
    app.setApplicationVersion(APP_VERSION)
    app.setStyleSheet(APP_STYLESHEET)
    window = MainWindow()

    if len(sys.argv) > 1:
        candidate = Path(sys.argv[1]).expanduser()
        if candidate.exists():
            window.open_project_path(candidate)

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
