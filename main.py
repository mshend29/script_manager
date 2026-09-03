import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.theme import APP_STYLESHEET
from core.application_logging import configure_application_logging
from core.resource_paths import application_icon_path
from core.version import APP_VERSION


def main():
    configure_application_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Script Manager")
    app.setApplicationVersion(APP_VERSION)
    icon_path = application_icon_path()
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
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
