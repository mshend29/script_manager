from __future__ import annotations

import shutil
import wave

from core.database import Database
from services.track_file_service import (
    TrackAudioSpec,
    TrackFileService,
    build_track_suggestion,
)
from services.tracking_service import (
    AUTO_FILE_STATUS_NOTE,
    DELIVERED,
    RECORDED,
    REVISION,
    STEMMED,
    TrackingService,
)


def _write_wav(path, *, rate=48000, width=3, channels=1):
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(width)
        handle.setframerate(rate)
        handle.writeframes(b"\x00" * width * channels * 16)


def _write_float_wav(path, *, rate=48000, channels=1):
    data = b"\\x00\\x00\\x00\\x00" * channels * 8
    fmt = struct.pack(
        "<IHHIIHH",
        16,
        3,
        channels,
        rate,
        rate * channels * 4,
        channels * 4,
        32,
    )
    payload = b"fmt " + fmt + b"data" + struct.pack("<I", len(data)) + data
    riff_size = 4 + len(payload)
    path.write_bytes(
        b"RIFF"
        + struct.pack("<I", riff_size)
        + b"WAVE"
        + payload
    )


def _seed(database: Database) -> dict[str, int]:
    database.initialize()
    with database.connect() as connection:
        source = connection.execute(
            """
            INSERT INTO source_files(
                file_path, file_name, episode_number, is_active
            ) VALUES('ep4.xlsx', 'ep4.xlsx', 4, 1)
            """
        ).lastrowid
        episode = connection.execute(
            """
            INSERT INTO episodes(
                episode_number, source_file_id, is_active
            ) VALUES(4, ?, 1)
            """,
            (source,),
        ).lastrowid
        andi = connection.execute(
            """
            INSERT INTO characters(name, normalized_name, is_active)
            VALUES('Andi', 'andi', 1)
            """
        ).lastrowid
        brama = connection.execute(
            """
            INSERT INTO talents(name, normalized_name, is_active)
            VALUES('Brama', 'brama', 1)
            """
        ).lastrowid

        dialogue = connection.execute(
            """
            INSERT INTO dialogues(
                dialog_uid, episode_id, source_file_id,
                dialog_text, source_row, is_active
            ) VALUES('uid-4', ?, ?, 'Halo', 10, 1)
            """,
            (episode, source),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO dialog_cast(
                dialogue_id, character_id, talent_id, position
            ) VALUES(?, ?, ?, 0)
            """,
            (dialogue, andi, brama),
        )
        connection.execute(
            """
            INSERT INTO recording_status(dialogue_id, is_recorded)
            VALUES(?, 1)
            """,
            (dialogue,),
        )

        alias = connection.execute(
            """
            INSERT INTO character_alias(
                alias_name, normalized_alias,
                canonical_character_id, created_at, updated_at
            ) VALUES(
                'Bapak jas navy', 'bapak jas navy', ?,
                '2026-08-27T09:00:00', '2026-08-27T09:00:00'
            )
            """,
            (andi,),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO character_alias_dialogue(
                alias_id, dialogue_id, talent_id, position, created_canonical
            ) VALUES(?, ?, ?, 0, 1)
            """,
            (alias, dialogue, brama),
        )

        # A global alias without episode provenance must not pollute EP4 filename.
        connection.execute(
            """
            INSERT INTO character_alias(
                alias_name, normalized_alias,
                canonical_character_id, created_at, updated_at
            ) VALUES(
                'Pria jas navy', 'pria jas navy', ?,
                '2026-08-27T09:00:00', '2026-08-27T09:00:00'
            )
            """,
            (andi,),
        )

    return {
        "episode": int(episode),
        "character": int(andi),
        "talent": int(brama),
        "dialogue": int(dialogue),
    }


def _service(database, output, delivery):
    return TrackFileService(
        database,
        output_folder=str(output),
        delivery_folder=str(delivery),
        audio_spec=TrackAudioSpec(
            file_format="WAV",
            sample_rate=48000,
            bit_depth=24,
            channels=1,
        ),
    )


