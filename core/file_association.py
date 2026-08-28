from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.project import PROJECT_FILE_EXTENSION


WINDOWS_PROG_ID = "ScriptManager.Project"
WINDOWS_FILE_TYPE = "Script Management Project"


@dataclass(frozen=True)
class WindowsFileAssociationSpec:
    extension: str
    prog_id: str
    file_type: str
    open_command: str


def windows_file_association_spec(
    executable: str | Path,
) -> WindowsFileAssociationSpec:
    exe = str(Path(executable).expanduser().resolve(strict=False))
    return WindowsFileAssociationSpec(
        extension=PROJECT_FILE_EXTENSION,
        prog_id=WINDOWS_PROG_ID,
        file_type=WINDOWS_FILE_TYPE,
        open_command=f'"{exe}" "%1"',
    )
