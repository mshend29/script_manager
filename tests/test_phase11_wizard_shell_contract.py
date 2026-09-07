from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_phase11_new_project_uses_five_step_wizard_shell():
    source = _read("dialogs/new_project_dialog.py")

    for title in (
        "Inisialisasi Proyek",
        "Sumber Naskah",
        "Sumber Audio",
        "Folder & Tautan",
        "Buat Proyek",
    ):
        assert title in source

    assert "WizardMilestoneRail" in source
    assert "QStackedWidget" in source
    assert 'QPushButton("?")' in source
    assert 'QPushButton("< Kembali")' in source
    assert 'QPushButton("Berikutnya >")' in source
    assert 'QPushButton("Buat Proyek")' in source
    assert 'QPushButton("Batal")' in source
    assert "set_step_state(" in source
    assert "_can_advance_current_step" in source
    assert "self.page_stack.setCurrentIndex(index)" in source
    assert "self.setMinimumSize(760, 560)" in source


def test_phase11_milestone_state_is_not_color_only():
    source = _read("widgets/wizard_milestone_rail.py")

    assert 'PENDING = "pending"' in source
    assert 'VALID = "valid"' in source
    assert 'WARNING = "warning"' in source
    assert 'ERROR = "error"' in source
    assert '"○"' in source
    assert '"✓"' in source
    assert '"⚠"' in source
    assert '"✕"' in source
    assert 'symbol = "●"' in source
