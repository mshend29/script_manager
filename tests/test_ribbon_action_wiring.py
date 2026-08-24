from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTION_PREFIXES = {
    "project",
    "client",
    "source",
    "script",
    "dialog",
    "tracking",
    "data",
    "tools",
}
REMOVED_UNSUPPORTED = {
    "script.export",
    "dialog.search",
    "tracking.mark_stemmed",
    "tools.settings",
    "tools.logs",
}


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
        if prefix in ACTION_PREFIXES and action and " " not in value:
            values.add(value)

    return values


def test_every_visible_ribbon_action_has_a_main_window_handler():
    declared = _action_strings(ROOT / "app" / "ribbon.py")
    handled = _action_strings(ROOT / "app" / "main_window.py")

    missing_handlers = declared - handled
    assert missing_handlers == set(), (
        "Visible ribbon actions without handlers: "
        + ", ".join(sorted(missing_handlers))
    )


def test_unsupported_placeholder_actions_are_not_advertised():
    declared = _action_strings(ROOT / "app" / "ribbon.py")
    assert declared.isdisjoint(REMOVED_UNSUPPORTED)
