from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_contextual_header_exposes_one_sync_source_action_only() -> None:
    header = (ROOT / "widgets" / "page_header.py").read_text(encoding="utf-8")

    assert header.count('HeaderAction("source.sync", "Sync Source"') == 1

    for removed in (
        "source.import",
        "source.refresh",
        "script.refresh",
        "dialog.refresh",
        "tracking.refresh",
        "data.refresh",
        "Import Source",
        "Refresh Data",
        "Refresh View",
    ):
        assert removed not in header


def test_main_window_routes_f5_and_header_to_same_sync_source_method() -> None:
    main = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")

    assert '("F5", self.sync_source)' in main
    assert '"source.sync": self.sync_source' in main
    assert "def sync_source(self)" in main
    assert 'self._run_source_sync("Sync Source")' in main

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

    assert "Sync Source" in getting_started
    assert "initial sync" in getting_started
    assert "incremental sync" in getting_started

    assert "Sync Source" in user_guide
    guide_lower = user_guide.casefold()
    assert "initial sync" in guide_lower
    assert "incremental sync" in guide_lower
    assert "tidak perlu menjalankan Refresh View manual" in user_guide

    assert "<td>Sync Source</td>" in shortcuts
    assert "initial sync dan incremental sync" in shortcuts

    assert "Import Source" not in getting_started
    assert "Refresh Data" not in getting_started
    assert "Import Source" not in shortcuts
    assert "Refresh Data" not in shortcuts
