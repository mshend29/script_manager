from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from app.theme import COLORS


ROOT = Path(__file__).resolve().parents[1]

VISUAL_IMPLEMENTATION_FILES = (
    "pages/project_page.py",
    "pages/dialog_page.py",
    "pages/tracking_page.py",
    "pages/tracking_compact_page.py",
    "widgets/episode_chip.py",
    "widgets/page_header.py",
    "widgets/sidebar_nav.py",
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _channel(value: int) -> float:
    normalized = value / 255.0
    if normalized <= 0.04045:
        return normalized / 12.92
    return ((normalized + 0.055) / 1.055) ** 2.4


def _luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    red, green, blue = (
        int(value[index : index + 2], 16)
        for index in (0, 2, 4)
    )
    return (
        0.2126 * _channel(red)
        + 0.7152 * _channel(green)
        + 0.0722 * _channel(blue)
    )


def _contrast(first: str, second: str) -> float:
    high, low = sorted(
        (_luminance(first), _luminance(second)),
        reverse=True,
    )
    return (high + 0.05) / (low + 0.05)


def test_phase10_visual_colors_are_centralized_in_theme() -> None:
    pattern = re.compile(r"#[0-9A-Fa-f]{6}")

    for path in VISUAL_IMPLEMENTATION_FILES:
        assert pattern.findall(_read(path)) == [], path


def test_shared_shell_components_are_reused_by_main_window() -> None:
    main = _read("app/main_window.py")
    header = _read("widgets/page_header.py")
    sidebar = _read("widgets/sidebar_nav.py")

    assert "from widgets.page_header import PageHeader" in main
    assert "from widgets.sidebar_nav import SidebarNavigation" in main
    assert "self.page_header = PageHeader()" in main
    assert "self.sidebar = SidebarNavigation()" in main
    assert "PAGE_HEADER_SPECS" in header
    assert "PRIMARY_PAGES" in sidebar
    assert "SECONDARY_PAGES" in sidebar

    assert "from app.ribbon import Ribbon" not in main
    assert 'getattr(window, "ribbon", None)' not in _read(
        "pages/tracking_page.py"
    )
    assert 'getattr(window, "ribbon", None)' not in _read(
        "widgets/episode_chip.py"
    )


@pytest.mark.parametrize(
    ("foreground", "background"),
    (
        ("recorded_text", "recorded_soft"),
        ("ready_to_stem_text", "ready_to_stem_soft"),
        ("stemmed_text", "stemmed_soft"),
        ("attention_text", "attention_soft"),
        ("source_revised_text", "source_revised_soft"),
        ("revision_text", "revision_soft"),
        ("delivered_text", "delivered_soft"),
        ("error_text", "error_soft"),
        ("neutral_text", "neutral_soft"),
    ),
)
def test_semantic_text_has_accessible_contrast(
    foreground: str,
    background: str,
) -> None:
    assert _contrast(COLORS[foreground], COLORS[background]) >= 4.5


def test_phase10_pr_does_not_modify_business_rule_modules() -> None:
    result = subprocess.run(
        ["git", "rev-list", "--parents", "-n", "1", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    parts = result.stdout.strip().split()

    # GitHub PR CI checks out refs/pull/<n>/merge, which has two parents.
    # Ordinary local/main commits do not, so there is no PR delta to inspect.
    if len(parts) < 3:
        pytest.skip("Business-rule diff guard only applies to PR merge refs.")

    base_parent = parts[1]
    changed = subprocess.run(
        ["git", "diff", "--name-only", base_parent, "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    forbidden_prefixes = (
        "services/",
        "import_engine/",
    )
    forbidden_exact = {
        "core/database.py",
        "core/project.py",
        "core/project_settings.py",
    }

    offenders = [
        path
        for path in changed
        if path.startswith(forbidden_prefixes)
        or path in forbidden_exact
    ]
    assert offenders == []
