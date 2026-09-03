from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_main_window_imports_production_page_variants_directly() -> None:
    source = (ROOT / "app" / "main_window.py").read_text(encoding="utf-8")

    assert "from pages.data_alias_page import AliasDataPage as DataPage" in source
    assert (
        "from pages.tracking_compact_page import "
        "CompactTrackingPage as TrackingPage"
    ) in source
    assert "from pages.data_page import DataPage" not in source
    assert "from pages.tracking_page import TrackingPage" not in source


def test_entrypoint_does_not_monkey_patch_main_window_page_classes() -> None:
    source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "from app.main_window import MainWindow" in source
    assert "main_window_module.DataPage" not in source
    assert "main_window_module.TrackingPage" not in source
    assert "AliasDataPage" not in source
    assert "CompactTrackingPage" not in source


def test_alias_data_page_routes_core_data_services_through_controller() -> None:
    source = (ROOT / "pages" / "data_alias_page.py").read_text(
        encoding="utf-8"
    )

    assert "DataWorkspaceController(" in source
    assert "AliasAwareValidationService(database, ValidationService)" in source
    assert "super().set_database(database)" in source
    assert "self._controller.get_characters()" in source

    for forbidden in (
        "self._service",
        "self._review_service",
        "self._validation_service",
        "DataService(",
        "ReviewService(",
    ):
        assert forbidden not in source
