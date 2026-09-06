from __future__ import annotations

import re
from pathlib import Path

from core.project import PROJECT_FILE_EXTENSION


_WINDOWS_INVALID_FILENAME_CHARS = frozenset('<>:"/\\|?*')
_WHITESPACE = re.compile(r"\s+")


def _strip_project_extension(value: str) -> str:
    text = str(value or "").strip()
    extension = PROJECT_FILE_EXTENSION.casefold()
    while text.casefold().endswith(extension):
        text = text[: -len(PROJECT_FILE_EXTENSION)].rstrip()
    return text


def sanitize_project_filename_component(value: str) -> str:
    """Return a Windows-safe filename component without mutating metadata."""
    text = _strip_project_extension(value)
    text = _WHITESPACE.sub(" ", text)
    text = "".join(
        "_" if char in _WINDOWS_INVALID_FILENAME_CHARS or ord(char) < 32 else char
        for char in text
    )
    return text.strip(" .")


def format_new_project_filename(project_code: str, project_name: str) -> str:
    """Official filename rule for newly created Script Manager projects."""
    code = sanitize_project_filename_component(project_code)
    name = sanitize_project_filename_component(project_name)

    if not code:
        code = name or "Project"
    if not name:
        name = code or "Project"

    return f"{code} - {name}{PROJECT_FILE_EXTENSION}"


def new_project_destination(
    parent_folder: str | Path,
    project_code: str,
    project_name: str,
) -> Path:
    parent = Path(parent_folder).expanduser()
    return parent / format_new_project_filename(project_code, project_name)
