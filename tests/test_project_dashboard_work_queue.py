from __future__ import annotations

from core.database import Database
from core.project_settings import ProjectSettings
from services.audit_service import AuditService
from services.project_dashboard_service import ProjectDashboardService


def _seed(database: Database) -> None:
    database.initialize()
    with database.connect() as connection:
        source = connection.execute(
            """
            INSERT INTO source_files(
                file_path, file_name, episode_number, is_active
            ) VALUES('ep1.xlsx', 'ep1.xlsx', 1, 1)
            """
        ).lastrowid
        episode = connection.execute(
            """
            INSERT INTO episodes(
                episode_number, source_file_id, title, is_active
            ) VALUES(1, ?, 'EP1', 1)
            """,
            (source,),
        ).lastrowid

        character = connection.execute(
            """
            INSERT INTO characters(
                name, normalized_name, base_normalized_name, is_active
            ) VALUES('Andi', 'andi', 'andi', 1)
            """
        ).lastrowid
        talent = connection.execute(
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
            ) VALUES('uid-recording', ?, ?, 'Halo', 3, 1)
            """,
            (episode, source),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO dialog_cast(
                dialogue_id, character_id, talent_id, position
            ) VALUES(?, ?, ?, 0)
            """,
            (dialogue, character, talent),
        )
        connection.execute(
            """
            INSERT INTO recording_status(dialogue_id, is_recorded)
            VALUES(?, 0)
            """,
            (dialogue,),
        )

        # Separate unresolved/no-cast dialogue creates a human review action.
        connection.execute(
            """
            INSERT INTO dialogues(
                dialog_uid, episode_id, source_file_id,
                dialog_text, source_row, is_active
            ) VALUES('uid-review', ?, ?, 'Narasi?', 4, 1)
            """,
            (episode, source),
        )

        connection.execute(
            """
            INSERT INTO stem_status(
                episode_id, talent_id, character_id,
                status, note, updated_at
            ) VALUES(?, ?, ?, 'REVISION', 'fix', '2026-08-27T13:00:00')
            """,
            (episode, talent, character),
        )


def test_dashboard_builds_actionable_work_queue_and_recent_audit(tmp_path):
    database = Database(tmp_path / "project.db")
    _seed(database)

    output = tmp_path / "output"
    delivery = tmp_path / "delivery"
    output.mkdir()
    delivery.mkdir()

    AuditService(database).record(
        event_type="DATA",
        action="TEST",
        summary="Recent test activity.",
    )

    snapshot = ProjectDashboardService(
        database,
        ProjectSettings(
            stem_output_folder=str(output),
            delivery_folder=str(delivery),
        ),
    ).build()

    assert snapshot.needs_review == 1
    assert snapshot.recording_episodes == 1
    assert snapshot.revisions == 1
    assert snapshot.total_tracks == 1
    assert snapshot.recent_activity
    assert snapshot.recent_activity[0].summary == "Recent test activity."

    keys = {action.key for action in snapshot.actions}
    assert "needs_review" in keys
    assert "recording" in keys
    assert "revision" in keys


def test_project_dashboard_ui_exposes_clickable_next_actions():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    page = (root / "pages" / "project_page.py").read_text(encoding="utf-8")
    main = (root / "app" / "main_window.py").read_text(encoding="utf-8")

    assert "action_requested = Signal(str)" in page
    assert '"WHAT NEEDS ATTENTION"' in page
    assert '"RECENT ACTIVITY"' in page
    assert "self.action_requested.emit(key)" in page

    assert "handle_project_dashboard_action" in main
    assert 'page.show_section("Unresolved")' in main
    assert 'page.show_section("Validation")' in main
    assert 'self.ribbon.select_tab("TRACKING")' in main


def test_source_preview_dialog_is_read_only_until_apply():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    dialog = (
        root / "dialogs" / "source_refresh_preview_dialog.py"
    ).read_text(encoding="utf-8")
    main = (root / "app" / "main_window.py").read_text(encoding="utf-8")
    worker = (root / "app" / "source_sync_worker.py").read_text(
        encoding="utf-8"
    )

    assert "Database belum diubah" in dialog
    assert '"Apply Refresh"' in dialog
    assert "_source_sync_prepared" in main
    assert "_pending_source_apply_report" in main
    assert 'operation="apply"' in main
    assert 'self._operation == "prepare"' in worker
    assert 'self._operation == "apply"' in worker
