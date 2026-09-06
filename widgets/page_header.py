from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
)


@dataclass(frozen=True)
class HeaderAction:
    action_id: str
    label: str
    primary: bool = False


@dataclass(frozen=True)
class PageHeaderSpec:
    title: str
    subtitle: str
    actions: tuple[HeaderAction, ...] = ()
    overflow: tuple[HeaderAction, ...] = ()


PAGE_HEADER_SPECS = {
    "PROJECT": PageHeaderSpec(
        title='Proyek',
        subtitle='Ringkasan proyek, sinkronisasi sumber, dan status produksi',
        actions=(
            HeaderAction("source.sync", 'Sinkronkan Sumber', primary=True),
            HeaderAction("project.open", 'Buka Proyek'),
            HeaderAction("project.settings", 'Pengaturan Proyek'),
        ),
        overflow=(
            HeaderAction("project.new", 'Proyek Baru'),
            HeaderAction("project.open_recent", 'Buka Terbaru'),
            HeaderAction("project.save", 'Simpan'),
            HeaderAction("project.save_as", 'Simpan Sebagai'),
            HeaderAction("project.duplicate", "Duplicate"),
            HeaderAction("project.recover", 'Pulihkan'),
            HeaderAction("client.drive", 'Buka Drive Klien'),
            HeaderAction("project.close", 'Tutup Proyek'),
        ),
    ),
    "SCRIPT": PageHeaderSpec(
        title='Naskah',
        subtitle='Sumber dialog yang diimpor dan ringkasan episode',
        actions=(
            HeaderAction("script.search", 'Cari'),
        ),
    ),
    "DIALOG": PageHeaderSpec(
        title="Dialog",
        subtitle='Workspace rekaman untuk meninjau dan menyelesaikan dialog',
        actions=(
            HeaderAction("dialog.open_source", 'Buka File Sumber', primary=True),
            HeaderAction("dialog.check_all", "Check All"),
        ),
        overflow=(
            HeaderAction("dialog.uncheck_all", "Uncheck All"),
        ),
    ),
    "TRACKING": PageHeaderSpec(
        title="Tracking",
        subtitle='Matriks status episode ringkas untuk memantau progres produksi',
        actions=(
            HeaderAction("tracking.open_drive", 'Buka Drive Klien'),
        ),
    ),
    "DATA": PageHeaderSpec(
        title="Data",
        subtitle='Tokoh, talent, pemetaan, dan validasi proyek',
        actions=(
            HeaderAction("data.validate", "Validate", primary=True),
            HeaderAction("data.backup", 'Cadangkan'),
        ),
        overflow=(
            HeaderAction("data.characters", 'Tokoh'),
            HeaderAction("data.talents", 'Talent'),
            HeaderAction("data.cast", 'Pemetaan Tokoh & Talent'),
            HeaderAction("data.rebuild", 'Bangun Ulang Indeks'),
        ),
    ),
    "TOOLS": PageHeaderSpec(
        title='Peralatan',
        subtitle='Diagnostik, cadangan, folder proyek, dan pemeliharaan',
        actions=(
            HeaderAction("tools.diagnostics", 'Jalankan Diagnostik', primary=True),
            HeaderAction("tools.backup", 'Buat Cadangan'),
        ),
        overflow=(
            HeaderAction("tools.audit", 'Riwayat Audit'),
            HeaderAction("tools.restore_backup", 'Pulihkan Cadangan'),
            HeaderAction("tools.open_project_folder", 'Buka Folder Proyek'),
            HeaderAction("tools.open_source_folder", 'Buka Folder Sumber'),
            HeaderAction("tools.open_output_folder", 'Buka Stem / Export'),
            HeaderAction("tools.open_delivery_folder", 'Buka Setoran'),
            HeaderAction("tools.open_backups", 'Buka Cadangan'),
            HeaderAction("tools.open_logs", 'Buka Log'),
            HeaderAction("tools.open_main_drive", 'Buka Drive Utama'),
            HeaderAction("tools.open_material_drive", 'Buka Drive Material'),
            HeaderAction("tools.open_delivery_drive", 'Buka Drive Setoran'),
        ),
    ),
    "HELP": PageHeaderSpec(
        title='Bantuan',
        subtitle='Panduan, pintasan, pembaruan, dan dukungan',
        actions=(
            HeaderAction("help.user_guide", 'Panduan Pengguna', primary=True),
            HeaderAction("help.check_updates", 'Periksa Pembaruan'),
        ),
        overflow=(
            HeaderAction("help.getting_started", 'Mulai'),
            HeaderAction("help.keyboard_shortcuts", 'Pintasan Keyboard'),
            HeaderAction("help.report_problem", 'Laporkan Masalah'),
            HeaderAction("help.about", 'Tentang Script Manager'),
        ),
    ),
}


class PageHeader(QFrame):
    action_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PageHeader")
        self.setFixedHeight(78)

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 10, 16, 10)
        root.setSpacing(10)

        title_area = QVBoxLayout()
        title_area.setContentsMargins(0, 0, 0, 0)
        title_area.setSpacing(1)

        self.title_label = QLabel('Proyek')
        self.title_label.setObjectName("HeaderTitle")
        title_area.addWidget(self.title_label)

        self.subtitle_label = QLabel("")
        self.subtitle_label.setObjectName("HeaderSubtitle")
        title_area.addWidget(self.subtitle_label)

        root.addLayout(title_area, 1)

        self.actions_layout = QHBoxLayout()
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(8)
        root.addLayout(self.actions_layout)

        self.overflow_button = QToolButton()
        self.overflow_button.setText("•••")
        self.overflow_button.setProperty("headerOverflow", True)
        self.overflow_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.overflow_button.setFixedWidth(42)
        self.actions_layout.addWidget(self.overflow_button)

    def set_page(self, page_name: str) -> None:
        spec = PAGE_HEADER_SPECS.get(page_name)
        if spec is None:
            return

        self.title_label.setText(spec.title)
        self.subtitle_label.setText(spec.subtitle)

        while self.actions_layout.count() > 1:
            item = self.actions_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        for action in spec.actions:
            button = QPushButton(action.label)
            if action.primary:
                button.setProperty("headerPrimary", True)
            else:
                button.setProperty("headerSecondary", True)
            button.clicked.connect(
                lambda checked=False, action_id=action.action_id:
                    self.action_requested.emit(action_id)
            )
            self.actions_layout.insertWidget(
                self.actions_layout.count() - 1,
                button,
            )

        menu = QMenu(self.overflow_button)
        for action in spec.overflow:
            menu_action = menu.addAction(action.label)
            menu_action.triggered.connect(
                lambda checked=False, action_id=action.action_id:
                    self.action_requested.emit(action_id)
            )
        self.overflow_button.setMenu(menu)
        self.overflow_button.setVisible(bool(spec.overflow))
