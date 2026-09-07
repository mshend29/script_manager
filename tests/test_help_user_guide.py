from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_user_guide_covers_current_application_areas():
    guide_file = ROOT / "resources" / "help" / "user_guide.html"
    assert guide_file.is_file()

    content = guide_file.read_text(encoding="utf-8")

    for expected in (
        "Panduan Pengguna",
        ".smproj",
        "Pengaturan Proyek",
        "Sinkronkan Sumber",
        "NASKAH",
        "DIALOG",
        "TRACKING",
        "DELIVERY",
        "DATA",
        "Peralatan &amp; Pemeliharaan",
        "Tokoh Alias",
        "Kondisi Output",
        "Pulihkan Cadangan",
        "Pulihkan Proyek",
    ):
        assert expected in content


def test_user_guide_documents_phase11_project_setup_and_source_safety():
    content = (
        ROOT / "resources" / "help" / "user_guide.html"
    ).read_text(encoding="utf-8")

    for expected in (
        "Membuat Proyek Baru",
        "KODE - NAMA PROYEK.smproj",
        "Source Preflight",
        "Initial Source Sync",
        "Proyek</b></td>",
        "Sumber Naskah</b></td>",
        "Audio &amp; Setoran</b></td>",
        "Tautan Drive</b></td>",
        "Google Drive Desktop",
        "Mapped drive",
        "UNC / network path",
        "Kapitalisasi tidak membedakan pola",
        "Sumber Direvisi",
        "Troubleshooting",
        "FAQ",
    ):
        assert expected in content


def test_user_guide_has_documentation_navigation_anchors():
    content = (
        ROOT / "resources" / "help" / "user_guide.html"
    ).read_text(encoding="utf-8")

    for anchor in (
        "panduan",
        "proyek-baru",
        "pengaturan-proyek",
        "nama-file-sumber",
        "preflight",
        "sinkronkan-sumber",
        "revisi-sumber",
        "naskah",
        "dialog",
        "tracking",
        "delivery",
        "data",
        "folder-drive",
        "backup-recovery",
        "troubleshooting",
        "faq",
    ):
        assert f'name="{anchor}"' in content

    assert "help://new-project" in content
    assert "help://source-sync" in content
    assert "help://troubleshooting" in content


def test_help_page_can_switch_between_getting_started_and_user_guide():
    page = (ROOT / "pages" / "help_page.py").read_text(encoding="utf-8")

    assert "USER_GUIDE_FILE" in page
    assert 'QPushButton("Panduan Pengguna")' in page
    assert "def show_user_guide" in page
    assert "def _set_active_button" in page
    assert 'button.setProperty("primary", is_active)' in page
    assert 'button.setProperty("secondary", not is_active)' in page


def test_help_page_uses_structured_offline_documentation_workspace():
    page = (ROOT / "pages" / "help_page.py").read_text(encoding="utf-8")

    for expected in (
        "HelpArticle",
        "HELP_ARTICLES",
        "QTreeWidget",
        "HelpNavigationTree",
        "QLineEdit",
        "Cari panduan...",
        "HelpBreadcrumb",
        "def show_article",
        "def _filter_navigation",
        "def _show_previous_article",
        "def _show_next_article",
        'url.scheme() == "help"',
        "scrollToAnchor",
    ):
        assert expected in page

    assert "context.setVisible(False)" not in page


def test_user_guide_action_is_wired_to_header_and_main_window():
    header = (ROOT / "widgets" / "page_header.py").read_text(encoding="utf-8")
    main = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")

    assert 'HeaderAction("help.user_guide", "Panduan Pengguna", primary=True)' in header
    assert '"help.user_guide": self.open_user_guide' in main
    assert "def open_user_guide" in main
    assert "page.show_user_guide()" in main


def test_user_guide_stage_does_not_add_later_help_features():
    header = (ROOT / "widgets" / "page_header.py").read_text(encoding="utf-8")

    for action in (
        "help.shortcuts",
    ):
        assert action not in header
