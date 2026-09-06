from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_startup_goes_directly_to_project_workspace_after_splash() -> None:
    source = _read("main.py")

    assert "window.showMaximized()" in source
    assert "splash.finish(window)" in source
    assert "show_startup_recent_projects" not in source
    assert "QTimer.singleShot" not in source
    assert "Recent Projects dialog" in source


def test_project_home_replaces_startup_recent_dialog_visually() -> None:
    source = _read("pages/project_page.py")

    assert 'self.project_home = self._build_project_home()' in source
    assert 'sidebar.setFixedWidth(230)' in source
    assert "Buat Baru" in source
    assert "Buka Proyek" in source
    assert "Proyek Terbaru" in source
    assert '["PROJECT", "LAST OPENED"]' in source
    assert 'setPlaceholderText("Cari proyek terbaru…")' in source
    assert "setSortingEnabled(True)" in source
    assert "Qt.SortOrder.DescendingOrder" in source


def test_recent_project_rows_follow_excel_like_file_list_reference() -> None:
    source = _read("pages/project_page.py")

    assert "class RecentProjectCell(QWidget)" in source
    assert "project_file_icon_path" in source
    assert 'icon_label.setFixedSize(38, 38)' in source
    assert 'name_label = QLabel(project_name)' in source
    assert 'path_label = QLabel(display_path)' in source
    assert 'self._compact_project_path(item.file_path)' in source
    assert 'return " › ".join(folders)' in source
    assert "verticalHeader().setDefaultSectionSize(62)" in source

    # Native table text must stay completely absent so it cannot overlap the
    # custom icon/name renderer under any selection or hover palette.
    assert "class RecentProjectItem(QTableWidgetItem)" in source
    assert 'super().__init__("")' in source
    assert "project_item = RecentProjectItem(raw_project_name)" in source

    # The Recent list behaves like a launcher: no persistent selection
    # highlight, one click opens, but hover feedback remains visible.
    assert "QAbstractItemView.SelectionMode.NoSelection" in source
    assert "self.recent_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)" in source
    assert "self.recent_table.itemClicked.connect(self._open_recent_item)" in source
    assert "itemDoubleClicked.connect" not in source
    assert "class RecentProjectTable(QTableWidget)" in source
    assert "self.setMouseTracking(True)" in source
    assert "hover_row_changed = Signal(int)" in source
    assert "self.recent_table.hover_row_changed.connect(" in source
    assert 'COLORS["accent_soft"] if hovered else COLORS["surface"]' in source
    assert "cell.set_hovered(hovered)" in source

    # Last Opened remains sortable but gets a deliberately wider readable
    # column instead of shrinking to its minimum contents width.
    assert "QHeaderView.ResizeMode.Interactive" in source
    assert "self.recent_table.setColumnWidth(1, 240)" in source


def test_recent_history_supports_longer_project_home_list() -> None:
    source = _read("core/recent_projects.py")
    assert "RECENT_PROJECTS_LIMIT = 30" in source
