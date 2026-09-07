from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


ReviewStatus = Literal["ready", "warning", "error"]


@dataclass(frozen=True)
class ProjectReviewSection:
    title: str
    step_index: int
    status: ReviewStatus
    details: tuple[str, ...]
    message: str = ""


class ProjectReviewPanel(QWidget):
    step_requested = Signal(int)

    STATUS_LABELS = {
        "ready": "✓ Siap",
        "warning": "⚠ Opsional / dapat dilengkapi nanti",
        "error": "✕ Harus diperbaiki",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sections: tuple[ProjectReviewSection, ...] = ()

        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(0, 0, 0, 0)
        self.root.setSpacing(10)

        self.summary = QLabel("Review belum dihitung.")
        self.summary.setObjectName("PageSubtitle")
        self.summary.setWordWrap(True)
        self.root.addWidget(self.summary)

        self.sections_container = QWidget()
        self.sections_layout = QVBoxLayout(self.sections_container)
        self.sections_layout.setContentsMargins(0, 0, 0, 0)
        self.sections_layout.setSpacing(10)
        self.root.addWidget(self.sections_container)

    @property
    def sections(self) -> tuple[ProjectReviewSection, ...]:
        return self._sections

    def set_sections(self, sections: tuple[ProjectReviewSection, ...]) -> None:
        self._sections = tuple(sections)
        self._clear_sections()

        error_count = sum(section.status == "error" for section in self._sections)
        warning_count = sum(section.status == "warning" for section in self._sections)
        if error_count:
            self.summary.setText(
                f"✕ {error_count} bagian masih harus diperbaiki sebelum proyek dapat dibuat."
            )
        elif warning_count:
            self.summary.setText(
                f"⚠ Konfigurasi operasional siap; {warning_count} bagian memiliki warning/opsional."
            )
        else:
            self.summary.setText("✓ Seluruh konfigurasi blocking siap untuk membuat proyek.")

        for section in self._sections:
            self.sections_layout.addWidget(self._section_widget(section))
        self.sections_layout.addStretch(1)

    def _section_widget(self, section: ProjectReviewSection) -> QGroupBox:
        box = QGroupBox(section.title)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        status = QLabel(self.STATUS_LABELS[section.status])
        status.setStyleSheet("font-weight: 700;")
        header.addWidget(status, 1)

        edit_button = QPushButton("Ubah")
        edit_button.setProperty("secondary", True)
        edit_button.setAccessibleName(f"Ubah {section.title}")
        edit_button.clicked.connect(
            lambda _checked=False, step=section.step_index: self.step_requested.emit(step)
        )
        header.addWidget(edit_button)
        layout.addLayout(header)

        if section.message:
            message = QLabel(section.message)
            message.setObjectName("PageSubtitle")
            message.setWordWrap(True)
            layout.addWidget(message)

        for detail in section.details:
            label = QLabel(detail)
            label.setWordWrap(True)
            label.setTextInteractionFlags(label.textInteractionFlags())
            layout.addWidget(label)

        return box

    def _clear_sections(self) -> None:
        while self.sections_layout.count():
            item = self.sections_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
