from __future__ import annotations

import base64
import tempfile
from pathlib import Path


ICO_MAGIC = b"\x00\x00\x01\x00"


def _read_payload(resources_dir: Path, icon_name: str) -> bytes:
    single = resources_dir / f"{icon_name}.b64"
    if single.is_file():
        encoded = single.read_text(encoding="ascii")
    else:
        chunks = sorted(resources_dir.glob(f"{icon_name}.b64.part*"))
        if not chunks:
            raise FileNotFoundError(
                f"Icon payload not found for {icon_name}"
            )
        encoded = "".join(
            chunk.read_text(encoding="ascii")
            for chunk in chunks
        )

    data = base64.b64decode(
        "".join(encoded.split()),
        validate=True,
    )
    if not data.startswith(ICO_MAGIC):
        raise ValueError(f"Invalid ICO payload for {icon_name}")
    return data


def materialize_icon(
    resources_dir: Path,
    icon_name: str,
    *,
    output_dir: Path | None = None,
) -> Path:
    resources_dir = Path(resources_dir)
    target_dir = (
        Path(output_dir)
        if output_dir is not None
        else Path(tempfile.gettempdir()) / "script_manager_icons"
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    target = target_dir / icon_name
    data = _read_payload(resources_dir, icon_name)

    if not target.is_file() or target.read_bytes() != data:
        target.write_bytes(data)

    return target


def materialize_packaging_icons(project_root: Path) -> tuple[Path, Path]:
    project_root = Path(project_root)
    resources_dir = project_root / "resources"

    app_icon = materialize_icon(
        resources_dir,
        "app.ico",
        output_dir=resources_dir,
    )
    project_icon = materialize_icon(
        resources_dir,
        "project_file.ico",
        output_dir=resources_dir,
    )
    return app_icon, project_icon
