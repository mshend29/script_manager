from __future__ import annotations

from openpyxl import Workbook

from core.project_manager import ProjectManager
from core.project_settings import ProjectSettings
from import_engine.source_sync import SourceSyncEngine
from services.recording_service import RecordingService
from services.tracking_service import (
    AUTO_FILE_STATUS_NOTE,
    DELIVERED,
    RECORDED,
    TrackingService,
)


def _write_episode(path, *, hendra_dialogue: str) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "SCRIPT"
    sheet.append([None, None, None, None, None])
    sheet.append(["IN", "OUT", "DIALOG", "TOKOH", "TALENT"])
    sheet.append(
        [
            "00:00:01,000",
            "00:00:02,000",
            hendra_dialogue,
            "Hendra",
            "Brama",
        ]
    )
    sheet.append(
        [
            "00:00:03,000",
            "00:00:04,000",
            "Dialog Joko tetap",
            "Joko",
            "Dika",
        ]
    )
    workbook.save(path)
    workbook.close()


def _cast_scope(database, character_name: str):
    with database.connect() as connection:
        row = connection.execute(
            """
            SELECT
                d.id AS dialogue_id,
                d.episode_id,
                e.episode_number,
                c.id AS character_id,
                t.id AS talent_id
            FROM dialogues AS d
            JOIN episodes AS e ON e.id = d.episode_id
            JOIN dialog_cast AS dc ON dc.dialogue_id = d.id
            JOIN characters AS c ON c.id = dc.character_id
            JOIN talents AS t ON t.id = dc.talent_id
            WHERE d.is_active = 1
              AND c.name = ?
            LIMIT 1
            """,
            (character_name,),
        ).fetchone()

    assert row is not None
    return {
        "dialogue_id": int(row["dialogue_id"]),
        "episode_id": int(row["episode_id"]),
        "episode_number": int(row["episode_number"]),
        "character_id": int(row["character_id"]),
        "talent_id": int(row["talent_id"]),
    }


def _set_auto_delivered(database, scope) -> None:
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO stem_status(
                episode_id,
                talent_id,
                character_id,
                status,
                note
            )
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(episode_id, talent_id, character_id)
            DO UPDATE SET
                status = excluded.status,
                note = excluded.note
            """,
            (
                scope["episode_id"],
                scope["talent_id"],
                scope["character_id"],
                DELIVERED,
                AUTO_FILE_STATUS_NOTE,
            ),
        )


def _chip(tracking: TrackingService, scope):
    rows = tracking.get_character_rows(
        scope["talent_id"],
        episode_number=scope["episode_number"],
    )
    chips = [
        chip
        for row in rows
        for chip in row.chips
        if chip.character_id == scope["character_id"]
    ]
    assert len(chips) == 1
    return chips[0]


def test_v1_representative_operator_workflow_survives_client_revision(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "appdata"))

    source_folder = tmp_path / "source"
    source_folder.mkdir()
    source_file = source_folder / "AA23-第1集_中文.xlsx"
    _write_episode(source_file, hendra_dialogue="Dialog Hendra awal")

    manager = ProjectManager()
    project = manager.create(
        ProjectSettings(
            project_name="AA23 Representative UAT",
            project_code="AA23-UAT",
            source_folder=str(source_folder),
            episode_before="第",
            episode_after="集",
        ),
        tmp_path / "projects",
    )

    sync = SourceSyncEngine()
    initial = sync.synchronize(project)
    assert not initial.has_errors
    assert initial.applied is True

    hendra = _cast_scope(project.database, "Hendra")
    joko = _cast_scope(project.database, "Joko")
    assert hendra["episode_id"] == joko["episode_id"]

    recording = RecordingService(project.database)
    tracking = TrackingService(project.database)

    # Operator completes both cast scopes in DIALOG.
    recording.set_recorded(hendra["dialogue_id"], True)
    recording.set_recorded(joko["dialogue_id"], True)

    hendra_recorded = recording.get_dialogues(
        talent_id=hendra["talent_id"],
        character_id=hendra["character_id"],
        episode_number=1,
    )
    joko_recorded = recording.get_dialogues(
        talent_id=joko["talent_id"],
        character_id=joko["character_id"],
        episode_number=1,
    )
    assert hendra_recorded[0].is_recorded is True
    assert joko_recorded[0].is_recorded is True
    assert _chip(tracking, hendra).display_status == RECORDED
    assert _chip(tracking, joko).display_status == RECORDED

    # File inventory has already confirmed both outputs as delivered.
    _set_auto_delivered(project.database, hendra)
    _set_auto_delivered(project.database, joko)
    assert _chip(tracking, hendra).display_status == DELIVERED
    assert _chip(tracking, joko).display_status == DELIVERED

    # Client revises only Hendra's source dialogue.
    _write_episode(
        source_file,
        hendra_dialogue="Dialog Hendra revisi dari client",
    )
    refreshed = sync.synchronize(project)
    assert not refreshed.has_errors
    assert refreshed.applied is True

    hendra_after = _cast_scope(project.database, "Hendra")
    joko_after = _cast_scope(project.database, "Joko")

    # Persistent lineage survives the text revision.
    assert hendra_after["dialogue_id"] == hendra["dialogue_id"]
    assert joko_after["dialogue_id"] == joko["dialogue_id"]

    hendra_rows = recording.get_dialogues(
        talent_id=hendra["talent_id"],
        character_id=hendra["character_id"],
        episode_number=1,
    )
    joko_rows = recording.get_dialogues(
        talent_id=joko["talent_id"],
        character_id=joko["character_id"],
        episode_number=1,
    )

    # Recording history remains, but the revised line is clearly stale.
    assert hendra_rows[0].is_recorded is True
    assert hendra_rows[0].source_revised is True
    assert joko_rows[0].is_recorded is True
    assert joko_rows[0].source_revised is False

    # Only the affected downstream scope is invalidated.
    assert _chip(tracking, hendra).display_status == RECORDED
    assert _chip(tracking, joko).display_status == DELIVERED

    invalidations = refreshed.synchronize_report.tracking_invalidations
    assert len(invalidations) == 1
    assert invalidations[0].character_name == "Hendra"
    assert invalidations[0].talent_name == "Brama"
    assert invalidations[0].reasons == ("SOURCE_REVISED",)

    # Re-recording accepts the current source signature and clears the stale
    # marker without changing the persistent dialogue identity.
    recording.set_recorded(hendra["dialogue_id"], True)
    accepted = recording.get_dialogues(
        talent_id=hendra["talent_id"],
        character_id=hendra["character_id"],
        episode_number=1,
    )
    assert accepted[0].dialogue_id == hendra["dialogue_id"]
    assert accepted[0].is_recorded is True
    assert accepted[0].source_revised is False
