from __future__ import annotations

from services.source_setup_validation import validate_source_filenames


def _touch(path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"filename-only-validation")


def test_source_filename_validation_maps_every_supported_file(tmp_path):
    source = tmp_path / "source"
    _touch(source / "AA23_EP001_SCRIPT.xlsx")
    _touch(source / "AA23_EP002_SCRIPT.xlsm")
    _touch(source / "AA23_EP003_SCRIPT.xlsx")
    _touch(source / "ignore.txt")
    _touch(source / "~$AA23_EP004_SCRIPT.xlsx")

    result = validate_source_filenames(
        source,
        episode_before="EP",
        episode_after="_",
    )

    assert result.is_valid
    assert result.file_count == 3
    assert result.episode_numbers == (1, 2, 3)
    assert result.missing_episodes == ()
    assert [item.episode_number for item in result.preview_mappings] == [1, 2, 3]
    assert result.analysis is not None
    assert len(result.analysis.patterns) == 1


def test_source_filename_validation_blocks_wrong_delimiter_for_all_files(tmp_path):
    source = tmp_path / "source"
    _touch(source / "AA23_EP001_SCRIPT.xlsx")
    _touch(source / "AA23_EP002_SCRIPT.xlsx")

    result = validate_source_filenames(
        source,
        episode_before="第",
        episode_after="集",
    )

    assert result.is_valid is False
    filename_errors = [
        issue for issue in result.errors if issue.field == "source_filename"
    ]
    assert len(filename_errors) == 2
    assert all("Delimiter awal" in issue.message for issue in filename_errors)


def test_source_filename_validation_blocks_non_numeric_episode(tmp_path):
    source = tmp_path / "source"
    _touch(source / "AA23_EPABC_SCRIPT.xlsx")

    result = validate_source_filenames(
        source,
        episode_before="EP",
        episode_after="_",
    )

    assert result.is_valid is False
    assert any(
        issue.field == "source_filename"
        and "bukan nomor episode" in issue.message
        for issue in result.errors
    )


def test_source_filename_validation_blocks_duplicate_episode(tmp_path):
    source = tmp_path / "source"
    _touch(source / "AA23_EP001_SCRIPT.xlsx")
    _touch(source / "AA23_EP001_ALT.xlsx")

    result = validate_source_filenames(
        source,
        episode_before="EP",
        episode_after="_",
    )

    assert result.is_valid is False
    assert any(
        issue.field == "source_episode" and "Episode 1" in issue.message
        for issue in result.errors
    )


def test_source_filename_validation_blocks_multiple_filename_patterns(tmp_path):
    source = tmp_path / "source"
    _touch(source / "AA23_EP001_SCRIPT.xlsx")
    _touch(source / "AA23_EP002_ALT.xlsx")

    result = validate_source_filenames(
        source,
        episode_before="EP",
        episode_after="_",
    )

    assert result.is_valid is False
    assert any(
        issue.field == "source_pattern" and "2 pola filename" in issue.message
        for issue in result.errors
    )
    assert result.episode_numbers == (1, 2)


def test_source_filename_validation_reports_episode_gap_as_warning(tmp_path):
    source = tmp_path / "source"
    _touch(source / "AA23_EP001_SCRIPT.xlsx")
    _touch(source / "AA23_EP003_SCRIPT.xlsx")

    result = validate_source_filenames(
        source,
        episode_before="EP",
        episode_after="_",
    )

    assert result.is_valid
    assert result.episode_numbers == (1, 3)
    assert result.missing_episodes == (2,)
    assert any(
        issue.field == "source_episode_gap"
        and issue.severity == "warning"
        and "2" in issue.message
        for issue in result.warnings
    )


def test_source_filename_validation_blocks_empty_source_folder(tmp_path):
    source = tmp_path / "source"
    source.mkdir()

    result = validate_source_filenames(source)

    assert result.is_valid is False
    assert result.file_count == 0
    assert "Tidak ada file .xlsx/.xlsm" in result.errors[0].message


def test_source_filename_validation_counts_same_filename_in_nested_folders(tmp_path):
    source = tmp_path / "source"
    _touch(source / "a" / "AA23_EP001_SCRIPT.xlsx")
    _touch(source / "b" / "AA23_EP001_SCRIPT.xlsx")

    result = validate_source_filenames(
        source,
        episode_before="EP",
        episode_after="_",
    )

    assert result.file_count == 2
    assert result.is_valid is False
    assert any(issue.field == "source_episode" for issue in result.errors)
