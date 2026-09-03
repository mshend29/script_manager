from __future__ import annotations

import sys

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QPalette

from app.theme import COLORS


def _force_light_title_bar(widget) -> None:
    if sys.platform != "win32":
        return

    try:
        import ctypes

        hwnd = int(widget.winId())
        value = ctypes.c_int(0)
        size = ctypes.sizeof(value)
        dwmapi = ctypes.windll.dwmapi
        for attribute in (20, 19):
            result = dwmapi.DwmSetWindowAttribute(
                hwnd,
                attribute,
                ctypes.byref(value),
                size,
            )
            if result == 0:
                break
    except Exception:
        pass


class LightWindowChromeFilter(QObject):
    def eventFilter(self, watched, event) -> bool:
        if (
            event.type()
            in {
                QEvent.Type.Show,
                QEvent.Type.WinIdChange,
            }
            and hasattr(watched, "isWindow")
            and watched.isWindow()
        ):
            _force_light_title_bar(watched)
        return False


def install_light_window_chrome(app) -> None:
    filter_object = LightWindowChromeFilter(app)
    app.installEventFilter(filter_object)
    app._script_manager_light_chrome_filter = filter_object


def apply_light_theme(app) -> None:
    """Force Script Manager to stay light even when Windows uses dark mode."""
    app.setStyle("Fusion")

    try:
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except (AttributeError, RuntimeError):
        pass

    palette = QPalette()
    palette.setColor(
        QPalette.ColorRole.Window,
        QColor(COLORS["app_background"]),
    )
    palette.setColor(
        QPalette.ColorRole.WindowText,
        QColor(COLORS["text_primary"]),
    )
    palette.setColor(
        QPalette.ColorRole.Base,
        QColor(COLORS["surface"]),
    )
    palette.setColor(
        QPalette.ColorRole.AlternateBase,
        QColor(COLORS["surface_subtle"]),
    )
    palette.setColor(
        QPalette.ColorRole.ToolTipBase,
        QColor(COLORS["surface"]),
    )
    palette.setColor(
        QPalette.ColorRole.ToolTipText,
        QColor(COLORS["text_primary"]),
    )
    palette.setColor(
        QPalette.ColorRole.Text,
        QColor(COLORS["text_primary"]),
    )
    palette.setColor(
        QPalette.ColorRole.Button,
        QColor(COLORS["surface"]),
    )
    palette.setColor(
        QPalette.ColorRole.ButtonText,
        QColor(COLORS["text_primary"]),
    )
    palette.setColor(
        QPalette.ColorRole.BrightText,
        QColor(COLORS["error"]),
    )
    palette.setColor(
        QPalette.ColorRole.Highlight,
        QColor(COLORS["accent_soft"]),
    )
    palette.setColor(
        QPalette.ColorRole.HighlightedText,
        QColor(COLORS["text_primary"]),
    )
    palette.setColor(
        QPalette.ColorRole.Link,
        QColor(COLORS["accent"]),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        QColor(COLORS["text_muted"]),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor(COLORS["text_muted"]),
    )
    app.setPalette(palette)
