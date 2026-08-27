from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.project import Project
from services.audit_service import AuditService
from services.project_diagnostics_service import (
    STATUS_ERROR,
    STATUS_INFO,
    STATUS_OK,
    STATUS_WARNING,
    ProjectDiagnostics,
    ProjectDiagnosticsService,
)
from widgets.context_panel import ContextPanel
from widgets.page_shell import PageShell


class ToolsPage(PageShell):
    action_requested = Signal(str)

    def __init__(self, parent=None):
        self._project: Project | None = None

        context = ContextPanel("TOOLS")

        context.add_section_title("PROJECT")
        for action, label in (
            ("tools.open_project_folder", "Open Project Folder"),
            ("tools.open_source_folder", "Open Source Folder"),
            ("tools.open_output_folder", "Open Stem / Export"),
            ("tools.open_delivery_folder", "Open Setoran"),
        ):
            button = QPushButton(label)
            button.setProperty("secondary", True)
            button.clicked.connect(
                lambda checked=False, value=action:
                self.action_requested.emit(value)
            )
            context.add_widget(button)

        context.add_section_title("MAINTENANCE")
        for action, label in (
            ("tools.diagnostics", "Run Diagnostics"),
            ("tools.backup", "Create Backup"),
            ("tools.restore_backup", "Restore Backup"),
            ("tools.open_backups", "Open Backups"),
            ("tools.open_logs", "Open Logs"),
        ):
            button = QPushButton(label)
            button.setProperty(
                "primary" if action == "tools.diagnostics" else "secondary",
                True,
            )
            button.clicked.connect(
                lambda checked=False, value=action:
                self.action_requested.emit(value)
            )
            context.add_widget(button)

        context.add_stretch()

        workspace = QWidget()
        root = QVBoxLayout(workspace)
        root.setContentsMargins(24, 20, 24, 22)
        root.setSpacing(10)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(1)

        title = QLabel("Tools & Maintenance")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Diagnostics, filesystem shortcuts, database safety, dan audit history."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)

        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setProperty("secondary", True)
        self.refresh_button.clicked.connect(
            lambda: self.action_requested.emit("tools.diagnostics")
        )
        header.addWidget(self.refresh_button)
        root.addLayout(header)

        summary_title = QLabel("PROJECT DIAGNOSTICS")
        summary_title.setObjectName("SectionTitle")
        root.addWidget(summary_title)

        cards = QGridLayout()
        cards.setHorizontalSpacing(8)
        cards.setVerticalSpacing(8)

        self.health_card = self._metric_card("Project Health", "—")
        self.validation_card = self._metric_card("Validation", "0")
        self.output_card = self._metric_card("Output Warnings", "0")
        self.backup_card = self._metric_card("Backups", "0")
        self.audit_card = self._metric_card("Audit Entries", "0")

        for index, card in enumerate(
            (
                self.health_card,
                self.validation_card,
                self.output_card,
                self.backup_card,
                self.audit_card,
            )
        ):
            cards.addWidget(card, 0, index)
        root.addLayout(cards)

        self.diagnostics_table = QTableWidget(0, 4)
        self.diagnostics_table.setHorizontalHeaderLabels(
            ["CHECK", "STATUS", "VALUE", "DETAIL"]
        )
        self.diagnostics_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.diagnostics_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.diagnostics_table.setAlternatingRowColors(True)
        self.diagnostics_table.verticalHeader().setVisible(False)
        self.diagnostics_table.setMaximumHeight(260)

        header_view = self.diagnostics_table.horizontalHeader()
        header_view.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        header_view.setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        header_view.setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.diagnostics_table)

        shortcut_title = QLabel("FOLDERS & DRIVE LINKS")
        shortcut_title.setObjectName("SectionTitle")
        root.addWidget(shortcut_title)

        shortcut_frame = QFrame()
        shortcut_frame.setObjectName("DashboardCard")
        shortcuts = QGridLayout(shortcut_frame)
        shortcuts.setContentsMargins(10, 9, 10, 9)
        shortcuts.setHorizontalSpacing(7)
        shortcuts.setVerticalSpacing(7)

        actions = (
            ("tools.open_project_folder", "Project Folder"),
            ("tools.open_source_folder", "Source Folder"),
            ("tools.open_output_folder", "Stem / Export"),
            ("tools.open_delivery_folder", "Setoran Folder"),
            ("tools.open_backups", "Backups Folder"),
            ("tools.open_logs", "Logs Folder"),
            ("tools.open_main_drive", "Main Drive"),
            ("tools.open_material_drive", "Material Drive"),
            ("tools.open_delivery_drive", "Delivery Drive"),
        )
        for index, (action, label) in enumerate(actions):
            button = QPushButton(label)
            button.setProperty("secondary", True)
            button.clicked.connect(
                lambda checked=False, value=action:
                self.action_requested.emit(value)
            )
            shortcuts.addWidget(button, index // 3, index % 3)

        for column in range(3):
            shortcuts.setColumnStretch(column, 1)

        root.addWidget(shortcut_frame)

        audit_title = QLabel("AUDIT HISTORY")
        audit_title.setObjectName("SectionTitle")
        root.addWidget(audit_title)

        self.audit_table = QTableWidget(0, 4)
        self.audit_table.setHorizontalHeaderLabels(
            ["DATE", "TYPE", "ACTION", "SUMMARY"]
        )
        self.audit_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.audit_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.audit_table.setAlternatingRowColors(True)
        self.audit_table.verticalHeader().setVisible(False)

        audit_header = self.audit_table.horizontalHeader()
        audit_header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        audit_header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        audit_header.setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        audit_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.audit_table, 1)

        super().__init__(context, workspace, parent)
        self.reset_view()

    @staticmethod
    def _metric_card(label: str, value: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("DashboardCard")
        frame.setMinimumHeight(72)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(1)

        value_label = QLabel(value)
        value_label.setObjectName("CardValue")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        caption = QLabel(label)
        caption.setObjectName("CardLabel")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)

        frame.value_label = value_label
        layout.addWidget(value_label)
        layout.addWidget(caption)
        return frame

    def set_project(
        self,
        project: Project | None,
        *,
        run_diagnostics: bool = True,
    ) -> None:
        self._project = project
        if project is None:
            self.reset_view()
            return

        if run_diagnostics:
            self.refresh_view()
        else:
            self._refresh_audit()

    def refresh_view(self) -> None:
        if self._project is None:
            self.reset_view()
            return

        try:
            diagnostics = ProjectDiagnosticsService(
                self._project
            ).run()
        except Exception as exc:
            self.reset_view()
            self.health_card.value_label.setText("ERROR")
            self.diagnostics_table.setRowCount(1)
            self.diagnostics_table.setItem(
                0, 0, QTableWidgetItem("Diagnostics")
            )
            self.diagnostics_table.setItem(
                0, 1, QTableWidgetItem("ERROR")
            )
            self.diagnostics_table.setItem(
                0, 2, QTableWidgetItem("Failed")
            )
            self.diagnostics_table.setItem(
                0, 3, QTableWidgetItem(str(exc))
            )
            return

        self._populate_diagnostics(diagnostics)
        self._refresh_audit()

    def _populate_diagnostics(
        self,
        diagnostics: ProjectDiagnostics,
    ) -> None:
        health_text = (
            "HEALTHY"
            if diagnostics.error_count == 0
            else f"{diagnostics.error_count} ERROR"
        )
        self.health_card.value_label.setText(health_text)

        validation_total = (
            diagnostics.system_errors
            + diagnostics.needs_review
            + diagnostics.workflow_warnings
        )
        self.validation_card.value_label.setText(str(validation_total))
        self.output_card.value_label.setText(
            str(diagnostics.output_warnings)
        )
        self.backup_card.value_label.setText(
            str(diagnostics.backup_count)
        )
        self.audit_card.value_label.setText(
            str(diagnostics.audit_count)
        )

        self.diagnostics_table.setRowCount(len(diagnostics.checks))
        for row_index, check in enumerate(diagnostics.checks):
            status_text = {
                STATUS_OK: "✓ OK",
                STATUS_WARNING: "⚠ Warning",
                STATUS_ERROR: "✕ Error",
                STATUS_INFO: "Info",
            }.get(check.status, check.status)

            values = [
                check.label,
                status_text,
                check.value,
                check.detail,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(check.detail or value)
                self.diagnostics_table.setItem(
                    row_index,
                    column,
                    item,
                )

    def _refresh_audit(self) -> None:
        if self._project is None:
            self.audit_table.setRowCount(0)
            return

        try:
            entries = AuditService(
                self._project.database
            ).recent(50)
        except Exception:
            entries = []

        self.audit_table.setRowCount(len(entries))
        for row_index, entry in enumerate(entries):
            values = [
                entry.created_at,
                entry.event_type,
                entry.action,
                entry.summary,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(entry.summary)
                self.audit_table.setItem(
                    row_index,
                    column,
                    item,
                )

    def reset_view(self) -> None:
        for card, value in (
            (self.health_card, "—"),
            (self.validation_card, "0"),
            (self.output_card, "0"),
            (self.backup_card, "0"),
            (self.audit_card, "0"),
        ):
            card.value_label.setText(value)
        self.diagnostics_table.setRowCount(0)
        self.audit_table.setRowCount(0)
