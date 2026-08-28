import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app import main_window as main_window_module
from app.theme import APP_STYLESHEET
from core.version import APP_VERSION
from pages.data_alias_page import AliasDataPage
from pages.tracking_compact_page import CompactTrackingPage

# Keep MainWindow's existing routing/actions intact while replacing only the
# concrete page implementations with the enhanced variants.
main_window_module.DataPage = AliasDataPage
main_window_module.TrackingPage = CompactTrackingPage
MainWindow = main_window_module.MainWindow


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
