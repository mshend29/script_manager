from __future__ import annotations

from services.source_filename_service import (
    analyze_source_filenames,
    read_source_filenames,
)


def test_source_filename_analysis_keeps_constant_project_number_and_marks_episode_run():
    analysis = analyze_source_filenames(
        [
            "AA23-第1集_中文.xlsx",
            "AA23-第2集_中文.xlsx",
            "AA23-第110集_中文.xlsx",
        ]
    )

    assert analysis.is_consistent is True
    assert len(analysis.patterns) == 1
    pattern = analysis.patterns[0]
    assert pattern.pattern == "AA23-第{number}集_中文.xlsx"
    assert pattern.count == 3
    assert pattern.varying_number_runs == 1


def test_source_filename_analysis_reports_multiple_naming_patterns():
    analysis = analyze_source_filenames(
        [
            "AA23-第1集_中文.xlsx",
            "AA23-第2集_中文.xlsx",
            "AA23_EP3.xlsx",
        ]
    )

    assert analysis.is_consistent is False
    assert len(analysis.patterns) == 2
    assert analysis.patterns[0].count == 2
    assert analysis.patterns[0].pattern == "AA23-第{number}集_中文.xlsx"


def test_read_source_filenames_only_needs_filenames_not_valid_workbook_content(tmp_path):
    source = tmp_path / "SCRIPT"
    nested = source / "nested"
    nested.mkdir(parents=True)

    # Empty files are intentionally not valid workbooks. The helper must only
    # inspect filenames and must never attempt to open/parse them.
    (source / "AA23-第1集_中文.xlsx").write_bytes(b"")
    (source / "AA23-第2集_中文.xlsm").write_bytes(b"")
    (source / "~$AA23-第3集_中文.xlsx").write_bytes(b"")
    (nested / "notes.txt").write_text("ignore", encoding="utf-8")

    analysis = read_source_filenames(source)

    assert analysis.filenames == (
        "AA23-第1集_中文.xlsx",
        "AA23-第2集_中文.xlsm",
    )
    # Extension differences are intentionally surfaced as different patterns.
    assert analysis.is_consistent is False
    assert len(analysis.patterns) == 2


def test_source_filename_analysis_flags_two_varying_numeric_runs_as_ambiguous():
    analysis = analyze_source_filenames(
        [
            "AA23_EP1_v1.xlsx",
            "AA24_EP2_v2.xlsx",
        ]
    )

    assert analysis.is_consistent is False
    assert analysis.patterns[0].varying_number_runs == 3
