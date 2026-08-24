import hashlib

import pytest

from core.database import Database, DatabaseCompatibilityError, SCHEMA_VERSION
from core.project import Project
from core.project_manager import ProjectError, ProjectManager
from core.project_settings import ProjectSettings


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _set_schema_version(database: Database, value: str) -> None:
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO app_meta(key, value)
            VALUES('schema_version', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (value,),
        )


def test_database_initialize_rejects_future_schema_without_modifying_file(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    future_version = str(SCHEMA_VERSION + 996)
    _set_schema_version(database, future_version)

    before_hash = _sha256(database.path)

    with pytest.raises(DatabaseCompatibilityError, match=future_version):
        database.initialize()

    after_hash = _sha256(database.path)
    assert after_hash == before_hash

    with database.connect() as connection:
        row = connection.execute(
            "SELECT value FROM app_meta WHERE key = 'schema_version'"
        ).fetchone()
    assert str(row["value"]) == future_version


def test_project_open_rejects_future_schema_without_rewriting_database(tmp_path):
    project = Project(
        root=tmp_path / "future-project",
        settings=ProjectSettings(project_name="Future Project"),
    )
    project.ensure_structure()
    project.database.initialize()
    project.save()

    future_version = "999"
    _set_schema_version(project.database, future_version)
    before_hash = _sha256(project.database_file)

    manager = ProjectManager()
    with pytest.raises(ProjectError, match="schema 999"):
        manager.open(project.project_file)

    assert manager.current is None
    assert _sha256(project.database_file) == before_hash

    with project.database.connect() as connection:
        row = connection.execute(
            "SELECT value FROM app_meta WHERE key = 'schema_version'"
        ).fetchone()
    assert str(row["value"]) == future_version
