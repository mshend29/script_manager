from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.recent_projects import RecentProject


class RecentProjectsDialog(QDialog):
    ACTION_NONE = "none"
    ACTION_OPEN = "open"
    ACTION_NEW = "new"
    ACTION_CLOSE = "close"

    def __init__(
        self,
        recent_projects: list[RecentProject],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("RecentProjectsDialog")
        self.setWindowTitle("Script Manager")
        self.resize(920, 610)
        self.setMinimumSize(760, 520)
        self.setModal(True)

        self.action = self.ACTION_NONE
        self.project_path = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(14)

        title = QLabel("Recent Projects")
        title.setObjectName("RecentProjectsTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "Pilih project terakhir untuk langsung melanjutkan pekerjaan."
        )
        subtitle.setObjectName("RecentProjectsSubtitle")
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("RecentProjectsBody")

        body = QWidget()
        body.setObjectName("RecentProjectsBody")
        grid = QGridLayout(body)
        grid.setContentsMargins(0, 4, 8, 4)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        items = list(recent_projects[:5])
        if items:
            for index, item in enumerate(items):
                card = QPushButton(self._card_text(item))
                card.setProperty("recentProjectCard", True)
                card.setCursor(Qt.CursorShape.PointingHandCursor)
                card.setToolTip(item.file_path)
                card.clicked.connect(
                    lambda checked=False, path=item.file_path:
                        self._open_project(path)
                )
                grid.addWidget(card, index // 2, index % 2)
        else:
            empty = QLabel(
                "Belum ada recent project. Gunakan Create New untuk membuat project pertama."
            )
            empty.setObjectName("RecentProjectsSubtitle")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(empty, 0, 0, 1, 2)

        grid.setRowStretch((len(items) + 1) // 2 + 1, 1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(8)
        buttons.addStretch(1)

        close_button = QPushButton("Close")
        close_button.setProperty("secondary", True)
        close_button.clicked.connect(self._close_application)
        buttons.addWidget(close_button)

        create_button = QPushButton("Create New")
        create_button.setProperty("primary", True)
        create_button.clicked.connect(self._create_new)
        buttons.addWidget(create_button)

        root.addLayout(buttons)

    @staticmethod
    def _card_text(item: RecentProject) -> str:
        name = item.project_name.strip() or Path(item.file_path).stem
        path = str(Path(item.file_path).expanduser())
        opened = item.last_opened_at.replace("T", " ")
        if len(path) > 76:
            path = "…" + path[-75:]
        return f"{name}\n\n{path}\n\nLast opened: {opened}"

    def _open_project(self, path: str) -> None:
        self.action = self.ACTION_OPEN
        self.project_path = str(path)
        self.accept()

    def _create_new(self) -> None:
        self.action = self.ACTION_NEW
        self.accept()

    def _close_application(self) -> None:
        self.action = self.ACTION_CLOSE
        self.reject()

    def reject(self) -> None:
        if self.action == self.ACTION_NONE:
            self.action = self.ACTION_CLOSE
        super().reject()
