from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_recent_path_is_compact_but_search_keeps_full_path() -> None:
    source = (ROOT / "pages" / "project_page.py").read_text(
        encoding="utf-8"
    )

    assert 'normalized = text.replace("\\\\", "/")' in source
    assert "folders = parts[:-1]" in source
    assert 'folders = [folders[0], "…", *folders[-4:]]' in source
    assert 'return " › ".join(folders)' in source
    assert 'f"{raw_project_name}\\n{item.file_path}".casefold()' in source
    assert "setToolTip(full_path)" in source


def test_recent_row_uses_project_file_icon_and_two_line_identity() -> None:
    source = (ROOT / "pages" / "project_page.py").read_text(
        encoding="utf-8"
    )

    assert "project_file_icon_path" in source
    assert "QIcon(str(project_file_icon_path()))" in source
    assert "icon.pixmap(QSize(30, 30))" in source
    assert "RecentProjectCell(" in source
    assert "QVBoxLayout()" in source
    assert "QLabel(project_name)" in source
    assert "QLabel(display_path)" in source
