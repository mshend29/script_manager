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

    arguments = [str(value) for value in sys.argv[1:]]
    if "--smoke-test" in arguments:
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

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
