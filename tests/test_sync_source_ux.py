from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_data_menu_exposes_one_sync_source_action_only() -> None:
    main = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")

    assert main.count("Sinkronkan Sumber") >= 1
    assert "self.sync_source" in main
    assert "F5" in main

    for removed in (
        "source.import",
        "source.refresh",
        "script.refresh",
        "dialog.refresh",
        "tracking.refresh",
        "data.refresh",
        "Import Source",
        "Refresh Data",
    ):
        assert removed not in main


def test_main_window_routes_f5_and_data_menu_to_same_sync_source_method() -> None:
    main = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")

    assert "Sinkronkan Sumber" in main
    assert "self.sync_source" in main
    assert "F5" in main
    assert '"source.sync": self.sync_source' in main
    assert "def sync_source(self)" in main
    assert "self._run_source_sync" in main
    assert "Sinkronkan Sumber" in main

    for removed in (
        "def import_source",
        "def refresh_source",
        '"source.import"',
        '"source.refresh"',
        '"script.refresh"',
        '"dialog.refresh"',
        '"tracking.refresh"',
        '"data.refresh"',
    ):
        assert removed not in main


def test_help_documents_use_unified_sync_source_mental_model() -> None:
    getting_started = (
        ROOT / "resources" / "help" / "getting_started.html"
    ).read_text(encoding="utf-8")
    user_guide = (
        ROOT / "resources" / "help" / "user_guide.html"
    ).read_text(encoding="utf-8")
    shortcuts = (
        ROOT / "resources" / "help" / "keyboard_shortcuts.html"
    ).read_text(encoding="utf-8")

    assert "Sinkronkan Sumber" in getting_started
    assert "Sinkronisasi pertama" in getting_started
    assert "sinkronisasi lanjutan" in getting_started

    assert "Sinkronkan Sumber" in user_guide
    guide_lower = user_guide.casefold()
    assert "sinkronisasi pertama" in guide_lower
    assert "sinkronisasi lanjutan" in guide_lower
    assert "tidak perlu menjalankan Muat Ulang Tampilan secara manual" in user_guide

    assert "<td>Sinkronkan Sumber</td>" in shortcuts
    assert "sinkronisasi pertama dan sinkronisasi lanjutan" in shortcuts.casefold()

    assert "Import Source" not in getting_started
    assert "Refresh Data" not in getting_started
    assert "Import Source" not in shortcuts
    assert "Refresh Data" not in shortcuts
