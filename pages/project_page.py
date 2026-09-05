from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
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

from core.recent_projects import RecentProjectsStore
from pages.project_dashboard_page import ProjectPage as DashboardProjectPage


class RecentDateItem(QTableWidgetItem):
    def __init__(self, text: str, sort_key: str):
        super().__init__(text)
        self.sort_key = str(sort_key or "")

    def __lt__(self, other) -> bool:
        if isinstance(other, RecentDateItem):
            return self.sort_key < other.sort_key
        return super().__lt__(other)


class ProjectPage(DashboardProjectPage):
    """Project workspace with a Recent-project home and the existing dashboard."""

    # Dashboard implementation is preserved in project_dashboard_page.py.
    # Compatibility guarantees retained there include:
    # self.project_name.setWordWrap(True)
    # self.project_identity.setWordWrap(True)

    def __init__(self, parent: QWidget | None = None):
        self._recent_store = RecentProjectsStore(limit=30)
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

        brand = QLabel("PROJECT")
        brand.setObjectName("ProjectSectionTitle")
        sidebar_layout.addWidget(brand)

        helper = QLabel("Create or open a Script Manager project.")
        helper.setObjectName("ProjectSectionHelper")
        helper.setWordWrap(True)
        sidebar_layout.addWidget(helper)
        sidebar_layout.addSpacing(10)

        self.home_new_button = QPushButton("Create New")
        self.home_new_button.setObjectName("ProjectHomeCreateButton")
        self.home_new_button.setProperty("primary", True)
        sidebar_layout.addWidget(self.home_new_button)

        self.home_open_button = QPushButton("Open Project")
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

        title = QLabel("Recent Projects")
        title.setObjectName("ProjectIdentityName")
        content_layout.addWidget(title)

        subtitle = QLabel(
            "Open a recent project, search by project name or location, "
            "or sort the list from the column headers."
        )
        subtitle.setObjectName("ProjectSectionHelper")
        subtitle.setWordWrap(True)
        content_layout.addWidget(subtitle)

        self.recent_search = QLineEdit()
        self.recent_search.setObjectName("ProjectRecentSearch")
        self.recent_search.setPlaceholderText("Search recent projects…")
        self.recent_search.setClearButtonEnabled(True)
        self.recent_search.textChanged.connect(self._filter_recent_projects)
        content_layout.addWidget(self.recent_search)

        self.recent_table = QTableWidget(0, 2)
        self.recent_table.setObjectName("ProjectRecentTable")
        self.recent_table.setHorizontalHeaderLabels(
            ["PROJECT", "LAST OPENED"]
        )
        self.recent_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.recent_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.recent_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.recent_table.setAlternatingRowColors(True)
        self.recent_table.verticalHeader().setVisible(False)
        self.recent_table.setSortingEnabled(True)
        header = self.recent_table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSortIndicator(1, Qt.SortOrder.DescendingOrder)

        self.recent_table.itemDoubleClicked.connect(
            self._open_recent_item
        )
        self.recent_table.itemActivated.connect(
            self._open_recent_item
        )
        content_layout.addWidget(self.recent_table, 1)

        self.recent_empty = QLabel("No recent projects yet.")
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

        self.recent_table.setSortingEnabled(False)
        self.recent_table.setRowCount(0)

        items = self._recent_store.list(existing_only=False)
        for row_index, item in enumerate(items):
            path = Path(item.file_path).expanduser()
            exists = path.is_file()
            project_name = item.project_name or path.stem or "Untitled Project"
            if not exists:
                project_name = f"{project_name}  (Missing)"

            project_item = QTableWidgetItem(project_name)
            project_item.setData(Qt.ItemDataRole.UserRole, item.file_path)
            project_item.setData(
                Qt.ItemDataRole.UserRole + 1,
                f"{project_name}\n{item.file_path}".casefold(),
            )
            project_item.setToolTip(item.file_path)

            opened_item = RecentDateItem(
                self._format_last_opened(item.last_opened_at),
                item.last_opened_at,
            )
            opened_item.setData(Qt.ItemDataRole.UserRole, item.file_path)

            self.recent_table.insertRow(row_index)
            self.recent_table.setItem(row_index, 0, project_item)
            self.recent_table.setItem(row_index, 1, opened_item)

        self.recent_table.setSortingEnabled(True)
        self.recent_table.sortItems(sort_column, sort_order)
        self._filter_recent_projects(self.recent_search.text())
        self.recent_empty.setVisible(self.recent_table.rowCount() == 0)
        self.recent_table.setVisible(self.recent_table.rowCount() > 0)

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
                "Recent Project",
                f"Project file tidak ditemukan:\n{path}",
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
