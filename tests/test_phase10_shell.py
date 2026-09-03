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


def test_main_window_uses_standard_menu_and_bottom_workspace_navigation() -> None:
    source = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")

    assert "from widgets.workspace_nav import WorkspaceNavigation" in source
    assert "self.workspace_nav = WorkspaceNavigation()" in source
    assert "self.menuBar()" in source
    assert "SidebarNavigation" not in source
    assert "PageHeader" not in source
    assert "from app.ribbon import Ribbon" not in source


def test_bottom_navigation_contains_production_workspaces_only() -> None:
    source = (ROOT / "widgets" / "workspace_nav.py").read_text(
        encoding="utf-8"
    )

    for page in ("PROJECT", "SCRIPT", "DIALOG", "TRACKING", "DATA"):
        assert f'("{page}",' in source

    assert "TOOLS" not in source.split("WORKSPACES =", 1)[1].split(")", 1)[0]
    assert "HELP" not in source.split("WORKSPACES =", 1)[1].split(")", 1)[0]


def test_standard_menu_contract_is_present() -> None:
    source = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")

    for menu in ("&File", "&Project", "&Data", "&Tools", "&Help"):
        assert f'menu_bar.addMenu("{menu}")' in source

    for label in (
        "New Project",
        "Open Project",
        "Sync Source",
        "Tools & Maintenance",
        "Getting Started",
    ):
        assert label in source

    assert "existing_only=True)[:5]" in source


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
