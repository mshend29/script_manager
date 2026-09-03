from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PYSIDE_AVAILABLE = importlib.util.find_spec("PySide6") is not None

pytestmark = pytest.mark.skipif(
    not PYSIDE_AVAILABLE,
    reason="PySide6 is only installed in the Qt runtime CI job.",
)

if PYSIDE_AVAILABLE:
    from PySide6.QtWidgets import QApplication, QWidget

    from app.main_window import MainWindow
    from services.tracking_service import (
        NOT_STARTED,
        TrackingCharacterRow,
        TrackingChip,
    )
    from widgets.episode_chip import EpisodeChipButton


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


@pytest.mark.parametrize("width,height", ((1920, 1080), (1366, 768)))
def test_primary_desktop_sizes_keep_core_workspaces_reachable(
    qapp,
    width: int,
    height: int,
) -> None:
    window = MainWindow()
    window.resize(width, height)
    window.show()
    qapp.processEvents()

    assert window.workspace_nav.isVisible()
    assert window.workspace_nav.height() == 58
    assert window.page_stack.width() > 1000

    window.set_page("PROJECT")
    qapp.processEvents()
    project = window.pages["PROJECT"]
    project_scroll = project.findChild(QWidget, "ProjectScrollArea")
    assert project_scroll is not None
    assert project_scroll.width() > 800

    window.set_page("DIALOG")
    qapp.processEvents()
    dialog = window.pages["DIALOG"]
    assert dialog.table.width() > 650
    assert dialog.search_edit.isVisibleTo(window)
    assert dialog.copy_all_button.isVisibleTo(window)

    window.set_page("TRACKING")
    qapp.processEvents()
    tracking = window.pages["TRACKING"]
    assert tracking.scroll.width() > 650
    assert tracking.status_legend_widget.isVisibleTo(window)
    assert tracking.tracking_workspace_stack.isVisibleTo(window)

    window.close()
    qapp.processEvents()


def test_long_labels_do_not_expand_filter_controls_unbounded(qapp) -> None:
    window = MainWindow()
    window.resize(1366, 768)
    window.show()
    qapp.processEvents()

    very_long = (
        "TALENT DENGAN NAMA PRODUKSI YANG SANGAT PANJANG "
        "DAN TIDAK BOLEH MENDORONG KONTROL LAIN KELUAR LAYAR"
    )

    dialog = window.pages["DIALOG"]
    dialog.talent_combo.addItem(very_long, 999)
    assert dialog.talent_combo.sizeHint().width() < 260
    dialog.character_combo.addItem(very_long, 999)
    assert dialog.character_combo.sizeHint().width() < 260

    tracking = window.pages["TRACKING"]
    tracking.talent_combo.addItem(very_long, 999)
    assert tracking.talent_combo.sizeHint().width() < 260

    project = window.pages["PROJECT"]
    project.project_name.setText(very_long)
    assert project.project_name.wordWrap()
    assert project.project_name.minimumWidth() == 0

    window.close()
    qapp.processEvents()


def test_tracking_dense_episode_grid_stays_compact_at_lower_width(qapp) -> None:
    window = MainWindow()
    window.resize(1366, 768)
    window.show()
    window.set_page("TRACKING")
    qapp.processEvents()

    tracking = window.pages["TRACKING"]
    chips = [
        TrackingChip(
            episode_id=index,
            episode_number=index,
            character_id=1,
            character_name="TOKOH DENGAN NAMA PANJANG UNTUK UJI GRID",
            talent_id=1,
            talent_name="Talent",
            total_dialogues=5,
            recorded_dialogues=0,
            recording_status=NOT_STARTED,
            downstream_status="NOT_READY",
            downstream_note="",
            display_status=NOT_STARTED,
        )
        for index in range(1, 41)
    ]
    row = TrackingCharacterRow(
        character_id=1,
        character_name="TOKOH DENGAN NAMA PANJANG UNTUK UJI GRID",
        chips=chips,
    )

    tracking._reset_tracking_grid()
    tracking._add_character_row(1, row)
    qapp.processEvents()

    episode_buttons = tracking.rows_container.findChildren(EpisodeChipButton)
    assert len(episode_buttons) == 40
    assert all(button.width() == 46 for button in episode_buttons)
    assert all(button.height() == 34 for button in episode_buttons)
    assert tracking.scroll.horizontalScrollBarPolicy().name == (
        "ScrollBarAlwaysOff"
    )

    window.close()
    qapp.processEvents()


def test_keyboard_focus_reaches_primary_dialog_controls(qapp) -> None:
    window = MainWindow()
    window.resize(1366, 768)
    window.show()
    window.set_page("DIALOG")
    qapp.processEvents()

    dialog = window.pages["DIALOG"]
    dialog.search_edit.setFocus()
    qapp.processEvents()
    assert dialog.search_edit.hasFocus()

    dialog.table.setFocus()
    qapp.processEvents()
    assert dialog.table.hasFocus()

    window.close()
    qapp.processEvents()


@pytest.mark.parametrize("scale", ("1", "1.25", "1.5"))
def test_phase10_shell_constructs_at_common_windows_scale_factors(
    scale: str,
) -> None:
    probe = r"""
from PySide6.QtWidgets import QApplication
from app.main_window import MainWindow

app = QApplication([])
window = MainWindow()
window.resize(1366, 768)
window.show()
app.processEvents()

assert window.workspace_nav.height() == 58
for page_name in ("PROJECT", "DIALOG", "TRACKING"):
    window.set_page(page_name)
    app.processEvents()
    assert window.page_stack.currentWidget().width() > 1000
    assert window.workspace_nav.isVisible()

window.close()
app.processEvents()
"""

    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["QT_SCALE_FACTOR"] = scale

    result = subprocess.run(
        [sys.executable, "-c", probe],
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, (
        f"scale={scale}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
