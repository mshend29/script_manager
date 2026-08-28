from __future__ import annotations

import sqlite3

import pytest

from core.database import Database


def test_database_context_manager_closes_connection_after_exit(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()

    with database.connect() as connection:
        connection.execute("SELECT 1").fetchone()

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")


def test_database_context_manager_rolls_back_and_closes_on_error(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()

    with pytest.raises(RuntimeError, match="boom"):
        with database.connect() as connection:
            connection.execute(
                """
                INSERT INTO app_meta(key, value)
                VALUES('temporary_test_key', '1')
                """
            )
            raise RuntimeError("boom")

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")

    with database.connect() as verify:
        row = verify.execute(
            """
            SELECT value
            FROM app_meta
            WHERE key = 'temporary_test_key'
            """
        ).fetchone()

    assert row is None


def test_closed_database_context_does_not_block_project_folder_rename(tmp_path):
    root = tmp_path / "Legacy"
    root.mkdir()

    database = Database(root / "project.db")
    database.initialize()

    with database.connect() as connection:
        connection.execute(
            "SELECT value FROM app_meta WHERE key = 'schema_version'"
        ).fetchone()

    target = tmp_path / "Legacy.drsp"
    root.rename(target)

    assert not root.exists()
    assert target.is_dir()
    assert (target / "project.db").is_file()
