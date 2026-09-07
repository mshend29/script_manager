from __future__ import annotations

from pathlib import Path

import pytest

import core.project_manager as project_manager_module
from core.project import Project
from core.project_manager import ProjectManager
from core.project_settings import ProjectSettings


def _settings(name: str = "Project Baru", code: str = "PB01") -> ProjectSettings:
    return ProjectSettings(
        project_name=name,
        project_code=code,
        client_name="Client",
        start_date="2026-09-06",
    )


def _sidecars(project_file: Path) -> tuple[Path, Path, Path]:
    return (
        Path(str(project_file) + "-journal"),
        Path(str(project_file) + "-wal"),
        Path(str(project_file) + "-shm"),
    )


def test_transaction_rolls_back_project_sidecars_runtime_and_restores_previous(
    tmp_path,
    monkeypatch,
):
    runtime_root = tmp_path / "runtime"
    monkeypatch.setattr(
        project_manager_module,
        "project_runtime_root",
        lambda project_id: runtime_root / project_id,
    )

    manager = ProjectManager()
    previous = Project(
        file_path=tmp_path / "previous.smproj",
        settings=_settings("Existing", "EX01"),
        project_id="existing-project",
    )
    manager.current = previous

    created_path: Path | None = None
    created_runtime: Path | None = None

    def fail_after_create(project: Project) -> None:
        nonlocal created_path, created_runtime
        created_path = project.project_file
        created_runtime = runtime_root / project.project_id
        created_runtime.mkdir(parents=True, exist_ok=True)
        (created_runtime / "temp.txt").write_text("temporary", encoding="utf-8")
        for sidecar in _sidecars(project.project_file):
            sidecar.write_text("sqlite-sidecar", encoding="utf-8")
        raise RuntimeError("post-create failure")

    with pytest.raises(RuntimeError, match="post-create failure"):
        manager.create_transactional(
            _settings(),
            tmp_path,
            after_create=fail_after_create,
        )

    assert created_path is not None
    assert created_runtime is not None
    assert created_path.exists() is False
    assert all(path.exists() is False for path in _sidecars(created_path))
    assert created_runtime.exists() is False
    assert manager.current is previous


def test_transaction_success_keeps_project_and_current(tmp_path):
    manager = ProjectManager()
    stages: list[str] = []

    project = manager.create_transactional(
        _settings(),
        tmp_path,
        after_create=lambda created: stages.append(created.project_id),
    )

    assert project.project_file.is_file()
    assert manager.current is project
    assert stages == [project.project_id]


def test_create_save_failure_uses_same_cleanup_path(tmp_path, monkeypatch):
    runtime_root = tmp_path / "runtime"
    monkeypatch.setattr(
        project_manager_module,
        "project_runtime_root",
        lambda project_id: runtime_root / project_id,
    )

    original_save = Project.save
    captured: dict[str, object] = {}

    def broken_save(project: Project) -> None:
        project.project_file.parent.mkdir(parents=True, exist_ok=True)
        project.project_file.write_text("partial", encoding="utf-8")
        for sidecar in _sidecars(project.project_file):
            sidecar.write_text("partial", encoding="utf-8")
        runtime = runtime_root / project.project_id
        runtime.mkdir(parents=True, exist_ok=True)
        (runtime / "temp.txt").write_text("partial", encoding="utf-8")
        captured["project_file"] = project.project_file
        captured["runtime"] = runtime
        raise RuntimeError("save failed")

    monkeypatch.setattr(Project, "save", broken_save)
    manager = ProjectManager()

    with pytest.raises(RuntimeError, match="save failed"):
        manager.create(_settings(), tmp_path)

    project_file = captured["project_file"]
    runtime = captured["runtime"]
    assert isinstance(project_file, Path)
    assert isinstance(runtime, Path)
    assert project_file.exists() is False
    assert all(path.exists() is False for path in _sidecars(project_file))
    assert runtime.exists() is False
    assert manager.current is None

    # Keep the monkeypatch target explicit for readability; pytest restores it
    # automatically after the test.
    assert original_save is not broken_save
