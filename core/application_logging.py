from __future__ import annotations

import logging
import platform
import sys
import tempfile
import threading
import traceback as traceback_module
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

from core.app_paths import app_data_root
from core.version import APP_NAME, APP_VERSION


LOGGER_NAME = "script_manager"
LOG_FILE_NAME = "script_manager.log"
MAX_LOG_BYTES = 2 * 1024 * 1024
BACKUP_LOG_COUNT = 3
FALLBACK_FATAL_LOG_FILE_NAME = "ScriptManager-startup-error.log"


def application_logs_dir() -> Path:
    path = app_data_root() / "Logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def application_log_file() -> Path:
    return application_logs_dir() / LOG_FILE_NAME


def configure_application_logging() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    log_path = application_log_file()
    existing = [
        handler
        for handler in logger.handlers
        if isinstance(handler, RotatingFileHandler)
        and Path(getattr(handler, "baseFilename", "")).resolve(
            strict=False
        ) == log_path.resolve(strict=False)
    ]
    if not existing:
        handler = RotatingFileHandler(
            log_path,
            maxBytes=MAX_LOG_BYTES,
            backupCount=BACKUP_LOG_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            )
        )
        logger.addHandler(handler)

    logger.info(
        "Application startup | app=%s %s | python=%s | os=%s %s | frozen=%s",
        APP_NAME,
        APP_VERSION,
        platform.python_version(),
        platform.system(),
        platform.release(),
        bool(getattr(sys, "frozen", False)),
    )

    sys.excepthook = _unhandled_exception_hook

    if hasattr(threading, "excepthook"):
        threading.excepthook = _thread_exception_hook

    return logger


def record_fatal_startup_error(exc: BaseException) -> Path:
    """Persist a fatal startup failure and return a local diagnostic path.

    The normal application log is preferred. If the configured per-user log
    location is unavailable, a temp-directory fallback is written so a
    windowed packaged build never fails without a diagnostic artifact.
    """

    logger = logging.getLogger(LOGGER_NAME)
    try:
        logger.critical(
            "Fatal startup exception",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        for handler in logger.handlers:
            try:
                handler.flush()
            except Exception:
                pass

        log_path = application_log_file()
        if log_path.is_file():
            return log_path
    except Exception:
        pass

    fallback = Path(tempfile.gettempdir()) / FALLBACK_FATAL_LOG_FILE_NAME
    trace_text = "".join(
        traceback_module.format_exception(type(exc), exc, exc.__traceback__)
    )
    fallback.write_text(
        (
            f"{datetime.now().isoformat(timespec='seconds')} | "
            f"{APP_NAME} {APP_VERSION} fatal startup exception\n"
            f"{trace_text}"
        ),
        encoding="utf-8",
    )
    return fallback


def _unhandled_exception_hook(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> None:
    logger = logging.getLogger(LOGGER_NAME)
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.critical(
        "Unhandled exception",
        exc_info=(exc_type, exc_value, exc_traceback),
    )


def _thread_exception_hook(args: threading.ExceptHookArgs) -> None:
    logger = logging.getLogger(LOGGER_NAME)
    logger.critical(
        "Unhandled thread exception | thread=%s",
        getattr(args.thread, "name", "unknown"),
        exc_info=(
            args.exc_type,
            args.exc_value,
            args.exc_traceback,
        ),
    )
