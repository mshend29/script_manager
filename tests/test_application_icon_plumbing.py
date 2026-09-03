from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_icon_uses_one_optional_resource_across_runtime_and_packaging() -> None:
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

    assert 'resource_path("resources", "app.ico")' in resources
    assert 'resource_path("resources", "project_file.ico")' in resources
    assert "application_icon_path()" in main
    assert "app.setWindowIcon(QIcon(str(icon_path)))" in main

    assert 'project_root / "resources" / "app.ico"' in spec
    assert 'exe_options["icon"] = str(icon_file)' in spec
    assert "**exe_options" in spec

    assert '#ifexist "..\\resources\\app.ico"' in installer
    assert "SetupIconFile=..\\resources\\app.ico" in installer
    assert 'Source: "..\\resources\\project_file.ico"' in installer
    assert 'ValueData: "{app}\\resources\\project_file.ico"' in installer


def test_help_resources_use_frozen_aware_resource_helper() -> None:
    source = (ROOT / "pages" / "help_page.py").read_text(encoding="utf-8")
    helper = (ROOT / "core" / "resource_paths.py").read_text(
        encoding="utf-8"
    )

    assert 'HELP_ROOT = resource_path("resources", "help")' in source
    assert 'getattr(sys, "_MEIPASS", None)' in helper


def test_icon_assets_exist_as_real_ico_files() -> None:
    app_icon = ROOT / "resources" / "app.ico"
    project_icon = ROOT / "resources" / "project_file.ico"

    assert app_icon.is_file()
    assert project_icon.is_file()
    assert app_icon.read_bytes()[:4] == b"\x00\x00\x01\x00"
    assert project_icon.read_bytes()[:4] == b"\x00\x00\x01\x00"
