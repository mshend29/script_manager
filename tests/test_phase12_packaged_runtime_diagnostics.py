from __future__ import annotations

from core.runtime_diagnostics import (
    diagnostic_log_location_hint,
    runtime_mode_label,
)


def test_runtime_mode_distinguishes_source_and_frozen() -> None:
    assert runtime_mode_label(frozen=False) == "Source (Python)"
    assert runtime_mode_label(frozen=True) == "Packaged (PyInstaller)"


def test_windows_diagnostic_hint_is_stable_and_privacy_safe() -> None:
    hint = diagnostic_log_location_hint(platform_name="win32")

    assert hint == r"%APPDATA%\Script Manager\Logs\script_manager.log"
    assert "Users\\" not in hint


def test_macos_diagnostic_hint_is_cross_platform_ready() -> None:
    assert diagnostic_log_location_hint(platform_name="darwin") == (
        "~/Library/Application Support/Script Manager/Logs/script_manager.log"
    )
