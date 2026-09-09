from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version


def runtime_mode_label(*, frozen: bool | None = None) -> str:
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
    return "Packaged (PyInstaller)" if is_frozen else "Source (Python)"


def diagnostic_log_location_hint(*, platform_name: str | None = None) -> str:
    platform_value = str(platform_name or sys.platform)
    if platform_value == "win32":
        return r"%APPDATA%\Script Manager\Logs\script_manager.log"
    if platform_value == "darwin":
        return "~/Library/Application Support/Script Manager/Logs/script_manager.log"
    return "~/.local/share/Script Manager/Logs/script_manager.log"


def package_version(package_name: str) -> str:
    name = str(package_name or "").strip()
    if not name:
        return "unknown"

    try:
        return version(name)
    except PackageNotFoundError:
        if name.casefold() == "pyside6":
            try:
                import PySide6

                value = str(getattr(PySide6, "__version__", "") or "").strip()
                if value:
                    return value
            except Exception:
                pass
        return "not installed"
