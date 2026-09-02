from __future__ import annotations

from pathlib import Path

from core.database import Database
from pages.data_workspace_controller import DataWorkspaceController


ROOT = Path(__file__).resolve().parents[1]


def test_data_workspace_controller_binds_service_graph(tmp_path) -> None:
    database = Database(tmp_path / "project.db")
    database.initialize()

    controller = DataWorkspaceController(database)

    assert controller.is_bound is True
    assert controller.database is database
    assert controller.data is not None
    assert controller.review is not None
    assert controller.validation is not None

    overview = controller.get_overview()
    assert overview.active_sources == 0
    assert overview.active_dialogues == 0
    assert controller.get_review_rows().unresolved == ()
    assert controller.get_review_rows().reviewed == ()
    assert controller.get_talent_options() == []


def test_data_workspace_controller_unbind_resets_service_graph(tmp_path) -> None:
    database = Database(tmp_path / "project.db")
    database.initialize()
    controller = DataWorkspaceController(database)

    controller.bind_database(None)

    assert controller.is_bound is False
    assert controller.database is None
    assert controller.data is None
    assert controller.review is None
    assert controller.validation is None
    assert controller.validate() == []


def test_data_page_does_not_construct_domain_services_directly() -> None:
    source = (ROOT / "pages" / "data_page.py").read_text(
        encoding="utf-8"
    )

    assert "DataWorkspaceController()" in source
    assert "self._controller.bind_database(database)" in source

    for forbidden in (
        "DataService(",
        "ReviewService(",
        "ValidationService(",
        "self._service",
        "self._review_service",
        "self._validation_service",
    ):
        assert forbidden not in source


def test_controller_owns_data_domain_mutation_entrypoints() -> None:
    source = (
        ROOT / "pages" / "data_workspace_controller.py"
    ).read_text(encoding="utf-8")

    for method in (
        "mark_non_dialogue",
        "restore_to_review",
        "add_missing_character",
        "add_talent_and_lock",
        "set_locked_mapping",
        "unlock_mapping",
        "backup_database",
        "rebuild_indexes",
    ):
        assert f"def {method}(" in source
