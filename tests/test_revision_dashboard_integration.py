from __future__ import annotations

import wave
from pathlib import Path

from core.database import Database
from core.project_settings import ProjectSettings
from services.project_dashboard_service import ProjectDashboardService
from services.tracking_service import REVISION
from services.validation_service import ValidationService


def _seed_single_track(
    database: Database,
    *,
    recorded: bool,
) -> dict[str, int]:
    database.initialize()

    with database.connect() as connection:
        source_id = connection.execute(
            """
            INSERT INTO source_files(
                file_path, file_name, episode_number, is_active
            ) VALUES('ep1.xlsx', 'ep1.xlsx', 1, 1)
            """
        ).lastrowid
        episode_id = connection.execute(
            """
            INSERT INTO episodes(episode_number, source_file_id, is_active)
            VALUES(1, ?, 1)
            """,
            (source_id,),
        ).lastrowid
        character_id = connection.execute(
            """
            INSERT INTO characters(name, normalized_name, is_active)
            VALUES('Joko', 'joko', 1)
            """
        ).lastrowid
        talent_id = connection.execute(
            """
            INSERT INTO talents(name, normalized_name, is_active)
            VALUES('Brama', 'brama', 1)
            """
        ).lastrowid
        dialogue_id = connection.execute(
            """
            INSERT INTO dialogues(
                dialog_uid, episode_id, source_file_id,
                time_in, time_out, dialog_text, is_active
            )
            VALUES('ep1-joko', ?, ?, '00:00:01,000', '00:00:02,000', 'Halo', 1)
            """,
            (episode_id, source_id),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO dialog_cast(dialogue_id, character_id, talent_id, position)
            VALUES(?, ?, ?, 0)
            """,
            (dialogue_id, character_id, talent_id),
        )
        connection.execute(
            """
            INSERT INTO recording_status(dialogue_id, is_recorded)
            VALUES(?, ?)
            """,
            (dialogue_id, 1 if recorded else 0),
        )

    return {
        "episode": int(episode_id),
        "character": int(character_id),
        "talent": int(talent_id),
    }


def _mark_pending_revision(database: Database, ids: dict[str, int]) -> None:
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO stem_status(
                episode_id, talent_id, character_id, status, note
            ) VALUES(?, ?, ?, ?, 'revision:1')
            """,
            (
                ids["episode"],
                ids["talent"],
                ids["character"],
                REVISION,
            ),
        )


def _settings(tmp_path: Path) -> ProjectSettings:
    output = tmp_path / "output"
    delivery = tmp_path / "delivery"
    output.mkdir(exist_ok=True)
    delivery.mkdir(exist_ok=True)
    return ProjectSettings(
        stem_output_folder=str(output),
        delivery_folder=str(delivery),
        audio_sample_rate=48000,
        audio_bit_depth=24,
        audio_channels=1,
    )


def _write_valid_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(3)
        handle.setframerate(48000)
        handle.writeframes(b"\x00\x00\x00" * 128)


def test_dashboard_does_not_double_count_pending_revision_as_recorded_to_stem(
    tmp_path,
):
    database = Database(tmp_path / "project.db")
    ids = _seed_single_track(database, recorded=True)
    _mark_pending_revision(database, ids)
    settings = _settings(tmp_path)

    snapshot = ProjectDashboardService(database, settings).build()

    assert snapshot.revisions == 1
    assert snapshot.recorded_waiting_stem == 0
    action_keys = {action.key for action in snapshot.actions}
    assert "revision" in action_keys
    assert "ready_to_stem" not in action_keys


def test_dashboard_uses_status_after_revision_output_scan(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed_single_track(database, recorded=True)
    _mark_pending_revision(database, ids)
    settings = _settings(tmp_path)

    output_path = Path(settings.stem_output_folder) / "1_JOKO_Brama_REV.wav"
    _write_valid_wav(output_path)

    snapshot = ProjectDashboardService(database, settings).build()

    assert snapshot.revisions == 0
    assert snapshot.recorded_waiting_stem == 0
    assert snapshot.stemmed_waiting_delivery == 1

    with database.connect() as connection:
        status = connection.execute(
            """
            SELECT status, note
            FROM stem_status
            WHERE episode_id = ? AND talent_id = ? AND character_id = ?
            """,
            (ids["episode"], ids["talent"], ids["character"]),
        ).fetchone()
    assert status["status"] == "STEMMED"
    assert "revision:1" in status["note"]


def test_validation_flags_legacy_revision_before_recording_complete(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed_single_track(database, recorded=False)
    _mark_pending_revision(database, ids)

    issues = ValidationService(database).validate()
    matching = [
        issue
        for issue in issues
        if issue.code == "DOWNSTREAM_BEFORE_RECORDED"
    ]

    assert len(matching) == 1
    assert matching[0].action == "TRACKING"
    assert "REVISION" in matching[0].message
