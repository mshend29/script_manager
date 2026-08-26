from core.database import Database, SCHEMA_VERSION
from services.review_service import ReviewService
from services.validation_service import (
    ACTION_REVIEW,
    REVIEW,
    SYSTEM,
    ValidationService,
)


def _seed_review_case(database: Database) -> dict[str, int]:
    database.initialize()
    with database.connect() as connection:
        source_id = connection.execute(
            """
            INSERT INTO source_files(
                file_path, file_name, episode_number,
                fingerprint, is_active, imported_at, last_seen_at
            ) VALUES(
                'ep53.xlsx', 'ep53.xlsx', 53,
                'fp53', 1, '2026-08-26T09:00:00', '2026-08-26T09:00:00'
            )
            """
        ).lastrowid
        episode_id = connection.execute(
            """
            INSERT INTO episodes(
                episode_number, source_file_id, title, is_active
            ) VALUES(53, ?, 'EP 53', 1)
            """,
            (source_id,),
        ).lastrowid
        dialogue_id = connection.execute(
            """
            INSERT INTO dialogues(
                dialog_uid, episode_id, source_file_id,
                time_in, time_out, dialog_text, source_row, is_active
            ) VALUES(
                'uid-narration', ?, ?, '00:00:10,000', '00:00:12,000',
                'Setengah bulan kemudian', 16, 1
            )
            """,
            (episode_id, source_id),
        ).lastrowid
    return {
        "source": int(source_id),
        "episode": int(episode_id),
        "dialogue": int(dialogue_id),
    }


def test_current_schema_preserves_dialogue_review_table(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()

    with database.connect() as connection:
        schema = connection.execute(
            "SELECT value FROM app_meta WHERE key = 'schema_version'"
        ).fetchone()["value"]
        table = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name = 'dialogue_review'
            """
        ).fetchone()

    assert schema == str(SCHEMA_VERSION)
    assert table is not None


def test_v3_database_is_upgraded_to_review_schema_without_losing_data(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed_review_case(database)

    with database.connect() as connection:
        connection.execute("DROP TABLE dialogue_review")
        connection.execute(
            "UPDATE app_meta SET value = '3' WHERE key = 'schema_version'"
        )

    database.initialize()

    with database.connect() as connection:
        dialogue = connection.execute(
            "SELECT dialog_text FROM dialogues WHERE id = ?",
            (ids["dialogue"],),
        ).fetchone()
        table = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name = 'dialogue_review'
            """
        ).fetchone()
        version = connection.execute(
            "SELECT value FROM app_meta WHERE key = 'schema_version'"
        ).fetchone()["value"]

    assert dialogue["dialog_text"] == "Setengah bulan kemudian"
    assert table is not None
    assert version == str(SCHEMA_VERSION)


def test_missing_character_becomes_non_dialogue_and_can_be_restored(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed_review_case(database)
    review = ReviewService(database)
    validator = ValidationService(database)

    before = validator.validate()
    missing = [issue for issue in before if issue.code == "MISSING_CHARACTER"]
    assert len(missing) == 1
    assert missing[0].category == REVIEW
    assert missing[0].action == ACTION_REVIEW
    assert missing[0].episode_number == 53

    review.mark_non_dialogue(ids["dialogue"])

    after = validator.validate()
    assert not any(issue.code == "MISSING_CHARACTER" for issue in after)
    reviewed = review.get_non_dialogues()
    assert len(reviewed) == 1
    assert reviewed[0].dialogue == "Setengah bulan kemudian"
    assert ids["dialogue"] in review.get_active_non_dialogue_ids()

    with database.connect() as connection:
        dialogue = connection.execute(
            "SELECT is_active, dialog_text FROM dialogues WHERE id = ?",
            (ids["dialogue"],),
        ).fetchone()
    assert int(dialogue["is_active"]) == 1
    assert dialogue["dialog_text"] == "Setengah bulan kemudian"

    review.restore_to_review(ids["dialogue"])
    restored = validator.validate()
    assert any(issue.code == "MISSING_CHARACTER" for issue in restored)


def test_non_dialogue_rejects_rows_that_already_have_cast(tmp_path):
    database = Database(tmp_path / "project.db")
    ids = _seed_review_case(database)
    review = ReviewService(database)

    with database.connect() as connection:
        character_id = connection.execute(
            """
            INSERT INTO characters(name, normalized_name, is_active)
            VALUES('Narator', 'narator', 1)
            """
        ).lastrowid
        connection.execute(
            """
            INSERT INTO dialog_cast(dialogue_id, character_id, talent_id, position)
            VALUES(?, ?, NULL, 0)
            """,
            (ids["dialogue"], character_id),
        )

    try:
        review.mark_non_dialogue(ids["dialogue"])
    except ValueError as exc:
        assert "tanpa character/cast" in str(exc)
    else:
        raise AssertionError("mark_non_dialogue should reject a cast row")


def test_validation_separates_system_and_human_review(tmp_path):
    database = Database(tmp_path / "project.db")
    _seed_review_case(database)
    validator = ValidationService(database)

    issues = validator.validate()
    summary = validator.summarize(issues)

    assert summary.system_errors == 0
    assert summary.needs_review == 1
    assert summary.workflow_warnings == 0
    assert all(issue.category != SYSTEM for issue in issues)
