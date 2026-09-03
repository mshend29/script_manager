from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _action_strings(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        value = node.value
        if "." not in value:
            continue
        prefix, _, action = value.partition(".")
        if prefix in {
            "project",
            "client",
            "source",
            "script",
            "dialog",
            "tracking",
            "data",
            "tools",
            "help",
        } and action and " " not in value:
            values.add(value)

    return values


def test_main_window_uses_phase10_desktop_shell_not_ribbon() -> None:
    source = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")

    assert "from widgets.sidebar_nav import SidebarNavigation" in source
    assert "from widgets.page_header import PageHeader" in source
    assert "self.sidebar = SidebarNavigation()" in source
    assert "self.page_header = PageHeader()" in source
    assert "from app.ribbon import Ribbon" not in source
    assert "self.ribbon = Ribbon()" not in source


def test_sidebar_contains_only_product_navigation_no_account_chrome() -> None:
    source = (ROOT / "widgets" / "sidebar_nav.py").read_text(
        encoding="utf-8"
    )

    for page in (
        "PROJECT",
        "SCRIPT",
        "DIALOG",
        "TRACKING",
        "DATA",
        "TOOLS",
        "HELP",
    ):
        assert f'("{page}",' in source

    for forbidden in (
        "avatar",
        "login",
        "logout",
        "account",
        "producer",
        "online",
        "profile",
    ):
        assert forbidden not in source.casefold()


def test_every_contextual_header_action_has_main_window_handler() -> None:
    declared = _action_strings(ROOT / "widgets" / "page_header.py")
    handled = _action_strings(ROOT / "app" / "main_window.py")

    assert declared - handled == set()


def test_sync_source_is_single_primary_project_action() -> None:
    source = (ROOT / "widgets" / "page_header.py").read_text(
        encoding="utf-8"
    )

    assert source.count('HeaderAction("source.sync", "Sync Source"') == 1
    assert 'HeaderAction("source.sync", "Sync Source", primary=True)' in source


def test_phase10_light_tokens_are_centralized() -> None:
    source = (ROOT / "app" / "theme.py").read_text(encoding="utf-8")

    expected = {
        '"app_background": "#F6F7F9"',
        '"sidebar": "#F1F3F6"',
        '"surface": "#FFFFFF"',
        '"text_primary": "#181B20"',
        '"text_secondary": "#717784"',
        '"accent": "#4F46E5"',
        '"accent_soft": "#EEF2FF"',
        '"recorded": "#22C55E"',
        '"attention": "#F59E0B"',
        '"source_revised": "#F97316"',
        '"revision": "#8B5CF6"',
        '"delivered": "#3B82F6"',
        '"error": "#EF4444"',
    }
    for token in expected:
        assert token in source