def test_track_suggestion_uses_canonical_plus_episode_alias_and_uppercase_character(
    tmp_path,
):
    database = Database(tmp_path / "project.db")
    _seed(database)
    output = tmp_path / "output"
    delivery = tmp_path / "setoran"
    output.mkdir()
    delivery.mkdir()

    inventory = _service(database, output, delivery).scan_and_sync()
    assert len(inventory.rows) == 1

    row = inventory.rows[0]
    assert row.aliases == ("Bapak jas navy",)
    assert row.track_suggestion == "4_BAPAK JAS NAVY ANDI_Brama"
    assert row.expected_filename == "4_BAPAK JAS NAVY ANDI_Brama.wav"
    assert "PRIA JAS NAVY" not in row.track_suggestion


def test_filename_component_uses_spaces_instead_of_windows_invalid_separators():
    suggestion = build_track_suggestion(
        4,
        "Andi/Bapak_jas",
        ["Pria: navy"],
        "Bra_ma",
    )
    assert suggestion == "4_PRIA NAVY ANDI BAPAK JAS_Bra ma"


def test_canonical_first_actual_filename_matches_alias_first_suggestion_without_warning(
    tmp_path,
):
    database = Database(tmp_path / "project.db")
    _seed(database)
    output = tmp_path / "output"
    delivery = tmp_path / "setoran"
    output.mkdir()
    delivery.mkdir()

    actual = "4_ANDI BAPAK JAS NAVY_Brama.wav"
    _write_wav(output / actual)

    inventory = _service(database, output, delivery).scan_and_sync()
    row = inventory.rows[0]

    assert row.track_suggestion == "4_BAPAK JAS NAVY ANDI_Brama"
    assert row.output.valid is True
    assert row.output.path.endswith(actual)
    assert not row.warnings
    assert not any(
        warning.code == "UNEXPECTED_TRACK_FILE"
        for warning in inventory.warnings
    )


def test_missing_or_extra_character_identity_does_not_match(tmp_path):
    database = Database(tmp_path / "project.db")
    _seed(database)
    output = tmp_path / "output"
    delivery = tmp_path / "setoran"
    output.mkdir()
    delivery.mkdir()

    _write_wav(output / "4_BAPAK JAS NAVY_Brama.wav")
    _write_wav(output / "4_BAPAK JAS NAVY ANDI ORANG ASING_Brama.wav")

    inventory = _service(database, output, delivery).scan_and_sync()
    assert inventory.rows[0].output.exists is False
    unexpected = [
        warning
        for warning in inventory.warnings
        if warning.code == "UNEXPECTED_TRACK_FILE"
    ]
    assert len(unexpected) == 2


