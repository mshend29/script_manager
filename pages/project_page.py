from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.theme import COLORS
from core.recent_projects import RecentProjectsStore
from core.resource_paths import project_file_icon_path
from pages.project_dashboard_page import ProjectPage as DashboardProjectPage


class RecentDateItem(QTableWidgetItem):
    def __init__(self, text: str, sort_key: str):
        super().__init__(text)
        self.sort_key = str(sort_key or "")
        self.setTextAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

    def __lt__(self, other) -> bool:
        if isinstance(other, RecentDateItem):
            return self.sort_key < other.sort_key
        return super().__lt__(other)


class RecentProjectItem(QTableWidgetItem):
    """Non-visual backing item for recent-project sorting and metadata."""

    def __init__(self, sort_key: str):
        # The visible name/path is rendered only by RecentProjectCell. Keeping
        # the native DisplayRole empty prevents Qt selection/focus painting
        # from ever drawing duplicate text underneath the project icon.
        super().__init__("")
        self.sort_key = str(sort_key or "").casefold()

    def __lt__(self, other) -> bool:
        if isinstance(other, RecentProjectItem):
            return self.sort_key < other.sort_key
        return super().__lt__(other)


class RecentProjectTable(QTableWidget):
    """Recent list with row hover feedback but no persistent selection."""

    hover_row_changed = Signal(int)

    def __init__(self, rows: int, columns: int, parent=None) -> None:
        super().__init__(rows, columns, parent)
        self._hover_row = -1
        self.setMouseTracking(True)

    def mouseMoveEvent(self, event) -> None:
        row = self.indexAt(event.position().toPoint()).row()
        if row != self._hover_row:
            self._hover_row = row
            self.hover_row_changed.emit(row)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        if self._hover_row != -1:
            self._hover_row = -1
            self.hover_row_changed.emit(-1)
        super().leaveEvent(event)


