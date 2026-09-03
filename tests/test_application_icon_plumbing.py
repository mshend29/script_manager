from __future__ import annotations

import hashlib
from pathlib import Path

from core.icon_assets import materialize_icon


ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "resources"


def _git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def test_icon_payloads_materialize_byte_for_byte(tmp_path) -> None:
    app_icon = materialize_icon(
        RESOURCES,
        "app.ico",
        output_dir=tmp_path,
    )
    project_icon = materialize_icon(
        RESOURCES,
        "project_file.ico",
        output_dir=tmp_path,
    )

    app_data = app_icon.read_bytes()
    project_data = project_icon.read_bytes()

    assert app_data[:4] == b"\x00\x00\x01\x00"
    assert project_data[:4] == b"\x00\x00\x01\x00"
    assert _git_blob_sha(app_data) == (
        "863f71f0d9b1828590a402a78153f41064e86773"
    )
    assert _git_blob_sha(project_data) == (
        "563596b8f17c7bb045a0848dfc83230de1a41c68"
    )


def test_icon_plumbing_covers_runtime_and_packaging() -> None:
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    resources = (ROOT / "core" / "resource_paths.py").read_text(
        encoding="utf-8"
    )
    spec = (ROOT / "packaging" / "ScriptManager.spec").read_text(
        encoding="utf-8"
    )
    installer = (ROOT / "packaging" / "ScriptManager.iss").read_text(
        encoding="utf-8"
    )

    assert "materialize_icon(" in resources
    assert 'return _icon_path("app.ico")' in resources
    assert 'return _icon_path("project_file.ico")' in resources
    assert "application_icon_path()" in main
    assert "app.setWindowIcon(QIcon(str(icon_path)))" in main

    assert "materialize_packaging_icons(project_root)" in spec
    assert 'project_root / "resources" / "app.ico"' in spec
    assert 'exe_options["icon"] = str(icon_file)' in spec
    assert "**exe_options" in spec

    assert '#ifexist "..\\resources\\app.ico"' in installer
    assert "SetupIconFile=..\\resources\\app.ico" in installer
    assert 'Source: "..\\resources\\project_file.ico"' in installer
    assert 'ValueData: "{app}\\resources\\project_file.ico"' in installer


def test_help_resources_use_frozen_aware_resource_helper() -> None:
    source = (ROOT / "pages" / "help_page.py").read_text(
        encoding="utf-8"
    )
    helper = (ROOT / "core" / "resource_paths.py").read_text(
        encoding="utf-8"
    )

    assert 'HELP_ROOT = resource_path("resources", "help")' in source
    assert 'getattr(sys, "_MEIPASS", None)' in helper