def test_valid_output_and_delivery_drive_automatic_statuses(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed(database)
    output = tmp_path / "output"
    delivery = tmp_path / "setoran"
    output.mkdir()
    delivery.mkdir()

    expected = "4_ANDI BAPAK JAS NAVY_Brama.wav"
    _write_wav(output / expected)

    service = _service(database, output, delivery)
    first = service.scan_and_sync()
    row = first.rows[0]
    assert row.output.valid is True
    assert row.delivered.exists is False
    assert row.file_status == STEMMED

    tracking = TrackingService(database)
    chip = tracking.get_character_rows(ids["talent"])[0].chips[0]
    assert chip.display_status == STEMMED
    assert chip.downstream_note == AUTO_FILE_STATUS_NOTE

    shutil.copy2(output / expected, delivery / expected)
    second = service.scan_and_sync()
    assert second.rows[0].delivered.valid is True
    assert second.rows[0].file_status == DELIVERED

    chip = tracking.get_character_rows(ids["talent"])[0].chips[0]
    assert chip.display_status == DELIVERED


def test_invalid_wav_does_not_promote_recorded_status_and_reports_warning(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed(database)
    output = tmp_path / "output"
    delivery = tmp_path / "setoran"
    output.mkdir()
    delivery.mkdir()

    expected = output / "4_ANDI BAPAK JAS NAVY_Brama.wav"
    _write_wav(expected, rate=44100, width=2, channels=2)

    inventory = _service(database, output, delivery).scan_and_sync()
    row = inventory.rows[0]
    assert row.output.exists is True
    assert row.output.valid is False
    assert row.file_status is None
    assert any(
        warning.code == "INVALID_OUTPUT_FORMAT"
        for warning in row.warnings
    )

    chip = TrackingService(database).get_character_rows(ids["talent"])[0].chips[0]
    assert chip.display_status == RECORDED


def test_removing_output_downgrades_auto_stemmed_back_to_recorded(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed(database)
    output = tmp_path / "output"
    delivery = tmp_path / "setoran"
    output.mkdir()
    delivery.mkdir()

    expected = output / "4_ANDI BAPAK JAS NAVY_Brama.wav"
    _write_wav(expected)
    service = _service(database, output, delivery)
    service.scan_and_sync()

    expected.unlink()
    service.scan_and_sync()

    with database.connect() as connection:
        cached = connection.execute(
            """
            SELECT status FROM stem_status
            WHERE episode_id = ? AND talent_id = ? AND character_id = ?
            """,
            (ids["episode"], ids["talent"], ids["character"]),
        ).fetchone()
    assert cached is None

    chip = TrackingService(database).get_character_rows(ids["talent"])[0].chips[0]
    assert chip.display_status == RECORDED


def test_revision_is_never_overwritten_by_filesystem_scan(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed(database)
    output = tmp_path / "output"
    delivery = tmp_path / "setoran"
    output.mkdir()
    delivery.mkdir()

    expected = "4_ANDI BAPAK JAS NAVY_Brama.wav"
    _write_wav(output / expected)
    _write_wav(delivery / expected)

    tracking = TrackingService(database)
    tracking.set_downstream_status(
        episode_id=ids["episode"],
        talent_id=ids["talent"],
        character_id=ids["character"],
        status=REVISION,
    )

    _service(database, output, delivery).scan_and_sync()

    with database.connect() as connection:
        row = connection.execute(
            """
            SELECT status FROM stem_status
            WHERE episode_id = ? AND talent_id = ? AND character_id = ?
            """,
            (ids["episode"], ids["talent"], ids["character"]),
        ).fetchone()
    assert row["status"] == REVISION

    chip = tracking.get_character_rows(ids["talent"])[0].chips[0]
    assert chip.display_status == REVISION


def test_delivery_without_output_is_delivered_but_warned_as_mismatch(tmp_path):
    database = Database(tmp_path / "project.db")
    _seed(database)
    output = tmp_path / "output"
    delivery = tmp_path / "setoran"
    output.mkdir()
    delivery.mkdir()

    expected = "4_ANDI BAPAK JAS NAVY_Brama.wav"
    _write_wav(delivery / expected)

    inventory = _service(database, output, delivery).scan_and_sync()
    row = inventory.rows[0]
    assert row.file_status == DELIVERED
    assert any(
        warning.code == "DELIVERED_WITHOUT_OUTPUT"
        for warning in row.warnings
    )


def test_32_bit_float_wav_is_valid_for_32_bit_project_spec(tmp_path):
    database = Database(tmp_path / "project.db")
    _seed(database)
    output = tmp_path / "output"
    delivery = tmp_path / "setoran"
    output.mkdir()
    delivery.mkdir()

    actual = output / "4_BAPAK JAS NAVY ANDI_Brama.wav"
    _write_float_wav(actual)

    service = TrackFileService(
        database,
        output_folder=str(output),
        delivery_folder=str(delivery),
        audio_spec=TrackAudioSpec(
            file_format="WAV",
            sample_rate=48000,
            bit_depth=32,
            channels=1,
        ),
    )
    inventory = service.scan_and_sync()
    assert inventory.rows[0].output.valid is True
    assert inventory.rows[0].output.info.format_tag == 3


def test_non_wav_audio_and_unexpected_wav_are_reported(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed(database)
    output = tmp_path / "output"
    delivery = tmp_path / "setoran"
    output.mkdir()
    delivery.mkdir()

    (output / "4_ANDI BAPAK JAS NAVY_Brama.mp3").write_bytes(b"not audio")
    _write_wav(output / "99_UNKNOWN_Brama.wav")

    inventory = _service(database, output, delivery).scan_and_sync()
    codes = {warning.code for warning in inventory.warnings}
    assert "UNSUPPORTED_OUTPUT_AUDIO" in codes
    assert "UNEXPECTED_TRACK_FILE" in codes

    health = inventory.health_for_talent(ids["talent"])
    assert health.warnings >= 2
