from __future__ import annotations

import sys
from pathlib import Path


def resource_root() -> Path:
    """Return the root that contains bundled application resources."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(str(frozen_root))
    return Path(__file__).resolve().parents[1]


def resource_path(*parts: str) -> Path:
    return resource_root().joinpath(*parts)


def application_icon_path() -> Path:
    return resource_path("resources", "app.ico")
