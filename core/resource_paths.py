from __future__ import annotations

import sys
from pathlib import Path

from core.icon_assets import materialize_icon


def resource_root() -> Path:
    """Return the root that contains bundled application resources."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(str(frozen_root))
    return Path(__file__).resolve().parents[1]


def resource_path(*parts: str) -> Path:
    return resource_root().joinpath(*parts)


def _icon_path(icon_name: str) -> Path:
    return materialize_icon(
        resource_path("resources"),
        icon_name,
    )


def application_icon_path() -> Path:
    return _icon_path("app.ico")


def project_file_icon_path() -> Path:
    return _icon_path("project_file.ico")
