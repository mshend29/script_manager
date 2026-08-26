import sys
from PySide6.QtWidgets import QApplication
from app.alias_main_window import AliasMainWindow
from app.theme import APP_STYLESHEET


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Script Manager")
    app.setStyleSheet(APP_STYLESHEET)
    window = AliasMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
