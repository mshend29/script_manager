from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_context_and_workspace_titles_have_global_horizontal_padding():
    theme = _read("app/theme.py")

    assert "#ContextPanel QLabel" in theme
    assert "#SectionTitle" in theme
    assert "#PageTitle" in theme
    assert "#PageSubtitle" in theme
    assert "padding-left: 7px" in theme
    assert "padding-right: 5px" in theme


def test_recording_checkbox_has_visible_centered_empty_box():
    theme = _read("app/theme.py")
    dialog = _read("pages/dialog_page.py")

    assert "QCheckBox {" in theme
    assert "min-width: 31px" in theme
    assert "max-width: 31px" in theme
    assert "min-height: 30px" in theme
    assert "max-height: 30px" in theme
    assert "padding-left: 6px" in theme
    assert "QCheckBox::indicator" in theme
    assert "width: 19px" in theme
    assert "height: 19px" in theme
    assert "QCheckBox::indicator:unchecked" in theme
    assert "border: 1px solid #9aa0a6" in theme
    assert "QCheckBox()" in dialog
    assert "holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)" in dialog
