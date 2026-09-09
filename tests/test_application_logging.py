from __future__ import annotations

import logging
import sys
from pathlib import Path

from core import application_logging


def _close_handlers() -> None:
    logger = logging.getLogger(application_logging.LOGGER_NAME)
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)


def test_application_logging_writes_privacy_safe_startup_metadata(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    _close_handlers()

    logger = application_logging.configure_application_logging()
    for handler in logger.handlers:
        handler.flush()

    log_file = application_logging.application_log_file()
    assert log_file.is_file()

    content = log_file.read_text(encoding="utf-8")
    assert "Application startup" in content
    assert "Script Manager" in content
    assert "python=" in content
    assert "os=" in content
    assert "frozen=" in content

    # Startup logging deliberately does not dump argv, project paths, source
    # content, or other operator data.
    assert "sys.argv" not in content
    _close_handlers()


def test_unhandled_exception_hook_records_traceback_locally(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    _close_handlers()
    logger = application_logging.configure_application_logging()

    try:
        raise RuntimeError("synthetic crash")
    except RuntimeError:
        exc_type, exc_value, traceback = sys.exc_info()

    application_logging._unhandled_exception_hook(
        exc_type,
        exc_value,
        traceback,
    )
    for handler in logger.handlers:
        handler.flush()

    content = application_logging.application_log_file().read_text(
        encoding="utf-8"
    )
    assert "Unhandled exception" in content
    assert "RuntimeError: synthetic crash" in content
    _close_handlers()


def test_fatal_startup_error_returns_local_diagnostic_file(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    _close_handlers()
    application_logging.configure_application_logging()

    exc = RuntimeError("startup exploded")
    path = application_logging.record_fatal_startup_error(exc)

    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    assert "Fatal startup exception" in content
    assert "RuntimeError: startup exploded" in content
    _close_handlers()


def test_main_configures_logging_before_qt_event_loop() -> None:
    source = Path("main.py").read_text(encoding="utf-8")

    assert "configure_application_logging()" in source
    assert source.index("configure_application_logging()") < source.index(
        "QApplication(sys.argv)"
    )
    assert "record_fatal_startup_error" in source
    assert "_show_startup_failure" in source
