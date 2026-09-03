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
    resources_dir = resource_path("resources")
    bundled = resources_dir / icon_name

    if bundled.is_file():
        try:
            if bundled.read_bytes()[:4] == b"\x00\x00\x01\x00":
                return bundled
        except OSError:
            pass

    return materialize_icon(resources_dir, icon_name)


def application_icon_path() -> Path:
    return _icon_path("app.ico")


def project_file_icon_path() -> Path:
    return _icon_path("project_file.ico")
