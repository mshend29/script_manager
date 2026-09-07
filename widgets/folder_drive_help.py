from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)


FOLDER_DRIVE_HELP_TEXT = """Folder filesystem
Folder filesystem adalah lokasi yang dapat dibaca/ditulis langsung oleh aplikasi melalui Windows, drive lokal, mapped drive, network drive, atau Google Drive Desktop.
Contoh: G:\\My Drive\\Client\\AA23\\Scripts

Google Drive Desktop
Google Drive Desktop membuat file Drive tersedia sebagai filesystem path. Drive/folder tersebut harus tersedia dan tersinkron atau dapat diakses di komputer agar aplikasi dapat membaca atau menulis file.

Tautan browser
Tautan browser adalah URL untuk membuka lokasi Drive di browser dan hanya disimpan sebagai shortcut/referensi.
Contoh: https://drive.google.com/drive/folders/...
URL browser tidak digunakan aplikasi untuk membaca file.

Penting
Jangan masukkan URL browser ke field Folder. Gunakan filesystem path pada field Folder dan masukkan URL hanya pada field Tautan Drive.
"""


class FolderDriveHelpDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bantuan Folder & Google Drive")
        self.setModal(True)
        self.resize(620, 470)
        self.setMinimumSize(520, 400)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        title = QLabel("Folder & Google Drive")
        title.setObjectName("SectionTitle")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        root.addWidget(title)

        intro = QLabel(
            "Aplikasi membedakan folder filesystem yang dipakai untuk membaca/menulis "
            "file dengan tautan browser yang hanya menjadi shortcut."
        )
        intro.setObjectName("PageSubtitle")
        intro.setWordWrap(True)
        root.addWidget(intro)

        root.addWidget(
            self._help_group(
                "Folder filesystem",
                (
                    "Folder filesystem adalah lokasi yang dapat dibaca/ditulis langsung "
                    "oleh aplikasi melalui Windows, drive lokal, mapped/network drive, "
                    "atau Google Drive Desktop.\n\n"
                    "Contoh:\nG:\\My Drive\\Client\\AA23\\Scripts"
                ),
            )
        )
        root.addWidget(
            self._help_group(
                "Google Drive Desktop",
                (
                    "Google Drive Desktop membuat file Drive tersedia sebagai filesystem "
                    "path. Drive atau folder tersebut harus tersedia dan tersinkron atau "
                    "dapat diakses di komputer agar aplikasi dapat membaca/menulis file."
                ),
            )
        )
        root.addWidget(
            self._help_group(
                "Tautan browser",
                (
                    "Tautan browser adalah URL untuk membuka lokasi Drive di browser dan "
                    "hanya disimpan sebagai shortcut/referensi.\n\n"
                    "Contoh:\nhttps://drive.google.com/drive/folders/...\n\n"
                    "URL browser tidak digunakan aplikasi untuk membaca file. Jangan "
                    "masukkan URL browser ke field Folder; gunakan field Tautan Drive."
                ),
            )
        )

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @staticmethod
    def _help_group(title: str, text: str) -> QGroupBox:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(label)
        return box


def show_folder_drive_help(parent: QWidget | None = None) -> None:
    dialog = FolderDriveHelpDialog(parent)
    dialog.exec()
