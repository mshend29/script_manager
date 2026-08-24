import shutil

from openpyxl import Workbook

from core.project import Project
from core.project_settings import ProjectSettings
from import_engine.source_sync import SourceSyncEngine


def _write_source(path, *, dialogue: str, character: str, talent: str) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Worksheet"
    sheet.append([None, None, None, None, None])
    sheet.append(["IN", "OUT", "DIALOG", "TOKOH", "TALENT"])
    sheet.append([
        "00:00:01,000",
        "00:00:02,000",
        dialogue,
        character,
        talent,
    ])
    workbook.save(path)
    workbook.close()


def test_byte_identical_restored_source_reactivates_dialogues(tmp_path):
    source_folder = tmp_path / "source"
    source_folder.mkdir()

    episode_1 = source_folder / "AA23-第1集_中文.xlsx"
    episode_2 = source_folder / "AA23-第2集_中文.xlsx"
    _write_source(
        episode_1,
        dialogue="Dialog episode satu",
        character="Hendra",
        talent="Brama",
    )
    _write_source(
        episode_2,
        dialogue="Dialog episode dua",
        character="Joko",
        talent="Dika",
    )

    project = Project(
        root=tmp_path / "project",
        settings=ProjectSettings(
            project_name="Restore Test",
            project_folder=str(tmp_path / "project"),
            source_folder=str(source_folder),
            episode_before="第",
            episode_after="集",
        ),
    )
    project.ensure_structure()
    project.database.initialize()

    engine = SourceSyncEngine()
    initial = engine.synchronize(project)
    assert not initial.has_errors
    assert initial.added == 2
    assert initial.parsed_files == 2
    assert initial.dialogues_added == 2

    with project.database.connect() as connection:
        episode_1_dialogue = connection.execute(
            """
            SELECT d.id
            FROM dialogues AS d
            JOIN episodes AS e ON e.id = d.episode_id
            WHERE e.episode_number = 1
            """
        ).fetchone()
        dialogue_id = int(episode_1_dialogue["id"])
        connection.execute(
            """
            UPDATE recording_status
            SET is_recorded = 1,
                recorded_at = '2026-08-24T10:00:00',
                updated_at = '2026-08-24T10:00:00'
            WHERE dialogue_id = ?
            """,
            (dialogue_id,),
        )

    held_copy = tmp_path / episode_1.name
    shutil.move(str(episode_1), held_copy)

    missing = engine.synchronize(project)
    assert not missing.has_errors
    assert missing.missing == 1
    assert missing.unchanged == 1
    assert missing.dialogues_deactivated == 1

    with project.database.connect() as connection:
        inactive = connection.execute(
            "SELECT is_active FROM dialogues WHERE id = ?",
            (dialogue_id,),
        ).fetchone()
        assert int(inactive["is_active"]) == 0

    shutil.move(str(held_copy), episode_1)

    restored = engine.synchronize(project)
    assert not restored.has_errors
    assert restored.restored == 1
    assert restored.changed == 0
    assert restored.unchanged == 1
    assert restored.inspected == 1
    assert restored.parsed_files == 1
    assert restored.dialogues_reactivated == 1
    assert "Restored Source: 1" in restored.summary()

    with project.database.connect() as connection:
        row = connection.execute(
            """
            SELECT
                d.is_active AS dialogue_active,
                e.is_active AS episode_active,
                sf.is_active AS source_active,
                rs.is_recorded
            FROM dialogues AS d
            JOIN episodes AS e ON e.id = d.episode_id
            JOIN source_files AS sf ON sf.id = d.source_file_id
            JOIN recording_status AS rs ON rs.dialogue_id = d.id
            WHERE d.id = ?
            """,
            (dialogue_id,),
        ).fetchone()

    assert int(row["dialogue_active"]) == 1
    assert int(row["episode_active"]) == 1
    assert int(row["source_active"]) == 1
    assert int(row["is_recorded"]) == 1
