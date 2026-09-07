from __future__ import annotations

import pytest
from openpyxl import Workbook

from import_engine.source_sync import SourceSyncEngine, SourceSyncError
from services.source_preflight_service import SourcePreflightService
from services.source_setup_validation import validate_source_filenames


def _write_script(path, *, valid_structure: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    if valid_structure:
        sheet.append(["IN", "OUT", "DIALOG", "TOKOH", "TALENT"])
        sheet.append(["00:00:01", "00:00:02", "Halo", "INDAH", "Talent A"])
        sheet.append(["00:00:03", "00:00:04", "Apa kabar?", "TEGUH", "Talent B"])
    else:
        sheet.append(["CATATAN", "LAIN"])
        sheet.append(["bukan", "naskah"])
    workbook.save(path)
    workbook.close()


def _filename_validation(source):
    return validate_source_filenames(
        source,
        episode_before="EP",
        episode_after="_",
    )


def test_preflight_reuses_production_read_only_inspector_and_parser(tmp_path):
    source = tmp_path / "source"
    _write_script(source / "AA23_EP001_SCRIPT.xlsx")
    _write_script(source / "AA23_EP002_SCRIPT.xlsm")

    filename_validation = _filename_validation(source)
    report = SourcePreflightService().run(filename_validation)

    assert report.is_valid
    assert report.is_reusable
    assert report.cancelled is False
    assert report.inspected_files == 2
    assert report.parsed_files == 2
    assert report.parsed_dialogues == 4
    assert report.scan is not None
    assert len(report.scan.files) == 2
    assert len(report.source_snapshot) == 2
    assert all(snapshot[1] for snapshot in report.source_snapshot)
    assert set(report.inspections) == {
        item.file_path for item in filename_validation.mappings
    }
    assert set(report.parse_results) == {
        item.file_path for item in filename_validation.mappings
    }

    # Delimiters that produced the validated mapping are retained so the same
    # production scanner can rebuild/compare the snapshot later.
    assert filename_validation.episode_before == "EP"
    assert filename_validation.episode_after == "_"
    assert all(item.layout_detection == "header" for item in report.files)

    # Preflight has no project/database target and must not create sidecar files.
    assert sorted(path.name for path in source.iterdir()) == [
        "AA23_EP001_SCRIPT.xlsx",
        "AA23_EP002_SCRIPT.xlsm",
    ]


def test_preflight_snapshot_detects_source_changed_before_create(tmp_path):
    source = tmp_path / "source"
    source_file = source / "AA23_EP001_SCRIPT.xlsx"
    _write_script(source_file)

    validation = _filename_validation(source)
    report = SourcePreflightService().run(validation)
    assert report.is_reusable

    source_file.write_bytes(source_file.read_bytes() + b"changed-after-preflight")

    with pytest.raises(SourceSyncError, match="Source berubah sejak Source Preflight"):
        SourceSyncEngine().verify_source_snapshot(
            source_folder=str(source),
            episode_before=validation.episode_before,
            episode_after=validation.episode_after,
            expected_snapshot=report.source_snapshot,
        )


def test_preflight_reports_corrupt_workbook_per_file_and_skips_parse_phase(tmp_path):
    source = tmp_path / "source"
    _write_script(source / "AA23_EP001_SCRIPT.xlsx")
    corrupt = source / "AA23_EP002_SCRIPT.xlsx"
    corrupt.write_bytes(b"not-an-xlsx")

    progress = []
    report = SourcePreflightService().run(
        _filename_validation(source),
        progress_callback=progress.append,
    )

    assert report.is_valid is False
    assert report.is_reusable is False
    assert report.inspected_files == 1
    assert report.parsed_files == 0
    assert any("AA23_EP002_SCRIPT.xlsx" in problem for problem in report.problems)
    assert any("Workbook tidak dapat dibuka" in problem for problem in report.problems)
    assert not any(item.stage == "parsing" for item in progress)


def test_preflight_reports_unrecognized_script_structure(tmp_path):
    source = tmp_path / "source"
    _write_script(
        source / "AA23_EP001_SCRIPT.xlsx",
        valid_structure=False,
    )

    report = SourcePreflightService().run(_filename_validation(source))

    assert report.is_valid is False
    assert report.is_reusable is False
    assert report.inspected_files == 1
    assert report.parsed_files == 0
    assert len(report.problems) == 1
    assert "Struktur naskah tidak dikenali" in report.problems[0]
    assert report.files[0].error


def test_preflight_can_be_cancelled_between_files(tmp_path):
    source = tmp_path / "source"
    for episode in range(1, 4):
        _write_script(source / f"AA23_EP{episode:03d}_SCRIPT.xlsx")

    progress = []

    def cancelled() -> bool:
        return any(
            item.stage == "inspecting" and item.current >= 1
            for item in progress
        )

    report = SourcePreflightService().run(
        _filename_validation(source),
        progress_callback=progress.append,
        cancel_callback=cancelled,
    )

    assert report.cancelled is True
    assert report.is_valid is False
    assert report.is_reusable is False
    assert report.inspected_files == 1
    assert report.parsed_files == 0
    assert progress[-1].stage == "cancelled"


def test_preflight_rejects_invalid_filename_gate_before_opening_workbooks(tmp_path):
    source = tmp_path / "source"
    _write_script(source / "AA23_EP001_SCRIPT.xlsx")
    _write_script(source / "AA23_EP001_OTHER.xlsx")

    filename_validation = _filename_validation(source)
    assert filename_validation.is_valid is False

    report = SourcePreflightService().run(filename_validation)

    assert report.is_valid is False
    assert report.is_reusable is False
    assert report.inspected_files == 0
    assert report.parsed_files == 0
    assert report.problems
