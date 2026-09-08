from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.resource_paths import resource_path
from widgets.page_shell import PageShell


HELP_ROOT = resource_path("resources", "help")
GETTING_STARTED_FILE = HELP_ROOT / "getting_started.html"
USER_GUIDE_FILE = HELP_ROOT / "user_guide.html"
KEYBOARD_SHORTCUTS_FILE = HELP_ROOT / "keyboard_shortcuts.html"
REPORT_PROBLEM_FILE = HELP_ROOT / "report_problem.html"
ABOUT_FILE = HELP_ROOT / "about.html"


@dataclass(frozen=True)
class HelpArticle:
    key: str
    category: str
    title: str
    subtitle: str
    file_path: Path
    anchor: str = ""
    keywords: tuple[str, ...] = ()


HELP_ARTICLES: tuple[HelpArticle, ...] = (
    HelpArticle(
        "getting-started",
        "Mulai",
        "Mulai Cepat",
        "Alur pertama dari membuat proyek sampai siap bekerja.",
        GETTING_STARTED_FILE,
        keywords=("awal", "proyek baru", "wizard", "first run"),
    ),
    HelpArticle(
        "guide-overview",
        "Mulai",
        "Cara Membaca Panduan",
        "Peta kerja Script Manager dan urutan penggunaan yang disarankan.",
        USER_GUIDE_FILE,
        "panduan",
        ("alur kerja", "overview", "workflow"),
    ),
    HelpArticle(
        "new-project",
        "Proyek",
        "Membuat Proyek Baru",
        "Panduan wizard 5 langkah, preflight, dan pembuatan proyek.",
        USER_GUIDE_FILE,
        "proyek-baru",
        ("new project", "proyek baru", "smproj", "wizard"),
    ),
    HelpArticle(
        "project-files",
        "Proyek",
        "Buka, Simpan, Duplikat & Pulihkan",
        "Memahami lifecycle file .smproj tanpa kehilangan identitas proyek.",
        USER_GUIDE_FILE,
        "file-proyek",
        ("save as", "simpan sebagai", "duplicate", "recent", "recover"),
    ),
    HelpArticle(
        "project-settings",
        "Proyek",
        "Pengaturan Proyek",
        "Empat tab pengaturan dan efek perubahan konfigurasi.",
        USER_GUIDE_FILE,
        "pengaturan-proyek",
        ("settings", "proyek", "sumber", "audio", "drive"),
    ),
    HelpArticle(
        "source-naming",
        "Sumber Naskah",
        "Nama File & Nomor Episode",
        "Menentukan delimiter dan memastikan seluruh filename terbaca konsisten.",
        USER_GUIDE_FILE,
        "nama-file-sumber",
        ("delimiter", "episode", "xlsx", "xlsm", "filename", "case"),
    ),
    HelpArticle(
        "source-preflight",
        "Sumber Naskah",
        "Source Preflight",
        "Memeriksa workbook sebelum proyek atau database diubah.",
        USER_GUIDE_FILE,
        "preflight",
        ("inspect", "parse", "workbook", "corrupt", "validasi"),
    ),
    HelpArticle(
        "source-sync",
        "Sumber Naskah",
        "Sinkronkan Sumber",
        "Memasukkan naskah baru dan menerapkan revisi source secara aman.",
        USER_GUIDE_FILE,
        "sinkronkan-sumber",
        ("f5", "sync", "refresh", "apply", "preview", "backup"),
    ),
    HelpArticle(
        "source-revision",
        "Sumber Naskah",
        "Revisi Sumber & Sumber Direvisi",
        "Apa yang terjadi pada recording dan tracking ketika client merevisi naskah.",
        USER_GUIDE_FILE,
        "revisi-sumber",
        ("source revised", "revisi", "recording", "tracking", "lineage"),
    ),
    HelpArticle(
        "script-workspace",
        "Area Kerja",
        "NASKAH",
        "Membaca naskah hasil sinkronisasi per episode.",
        USER_GUIDE_FILE,
        "naskah",
        ("script", "episode", "cari", "search"),
    ),
    HelpArticle(
        "dialog-workspace",
        "Area Kerja",
        "DIALOG & Rekaman",
        "Filter talent/tokoh/episode dan pencatatan progres rekaman.",
        USER_GUIDE_FILE,
        "dialog",
        ("recorded", "checkbox", "talent", "tokoh", "source revised"),
    ),
    HelpArticle(
        "tracking-workspace",
        "Area Kerja",
        "TRACKING",
        "Membaca status episode dan memahami Ready/Stemmed/Delivered/Revision.",
        USER_GUIDE_FILE,
        "tracking",
        ("ready to stem", "stemmed", "delivered", "revision", "status"),
    ),
    HelpArticle(
        "delivery-workspace",
        "Area Kerja",
        "DELIVERY",
        "Memeriksa File Track, saran nama, dan Kondisi Output.",
        USER_GUIDE_FILE,
        "delivery",
        ("file track", "output", "setoran", "stem", "rename", "warning"),
    ),
    HelpArticle(
        "data-workspace",
        "Area Kerja",
        "DATA, Tokoh, Talent & Alias",
        "Meninjau pemetaan, data belum terselesaikan, sumber, dan validasi.",
        USER_GUIDE_FILE,
        "data",
        ("alias", "unresolved", "mapping", "talent", "character", "validasi"),
    ),
    HelpArticle(
        "folders-drive",
        "Folder & Tautan",
        "Filesystem vs Google Drive",
        "Membedakan folder lokal/Drive Desktop dari URL browser.",
        USER_GUIDE_FILE,
        "folder-drive",
        ("google drive", "mapped drive", "unc", "url", "folder"),
    ),
    HelpArticle(
        "maintenance",
        "Pemeliharaan",
        "Peralatan & Pemeliharaan",
        "Tindakan maintenance yang aman dan kapan menggunakannya.",
        USER_GUIDE_FILE,
        "peralatan",
        ("tools", "maintenance", "rebuild", "diagnostics"),
    ),
    HelpArticle(
        "backup-recovery",
        "Pemeliharaan",
        "Cadangan & Pemulihan",
        "Backup, Pulihkan Cadangan, dan Pulihkan Proyek.",
        USER_GUIDE_FILE,
        "backup-recovery",
        ("backup", "restore", "recover", "cadangan", "pemulihan"),
    ),
    HelpArticle(
        "recommended-workflow",
        "Panduan Praktis",
        "Alur Kerja Harian yang Disarankan",
        "Urutan kerja operator dari source masuk sampai setoran.",
        USER_GUIDE_FILE,
        "alur-rekomendasi",
        ("workflow", "harian", "operator", "setoran"),
    ),
    HelpArticle(
        "troubleshooting",
        "Panduan Praktis",
        "Troubleshooting",
        "Solusi untuk masalah yang paling sering ditemui operator.",
        USER_GUIDE_FILE,
        "troubleshooting",
        ("gagal", "error", "preflight", "offline", "warning", "sync"),
    ),
    HelpArticle(
        "faq",
        "Panduan Praktis",
        "FAQ",
        "Jawaban singkat untuk pertanyaan penggunaan yang umum.",
        USER_GUIDE_FILE,
        "faq",
        ("pertanyaan", "frequently asked", "faq"),
    ),
    HelpArticle(
        "keyboard-shortcuts",
        "Referensi",
        "Pintasan Keyboard",
        "Daftar shortcut yang aktif di Script Manager.",
        KEYBOARD_SHORTCUTS_FILE,
        keywords=("f1", "f5", "ctrl", "shortcut", "keyboard"),
    ),
)


