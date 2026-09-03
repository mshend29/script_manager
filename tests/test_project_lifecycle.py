from __future__ import annotations

import sqlite3
from pathlib import Path

from core.file_association import (
    WINDOWS_FILE_TYPE,
    WINDOWS_PROG_ID,
    windows_file_association_spec,
)
from core.project_manager import ProjectManager
from core.project_settings import ProjectSettings
from core.recent_projects import RecentProjectsStore


def _insert_talent(project, name: str) -> None:
    with project.database.connect() as connection:
        connection.execute(
            """
            INSERT INTO talents(name, normalized_name, is_active)
            VALUES(?, ?, 1)
            """,
            (name, name.casefold()),
        )


def _talents(project) -> list[str]:
    with project.database.connect() as connection:
        return [
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM talents ORDER BY id"
            ).fetchall()
        ]


def _snapshot(source: Path, target: Path) -> None:
    src = sqlite3.connect(source)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def test_save_as_preserves_project_identity_and_switches_current_file(tmp_path):
    manager = ProjectManager()
    original = manager.create(
        ProjectSettings(project_name="AA23"),
        tmp_path,
    )
    _insert_talent(original, "Brama")
    original_id = original.project_id

    saved = manager.save_as(tmp_path / "AA23 Final.smproj")

    assert saved.project_id == original_id
    assert saved.project_file == tmp_path / "AA23 Final.smproj"
    assert manager.current is saved
    assert original.project_file.is_file()
    assert _talents(saved) == ["Brama"]


def test_duplicate_creates_new_identity_and_keeps_project_data(tmp_path):
    manager = ProjectManager()
    original = manager.create(
        ProjectSettings(project_name="AA23"),
        tmp_path,
    )
    _insert_talent(original, "Brama")
    original_id = original.project_id

    duplicated = manager.duplicate(tmp_path / "AA23 Copy.smproj")

    assert duplicated.project_id != original_id
    assert duplicated.project_file == tmp_path / "AA23 Copy.smproj"
    assert manager.current is duplicated
    assert _talents(duplicated) == ["Brama"]


def test_recover_from_snapshot_restores_data_to_new_smproj(tmp_path):
    manager = ProjectManager()
    original = manager.create(
        ProjectSettings(project_name="AA23"),
        tmp_path,
    )
    _insert_talent(original, "Before")
    original.save()

    backup = tmp_path / "AA23 Snapshot.smproj"
    _snapshot(original.project_file, backup)

    _insert_talent(original, "After")
    original.save()

    recovered = manager.recover_from_backup(
        backup,
        tmp_path / "AA23 Recovered.smproj",
    )

    assert recovered.project_id == original.project_id
    assert recovered.project_file.name == "AA23 Recovered.smproj"
    assert _talents(recovered) == ["Before"]



def test_recovery_rejects_backup_from_different_project(tmp_path):
    manager = ProjectManager()
    first = manager.create(
        ProjectSettings(project_name="AA23"),
        tmp_path,
    )
    first.save()
    backup = tmp_path / "AA23 Snapshot.smproj"
    _snapshot(first.project_file, backup)

    manager.create(
        ProjectSettings(project_name="BB01"),
        tmp_path,
    )

    import pytest

    with pytest.raises(Exception, match="project yang berbeda"):
        manager.recover_from_backup(
            backup,
            tmp_path / "Wrong Recovery.smproj",
            expected_project_id="different-project-id",
        )


def test_recent_projects_tracks_latest_path_for_same_identity(tmp_path):
    store = RecentProjectsStore(
        tmp_path / "recent_projects.json",
        limit=3,
    )

    store.add(
        project_id="project-1",
        project_name="AA23",
        file_path=tmp_path / "AA23.smproj",
    )
    store.add(
        project_id="project-1",
        project_name="AA23",
        file_path=tmp_path / "AA23 Final.smproj",
    )
    store.add(
        project_id="project-2",
        project_name="BB01",
        file_path=tmp_path / "BB01.smproj",
    )

    rows = store.list()

    assert [row.project_id for row in rows] == [
        "project-2",
        "project-1",
    ]
    assert rows[1].file_path.endswith("AA23 Final.smproj")


def test_windows_file_association_spec_uses_smproj_open_command(tmp_path):
    executable = tmp_path / "ScriptManager.exe"
    spec = windows_file_association_spec(executable)

    assert spec.extension == ".smproj"
    assert spec.prog_id == WINDOWS_PROG_ID
    assert spec.file_type == WINDOWS_FILE_TYPE
    assert spec.open_command.endswith('" "%1"')
    assert "ScriptManager.exe" in spec.open_command


def test_project_lifecycle_actions_are_wired_to_ui():
    root = Path(__file__).resolve().parents[1]
    main = (root / "app" / "main_window.py").read_text(encoding="utf-8")
    header = (root / "widgets" / "page_header.py").read_text(encoding="utf-8")
    page = (root / "pages" / "project_page.py").read_text(encoding="utf-8")

    for action in (
        "project.open_recent",
        "project.save_as",
        "project.duplicate",
        "project.recover",
    ):
        assert action in main
        assert action in header

    assert "Open Recent" in page
    assert "Recover Project" in page
