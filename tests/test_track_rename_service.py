from __future__ import annotations

from pathlib import Path

from core.database import Database
from services.audit_service import AuditService
from services.track_file_service import AudioFileCheck, TrackFileRow
from services.track_rename_service import (
    MATCH_SEMANTIC,
    MATCH_SIMPLE_EXPORT,
    RENAME_ALREADY_EXPECTED,
    RENAME_AMBIGUOUS,
    RENAME_COLLISION,
    RENAME_MATCHED,
    RENAME_UNMATCHED,
    TrackRenameService,
)


def _row(
    *,
    episode: int,
    character_id: int,
    character: str,
    aliases: tuple[str, ...] = (),
    talent_id: int = 1,
    talent: str = "Brama",
    expected: str,
) -> TrackFileRow:
    return TrackFileRow(
        episode_id=episode,
        episode_number=episode,
        character_id=character_id,
        character_name=character,
        aliases=aliases,
        talent_id=talent_id,
        talent_name=talent,
        total_dialogues=1,
        recorded_dialogues=1,
        track_suggestion=expected.removesuffix(".wav"),
        expected_filename=expected,
        output=AudioFileCheck(),
        delivered=AudioFileCheck(),
        file_status=None,
        warnings=(),
    )


def _service(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    output = tmp_path / "output"
    output.mkdir()
    return database, output, TrackRenameService(
        database,
        output_folder=str(output),
    )


def test_batch_plan_matches_simple_daw_exports_and_appends_expected_talent(tmp_path):
    database, output, service = _service(tmp_path)
    rows = [
        _row(
            episode=1,
            character_id=1,
            character="A",
            expected="1_A_Brama.wav",
        ),
        _row(
            episode=1,
            character_id=2,
            character="B",
            expected="1_B_Brama.wav",
        ),
        _row(
            episode=1,
            character_id=3,
            character="C",
            expected="1_C_Brama.wav",
        ),
    ]

    for name in ("1_A.wav", "1_B.wav", "1_C.wav"):
        (output / name).write_bytes(b"wav-placeholder")

    plan = service.build_plan(rows, talent_id=1, episode_number=1)

    assert plan.matched == 3
    assert plan.ambiguous == 0
    assert plan.collisions == 0
    assert {
        Path(item.source_path).name: Path(item.target_path).name
        for item in plan.rename_items
    } == {
        "1_A.wav": "1_A_Brama.wav",
        "1_B.wav": "1_B_Brama.wav",
        "1_C.wav": "1_C_Brama.wav",
    }
    assert {
        item.match_kind for item in plan.rename_items
    } == {MATCH_SIMPLE_EXPORT}

    renamed = service.execute(plan)
    assert len(renamed) == 3
    assert not (output / "1_A.wav").exists()
    assert (output / "1_A_Brama.wav").exists()
    assert (output / "1_B_Brama.wav").exists()
    assert (output / "1_C_Brama.wav").exists()

    audit = AuditService(database).recent(1)
    assert audit
    assert audit[0].action == "BATCH_RENAME_TO_EXPECTED"
    assert len(audit[0].details["renamed"]) == 3


def test_semantically_valid_canonical_first_file_can_normalize_to_preferred_expected(tmp_path):
    _database, output, service = _service(tmp_path)
    row = _row(
        episode=95,
        character_id=10,
        character="Andi",
        aliases=("Bapak jas navy",),
        expected="95_BAPAK JAS NAVY ANDI_Brama.wav",
    )
    current = output / "95_ANDI BAPAK JAS NAVY_Brama.wav"
    current.write_bytes(b"wav-placeholder")

    plan = service.build_plan([row], talent_id=1)

    assert plan.matched == 1
    item = plan.rename_items[0]
    assert item.match_kind == MATCH_SEMANTIC
    assert Path(item.source_path).name == current.name
    assert Path(item.target_path).name == row.expected_filename


def test_expected_file_is_not_renamed_again(tmp_path):
    _database, output, service = _service(tmp_path)
    row = _row(
        episode=95,
        character_id=10,
        character="Andi",
        aliases=("Bapak jas navy",),
        expected="95_BAPAK JAS NAVY ANDI_Brama.wav",
    )
    (output / row.expected_filename).write_bytes(b"wav-placeholder")

    plan = service.build_plan([row], talent_id=1)

    assert plan.matched == 0
    assert plan.already_expected == 1
    assert plan.items[0].status == RENAME_ALREADY_EXPECTED


def test_collision_never_overwrites_existing_expected_file(tmp_path):
    _database, output, service = _service(tmp_path)
    row = _row(
        episode=1,
        character_id=1,
        character="A",
        expected="1_A_Brama.wav",
    )
    source = output / "1_A.wav"
    target = output / "1_A_Brama.wav"
    source.write_bytes(b"source")
    target.write_bytes(b"keep-me")

    plan = service.build_plan([row], talent_id=1, episode_number=1)

    collision = [
        item for item in plan.items
        if Path(item.source_path).name == "1_A.wav"
    ][0]
    assert collision.status == RENAME_COLLISION
    assert plan.matched == 0

    renamed = service.execute(plan)
    assert renamed == []
    assert source.read_bytes() == b"source"
    assert target.read_bytes() == b"keep-me"


def test_simple_export_is_ambiguous_when_same_track_name_has_two_expected_identities(tmp_path):
    _database, output, service = _service(tmp_path)
    rows = [
        _row(
            episode=1,
            character_id=1,
            character="Bapak",
            aliases=("Jas Navy",),
            expected="1_JAS NAVY BAPAK_Brama.wav",
        ),
        _row(
            episode=1,
            character_id=2,
            character="Bapak",
            aliases=("Kemeja Biru",),
            expected="1_KEMEJA BIRU BAPAK_Brama.wav",
        ),
    ]
    source = output / "1_BAPAK.wav"
    source.write_bytes(b"source")

    plan = service.build_plan(rows, talent_id=1, episode_number=1)

    assert plan.matched == 0
    assert plan.ambiguous == 1
    assert plan.items[0].status == RENAME_AMBIGUOUS
    assert source.exists()


def test_single_source_action_surfaces_unmatched_file_instead_of_guessing(tmp_path):
    _database, output, service = _service(tmp_path)
    row = _row(
        episode=1,
        character_id=1,
        character="A",
        expected="1_A_Brama.wav",
    )
    source = output / "1_UNKNOWN.wav"
    source.write_bytes(b"source")

    plan = service.build_plan(
        [row],
        talent_id=1,
        selected_source_path=str(source),
    )

    assert len(plan.items) == 1
    assert plan.items[0].status == RENAME_UNMATCHED
    assert plan.matched == 0