class RecentProjectCell(QWidget):
    """Excel-like recent-project row: icon, project name, and compact path."""

    def __init__(
        self,
        project_name: str,
        display_path: str,
        full_path: str,
        *,
        missing: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ProjectRecentProjectCell")
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        self.setToolTip(full_path)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(11)

        icon_label = QLabel()
        icon_label.setObjectName("ProjectRecentIcon")
        icon_label.setFixedSize(38, 38)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QIcon(str(project_file_icon_path()))
        pixmap = icon.pixmap(QSize(30, 30))
        if pixmap.isNull():
            icon_label.setText("SM")
            icon_label.setObjectName("ProjectRecentIconFallback")
        else:
            icon_label.setPixmap(pixmap)
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        name_label = QLabel(project_name)
        name_label.setObjectName("ProjectRecentName")
        name_label.setProperty("missing", missing)
        name_label.setToolTip(full_path)
        text_layout.addWidget(name_label)

        path_label = QLabel(display_path)
        path_label.setObjectName("ProjectRecentPath")
        path_label.setToolTip(full_path)
        text_layout.addWidget(path_label)

        layout.addLayout(text_layout, 1)

    def set_hovered(self, hovered: bool) -> None:
        background = COLORS["accent_soft"] if hovered else "transparent"
        self.setStyleSheet(f"background: {background};")


class ProjectPage(DashboardProjectPage):
    """Project workspace with a Recent-project home and the existing dashboard."""

    # Dashboard implementation is preserved in project_dashboard_page.py.
    # Compatibility guarantees retained there include:
    # self.project_name.setWordWrap(True)
    # self.project_identity.setWordWrap(True)

    def __init__(self, parent: QWidget | None = None):
        self._recent_store = RecentProjectsStore(limit=30)
        self._recent_hover_row = -1
        super().__init__(parent)

        root = self.layout()
        self._dashboard_view = root.itemAt(0).widget()

        self._dashboard_new_button = self.new_button
        self._dashboard_open_button = self.open_button

        self.project_home = self._build_project_home()
        root.insertWidget(0, self.project_home)

        # MainWindow already connects these public buttons to New/Open actions.
        self.new_button = self.home_new_button
        self.open_button = self.home_open_button

        self.show_home()

    def _build_project_home(self) -> QWidget:
        home = QWidget()
        home.setObjectName("ProjectHome")

        layout = QHBoxLayout(home)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("ProjectHomeSidebar")
        sidebar.setFixedWidth(230)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 24, 20, 24)
        sidebar_layout.setSpacing(10)

        brand = QLabel("PROYEK")
        brand.setObjectName("ProjectSectionTitle")
        sidebar_layout.addWidget(brand)

        helper = QLabel('Buat atau buka proyek Script Manager.')
        helper.setObjectName("ProjectSectionHelper")
        helper.setWordWrap(True)
        sidebar_layout.addWidget(helper)
        sidebar_layout.addSpacing(10)

        self.home_new_button = QPushButton('Buat Baru')
        self.home_new_button.setObjectName("ProjectHomeCreateButton")
        self.home_new_button.setProperty("primary", True)
        sidebar_layout.addWidget(self.home_new_button)

        self.home_open_button = QPushButton('Buka Proyek')
        self.home_open_button.setObjectName("ProjectHomeOpenButton")
        self.home_open_button.setProperty("secondary", True)
        sidebar_layout.addWidget(self.home_open_button)
        sidebar_layout.addStretch(1)

        layout.addWidget(sidebar)

        content = QWidget()
        content.setObjectName("ProjectHomeContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(28, 24, 28, 28)
        content_layout.setSpacing(12)

        title = QLabel('Proyek Terbaru')
        title.setObjectName("ProjectIdentityName")
        content_layout.addWidget(title)

        subtitle = QLabel(
            "Buka proyek terbaru, cari berdasarkan nama atau lokasi, "
            "atau urutkan daftar melalui judul kolom."
        )
        subtitle.setObjectName("ProjectSectionHelper")
        subtitle.setWordWrap(True)
        content_layout.addWidget(subtitle)

        self.recent_search = QLineEdit()
        self.recent_search.setObjectName("ProjectRecentSearch")
        self.recent_search.setPlaceholderText('Cari proyek terbaru…')
        self.recent_search.setClearButtonEnabled(True)
        self.recent_search.textChanged.connect(self._filter_recent_projects)
        content_layout.addWidget(self.recent_search)

        self.recent_table = RecentProjectTable(0, 2)
        self.recent_table.setObjectName("ProjectRecentTable")
        self.recent_table.setHorizontalHeaderLabels(
            ["PROYEK", "TERAKHIR DIBUKA"]
        )
        self.recent_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        # Recent rows behave like launch targets rather than selectable data.
        # Selection stays disabled, while RecentProjectTable provides a
        # temporary hover cue so the row under the pointer is still obvious.
        self.recent_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.recent_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.recent_table.setAlternatingRowColors(False)
        self.recent_table.setShowGrid(False)
        self.recent_table.setWordWrap(False)
        self.recent_table.verticalHeader().setVisible(False)
        self.recent_table.verticalHeader().setDefaultSectionSize(62)
        self.recent_table.setSortingEnabled(True)
        self.recent_table.hover_row_changed.connect(
            self._set_recent_hover_row
        )

        header = self.recent_table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setMinimumSectionSize(120)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.recent_table.setColumnWidth(1, 240)
        header.setSortIndicator(1, Qt.SortOrder.DescendingOrder)

        # One click is enough to open a Recent Project. The custom cell widget
        # is transparent for mouse events, so clicks still land on the table.
        self.recent_table.itemClicked.connect(self._open_recent_item)
        content_layout.addWidget(self.recent_table, 1)

        self.recent_empty = QLabel('Belum ada proyek terbaru.')
        self.recent_empty.setObjectName("ProjectEmptyHint")
        self.recent_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recent_empty.setWordWrap(True)
        content_layout.addWidget(self.recent_empty)

        layout.addWidget(content, 1)
        return home

    def show_home(self) -> None:
        if not hasattr(self, "project_home"):
            return
        self._dashboard_view.hide()
        self.project_home.show()
        self.refresh_recent_projects()

    def show_dashboard(self) -> None:
        if not hasattr(self, "project_home"):
            return
        self.project_home.hide()
        self._dashboard_view.show()

    def refresh_recent_projects(self) -> None:
        if not hasattr(self, "recent_table"):
            return

        header = self.recent_table.horizontalHeader()
        sort_column = header.sortIndicatorSection()
        sort_order = header.sortIndicatorOrder()

        self._recent_hover_row = -1
        self.recent_table.setSortingEnabled(False)
        self.recent_table.setRowCount(0)

        items = self._recent_store.list(existing_only=False)
        for row_index, item in enumerate(items):
            path = Path(item.file_path).expanduser()
            exists = path.is_file()
            raw_project_name = item.project_name or path.stem or 'Proyek Tanpa Nama'
            project_name = (
                f"{raw_project_name}  (Missing)"
                if not exists
                else raw_project_name
            )
            display_path = self._compact_project_path(item.file_path)

            project_item = RecentProjectItem(raw_project_name)
            project_item.setData(Qt.ItemDataRole.UserRole, item.file_path)
            project_item.setData(
                Qt.ItemDataRole.UserRole + 1,
                f"{raw_project_name}\n{item.file_path}".casefold(),
            )
            project_item.setToolTip(item.file_path)

            opened_item = RecentDateItem(
                self._format_last_opened(item.last_opened_at),
                item.last_opened_at,
            )
            opened_item.setData(Qt.ItemDataRole.UserRole, item.file_path)
            opened_item.setToolTip(
                f"Last opened: {self._format_last_opened(item.last_opened_at)}"
            )

            self.recent_table.insertRow(row_index)
            self.recent_table.setItem(row_index, 0, project_item)
            self.recent_table.setItem(row_index, 1, opened_item)
            self.recent_table.setCellWidget(
                row_index,
                0,
                RecentProjectCell(
                    project_name,
                    display_path,
                    item.file_path,
                    missing=not exists,
                ),
            )

        self.recent_table.setSortingEnabled(True)
        self.recent_table.sortItems(sort_column, sort_order)
        self._filter_recent_projects(self.recent_search.text())
        self.recent_empty.setVisible(self.recent_table.rowCount() == 0)
        self.recent_table.setVisible(self.recent_table.rowCount() > 0)

    def _set_recent_hover_row(self, row: int) -> None:
        previous = self._recent_hover_row
        if previous == row:
            return

        self._paint_recent_hover_row(previous, hovered=False)
        self._recent_hover_row = row
        self._paint_recent_hover_row(row, hovered=True)

    def _paint_recent_hover_row(self, row: int, *, hovered: bool) -> None:
        if not hasattr(self, "recent_table"):
            return
        if row < 0 or row >= self.recent_table.rowCount():
            return

        color = COLORS["accent_soft"] if hovered else COLORS["surface"]
        brush = QBrush(QColor(color))
        for column in range(self.recent_table.columnCount()):
            item = self.recent_table.item(row, column)
            if item is not None:
                item.setBackground(brush)

        cell = self.recent_table.cellWidget(row, 0)
        if isinstance(cell, RecentProjectCell):
            cell.set_hovered(hovered)

    @staticmethod
    def _compact_project_path(value: str) -> str:
        """Return a short Explorer-like parent path for the Recent list."""
        text = str(value or "").strip()
        if not text:
            return "—"

        normalized = text.replace("\\", "/")
        parts = [part for part in normalized.split("/") if part]
        if len(parts) <= 1:
            return text

        # The filename is already represented by the project name. Show only
        # its location, similar to Excel's Recent view.
        folders = parts[:-1]
        if not folders:
            return "—"

        if len(folders) > 5:
            folders = [folders[0], "…", *folders[-4:]]

        return " › ".join(folders)

    @staticmethod
    def _format_last_opened(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return "—"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return text
        return parsed.strftime("%d %b %Y, %H:%M")

    def _filter_recent_projects(self, text: str) -> None:
        if not hasattr(self, "recent_table"):
            return
        query = str(text or "").strip().casefold()
        for row in range(self.recent_table.rowCount()):
            item = self.recent_table.item(row, 0)
            searchable = (
                str(item.data(Qt.ItemDataRole.UserRole + 1) or "")
                if item is not None
                else ""
            )
            self.recent_table.setRowHidden(
                row,
                bool(query and query not in searchable),
            )

    def _open_recent_item(self, item: QTableWidgetItem) -> None:
        row = item.row()
        project_item = self.recent_table.item(row, 0)
        if project_item is None:
            return
        path_text = str(
            project_item.data(Qt.ItemDataRole.UserRole) or ""
        ).strip()
        if not path_text:
            return

        path = Path(path_text).expanduser()
        if not path.is_file():
            QMessageBox.warning(
                self,
                'Proyek Terbaru',
                f"Proyek file tidak ditemukan:\n{path}",
            )
            return

        opener = getattr(self.window(), "open_project_path", None)
        if callable(opener):
            opener(path)

    def set_project_metadata(
        self,
        *,
        project_code: str = "",
        client_name: str = "",
        drive_configured: bool = False,
    ) -> None:
        self.show_dashboard()
        super().set_project_metadata(
            project_code=project_code,
            client_name=client_name,
            drive_configured=drive_configured,
        )

    def reset_view(self) -> None:
        super().reset_view()
        if hasattr(self, "project_home"):
            self.show_home()