class HelpPage(PageShell):
    action_requested = Signal(str)
    release_requested = Signal(str)
    issue_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        self._article_by_key = {article.key: article for article in HELP_ARTICLES}
        self._tree_items: dict[str, QTreeWidgetItem] = {}
        self._current_article_key = ""

        sidebar = self._build_documentation_sidebar()
        workspace = self._build_documentation_workspace()

        self._release_url = ""
        self._issue_url = ""
        self._problem_report_text = ""

        super().__init__(sidebar, workspace, parent)
        self.setObjectName("HelpDocumentationPage")
        self.show_getting_started()

    def _build_documentation_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("HelpSidebar")
        sidebar.setMinimumWidth(270)
        sidebar.setMaximumWidth(340)
        sidebar.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 18, 14, 18)
        layout.setSpacing(10)

        heading = QLabel("Panduan Script Manager")
        heading.setObjectName("HelpSidebarTitle")
        layout.addWidget(heading)

        description = QLabel(
            "Temukan langkah kerja berdasarkan tugas yang sedang dilakukan."
        )
        description.setObjectName("HelpSidebarDescription")
        description.setWordWrap(True)
        layout.addWidget(description)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("HelpSearch")
        self.search_edit.setPlaceholderText("Cari panduan...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setAccessibleName("Cari panduan Script Manager")
        self.search_edit.textChanged.connect(self._filter_navigation)
        layout.addWidget(self.search_edit)

        self.navigation_tree = QTreeWidget()
        self.navigation_tree.setObjectName("HelpNavigationTree")
        self.navigation_tree.setHeaderHidden(True)
        self.navigation_tree.setIndentation(14)
        self.navigation_tree.setRootIsDecorated(True)
        self.navigation_tree.setUniformRowHeights(False)
        self.navigation_tree.setAccessibleName("Daftar topik panduan")
        self.navigation_tree.itemActivated.connect(self._tree_item_activated)
        self.navigation_tree.itemClicked.connect(self._tree_item_activated)
        layout.addWidget(self.navigation_tree, 1)
        self._populate_navigation_tree()

        sidebar.setStyleSheet(
            """
            QFrame#HelpSidebar {
                background: #f7f8fa;
                border-right: 1px solid #dde2e8;
            }
            QLabel#HelpSidebarTitle {
                color: #18212b;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#HelpSidebarDescription {
                color: #64707d;
                font-size: 12px;
            }
            QLineEdit#HelpSearch {
                min-height: 32px;
                padding: 0 9px;
                border: 1px solid #cfd6de;
                border-radius: 6px;
                background: white;
            }
            QLineEdit#HelpSearch:focus {
                border: 1px solid #4b78c2;
            }
            QTreeWidget#HelpNavigationTree {
                background: transparent;
                border: 0;
                outline: 0;
                color: #27313c;
            }
            QTreeWidget#HelpNavigationTree::item {
                min-height: 27px;
                padding: 3px 5px;
                border-radius: 5px;
            }
            QTreeWidget#HelpNavigationTree::item:hover {
                background: #edf1f6;
            }
            QTreeWidget#HelpNavigationTree::item:selected {
                background: #e3ebf7;
                color: #244f8f;
            }
            """
        )
        return sidebar

    def _build_documentation_workspace(self) -> QWidget:
        workspace = QWidget()
        root = QVBoxLayout(workspace)
        root.setContentsMargins(30, 22, 30, 22)
        root.setSpacing(8)

        self.breadcrumb = QLabel("Bantuan › Mulai")
        self.breadcrumb.setObjectName("HelpBreadcrumb")
        root.addWidget(self.breadcrumb)

        self.title = QLabel("Mulai")
        self.title.setObjectName("PageTitle")
        root.addWidget(self.title)

        self.subtitle = QLabel(
            "Panduan offline untuk memulai alur kerja Script Manager."
        )
        self.subtitle.setObjectName("PageSubtitle")
        self.subtitle.setWordWrap(True)
        root.addWidget(self.subtitle)

        self.browser = QTextBrowser()
        self.browser.setObjectName("HelpBrowser")
        self.browser.setOpenExternalLinks(False)
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self._handle_browser_link)
        root.addWidget(self.browser, 1)

        navigation_bar = QHBoxLayout()
        navigation_bar.setContentsMargins(0, 4, 0, 0)
        self.previous_article_button = QPushButton("‹ Sebelumnya")
        self.previous_article_button.setProperty("secondary", True)
        self.previous_article_button.clicked.connect(self._show_previous_article)
        navigation_bar.addWidget(self.previous_article_button)
        navigation_bar.addStretch(1)
        self.next_article_button = QPushButton("Berikutnya ›")
        self.next_article_button.setProperty("secondary", True)
        self.next_article_button.clicked.connect(self._show_next_article)
        navigation_bar.addWidget(self.next_article_button)
        root.addLayout(navigation_bar)

        self.open_release_button = QPushButton("Buka Halaman Rilis")
        self.open_release_button.setProperty("primary", True)
        self.open_release_button.hide()
        self.open_release_button.clicked.connect(self._open_release_clicked)
        root.addWidget(self.open_release_button)

        self.open_issue_button = QPushButton("Buka GitHub Issue")
        self.open_issue_button.setProperty("primary", True)
        self.open_issue_button.hide()
        self.open_issue_button.clicked.connect(self._open_issue_clicked)
        root.addWidget(self.open_issue_button)

        self.copy_report_button = QPushButton("Salin Template Laporan")
        self.copy_report_button.setProperty("secondary", True)
        self.copy_report_button.hide()
        self.copy_report_button.clicked.connect(self._copy_report_clicked)
        root.addWidget(self.copy_report_button)

        workspace.setStyleSheet(
            """
            QLabel#HelpBreadcrumb {
                color: #77818c;
                font-size: 11px;
            }
            QTextBrowser#HelpBrowser {
                background: #ffffff;
                border: 0;
                padding: 4px 2px;
            }
            """
        )
        return workspace

    def _populate_navigation_tree(self) -> None:
        self.navigation_tree.clear()
        self._tree_items.clear()
        categories: dict[str, QTreeWidgetItem] = {}
        for article in HELP_ARTICLES:
            category_item = categories.get(article.category)
            if category_item is None:
                category_item = QTreeWidgetItem([article.category.upper()])
                category_item.setFlags(
                    category_item.flags() & ~Qt.ItemFlag.ItemIsSelectable
                )
                font = category_item.font(0)
                font.setBold(True)
                category_item.setFont(0, font)
                self.navigation_tree.addTopLevelItem(category_item)
                categories[article.category] = category_item
            item = QTreeWidgetItem([article.title])
            item.setData(0, Qt.ItemDataRole.UserRole, article.key)
            item.setToolTip(0, article.subtitle)
            category_item.addChild(item)
            self._tree_items[article.key] = item

        for index in range(self.navigation_tree.topLevelItemCount()):
            self.navigation_tree.topLevelItem(index).setExpanded(True)

    def _filter_navigation(self, text: str) -> None:
        query = str(text or "").strip().casefold()
        for index in range(self.navigation_tree.topLevelItemCount()):
            category_item = self.navigation_tree.topLevelItem(index)
            any_visible = False
            for child_index in range(category_item.childCount()):
                item = category_item.child(child_index)
                key = str(item.data(0, Qt.ItemDataRole.UserRole) or "")
                article = self._article_by_key.get(key)
                haystack = ""
                if article is not None:
                    haystack = " ".join(
                        (
                            article.category,
                            article.title,
                            article.subtitle,
                            *article.keywords,
                        )
                    ).casefold()
                visible = not query or query in haystack
                item.setHidden(not visible)
                any_visible = any_visible or visible
            category_item.setHidden(not any_visible)
            if query and any_visible:
                category_item.setExpanded(True)

    def _tree_item_activated(
        self,
        item: QTreeWidgetItem,
        _column: int,
    ) -> None:
        key = str(item.data(0, Qt.ItemDataRole.UserRole) or "")
        if key:
            self.show_article(key)

    def show_article(self, key: str) -> None:
        article = self._article_by_key.get(str(key or ""))
        if article is None:
            return

        self._hide_release_button()
        self._hide_problem_buttons()
        self._current_article_key = article.key
        self.breadcrumb.setText(
            f"Bantuan › {article.category} › {article.title}"
        )
        self.title.setText(article.title)
        self.subtitle.setText(article.subtitle)

        try:
            html = article.file_path.read_text(encoding="utf-8")
        except OSError as exc:
            self.browser.setPlainText(
                f"Halaman {article.title} tidak dapat dimuat.\n\n{exc}"
            )
            return

        self.browser.setHtml(html)
        if article.anchor:
            self.browser.scrollToAnchor(article.anchor)
        else:
            self.browser.verticalScrollBar().setValue(0)

        tree_item = self._tree_items.get(article.key)
        if tree_item is not None:
            self.navigation_tree.setCurrentItem(tree_item)
        self._update_article_navigation()

    def _update_article_navigation(self) -> None:
        keys = [article.key for article in HELP_ARTICLES]
        try:
            index = keys.index(self._current_article_key)
        except ValueError:
            self.previous_article_button.hide()
            self.next_article_button.hide()
            return
        self.previous_article_button.setVisible(index > 0)
        self.next_article_button.setVisible(index < len(keys) - 1)
        if index > 0:
            previous = self._article_by_key[keys[index - 1]]
            self.previous_article_button.setText(f"‹ {previous.title}")
        if index < len(keys) - 1:
            next_article = self._article_by_key[keys[index + 1]]
            self.next_article_button.setText(f"{next_article.title} ›")

    def _show_previous_article(self) -> None:
        keys = [article.key for article in HELP_ARTICLES]
        if self._current_article_key not in keys:
            return
        index = keys.index(self._current_article_key)
        if index > 0:
            self.show_article(keys[index - 1])

    def _show_next_article(self) -> None:
        keys = [article.key for article in HELP_ARTICLES]
        if self._current_article_key not in keys:
            return
        index = keys.index(self._current_article_key)
        if index < len(keys) - 1:
            self.show_article(keys[index + 1])

    def _handle_browser_link(self, url: QUrl) -> None:
        if url.scheme() == "help":
            key = url.host() or url.path().lstrip("/")
            self.show_article(key)
            return
        if not url.scheme() and url.fragment():
            self.browser.scrollToAnchor(url.fragment())

    def show_getting_started(self) -> None:
        self.show_article("getting-started")

    def show_user_guide(self) -> None:
        self.show_article("guide-overview")

    def show_keyboard_shortcuts(self) -> None:
        self.show_article("keyboard-shortcuts")

    def _prepare_dynamic_page(self, title: str, subtitle: str) -> None:
        self._current_article_key = ""
        self.navigation_tree.clearSelection()
        self.breadcrumb.setText(f"Bantuan › {title}")
        self.title.setText(title)
        self.subtitle.setText(subtitle)
        self.previous_article_button.hide()
        self.next_article_button.hide()

    def show_update_checking(self, current_version: str) -> None:
        self._hide_problem_buttons()
        self._hide_release_button()
        self._prepare_dynamic_page(
            "Periksa Pembaruan",
            f"Versi saat ini: {current_version}",
        )
        self.browser.setHtml(
            "<h2>Memeriksa pembaruan…</h2>"
            "<p>Script Manager sedang memeriksa GitHub Releases. "
            "Pemeriksaan berjalan di latar belakang sehingga UI tetap responsif.</p>"
        )

    def show_update_result(self, result) -> None:
        self._hide_problem_buttons()

        status = str(getattr(result, "status", ""))
        current = escape(str(getattr(result, "current_version", "") or ""))
        latest = escape(str(getattr(result, "latest_version", "") or ""))
        name = escape(str(getattr(result, "release_name", "") or ""))
        published = escape(str(getattr(result, "published_at", "") or ""))
        release_url = str(getattr(result, "release_url", "") or "").strip()

        self._prepare_dynamic_page(
            "Periksa Pembaruan",
            f"Versi saat ini: {current}",
        )

        if status.endswith("UPDATE_AVAILABLE"):
            heading = "Pembaruan tersedia"
            body = (
                f"<p>Versi terbaru: <b>{latest}</b></p>"
                f"<p>{name}</p>"
                "<p>Gunakan tombol <b>Buka Halaman Rilis</b> untuk "
                "membuka halaman rilis dan mengunduh pembaruan secara manual.</p>"
            )
            self._show_release_button(release_url)
        elif status.endswith("UP_TO_DATE"):
            heading = "Aplikasi sudah terbaru"
            body = (
                f"<p>Versi terbaru yang dipublikasikan adalah "
                f"<b>{latest}</b>.</p>"
            )
            self._show_release_button(release_url)
        else:
            heading = "Belum ada rilis yang dipublikasikan"
            body = (
                "<p>Repositori belum memiliki GitHub Release. "
                "Ini bukan masalah; pemeriksa pembaruan akan mulai "
                "membandingkan versi setelah rilis pertama dipublikasikan.</p>"
            )
            self._hide_release_button()

        if published:
            body += f"<p>Dipublikasikan: {published}</p>"
        self.browser.setHtml(f"<h2>{heading}</h2>{body}")

    def show_update_error(
        self,
        message: str,
        current_version: str,
    ) -> None:
        self._hide_problem_buttons()
        self._hide_release_button()
        self._prepare_dynamic_page(
            "Periksa Pembaruan",
            f"Versi saat ini: {escape(str(current_version))}",
        )
        self.browser.setHtml(
            "<h2>Pemeriksaan pembaruan gagal</h2>"
            f"<p>{escape(str(message))}</p>"
            "<p>Proyek dan data lokal tidak diubah.</p>"
        )

    def show_about(self, info) -> None:
        self._hide_release_button()
        self._hide_problem_buttons()
        self._prepare_dynamic_page(
            "Tentang Script Manager",
            "Informasi aplikasi, format proyek, skema database, dan runtime.",
        )

        try:
            html = ABOUT_FILE.read_text(encoding="utf-8")
        except OSError as exc:
            self.browser.setPlainText(
                "Halaman Tentang Script Manager tidak dapat dimuat.\n\n"
                f"{exc}"
            )
            return

        values = {
            "APP_NAME": getattr(info, "app_name", ""),
            "APP_VERSION": getattr(info, "app_version", ""),
            "PROJECT_EXTENSION": getattr(info, "project_extension", ""),
            "PROJECT_FORMAT_NAME": getattr(info, "project_format_name", ""),
            "PROJECT_FORMAT_ID": getattr(info, "project_format_id", ""),
            "PROJECT_FORMAT_VERSION": getattr(
                info,
                "project_format_version",
                "",
            ),
            "DATABASE_SCHEMA_VERSION": getattr(
                info,
                "database_schema_version",
                "",
            ),
            "PYTHON_VERSION": getattr(info, "python_version", ""),
            "PYSIDE6_VERSION": getattr(info, "pyside6_version", ""),
            "OS_NAME": getattr(info, "os_name", ""),
            "ARCHITECTURE": getattr(info, "architecture", ""),
            "REPOSITORY": getattr(info, "repository", ""),
        }
        for key, value in values.items():
            html = html.replace("{{" + key + "}}", escape(str(value)))
        self.browser.setHtml(html)
        self.browser.verticalScrollBar().setValue(0)

    def show_report_problem(self, report) -> None:
        self._hide_release_button()
        self._prepare_dynamic_page(
            "Laporkan Masalah",
            "Buat laporan bug dengan informasi lingkungan teknis "
            "yang aman untuk privasi.",
        )

        environment = dict(getattr(report, "environment", {}) or {})
        rows = "".join(
            "<tr>"
            f"<td>{escape(str(key))}</td>"
            f"<td>{escape(str(value))}</td>"
            "</tr>"
            for key, value in environment.items()
        )

        try:
            html = REPORT_PROBLEM_FILE.read_text(encoding="utf-8")
        except OSError as exc:
            self.browser.setPlainText(
                "Halaman Laporkan Masalah tidak dapat dimuat.\n\n"
                f"{exc}"
            )
            self._hide_problem_buttons()
            return

        self.browser.setHtml(html.replace("{{ENVIRONMENT_ROWS}}", rows))
        self.browser.verticalScrollBar().setValue(0)

        self._issue_url = str(getattr(report, "issue_url", "") or "").strip()
        self._problem_report_text = str(getattr(report, "body", "") or "")
        self.open_issue_button.setVisible(bool(self._issue_url))
        self.copy_report_button.setVisible(bool(self._problem_report_text))
        self.copy_report_button.setText("Salin Template Laporan")

    def _hide_problem_buttons(self) -> None:
        self._issue_url = ""
        self._problem_report_text = ""
        if hasattr(self, "open_issue_button"):
            self.open_issue_button.hide()
        if hasattr(self, "copy_report_button"):
            self.copy_report_button.hide()

    def _open_issue_clicked(self) -> None:
        if self._issue_url:
            self.issue_requested.emit(self._issue_url)

    def _copy_report_clicked(self) -> None:
        if not self._problem_report_text:
            return
        QApplication.clipboard().setText(self._problem_report_text)
        self.copy_report_button.setText("Tersalin")

    def _show_release_button(self, url: str) -> None:
        self._release_url = str(url or "").strip()
        self.open_release_button.setVisible(bool(self._release_url))

    def _hide_release_button(self) -> None:
        self._release_url = ""
        if hasattr(self, "open_release_button"):
            self.open_release_button.hide()

    def _open_release_clicked(self) -> None:
        if self._release_url:
            self.release_requested.emit(self._release_url)
