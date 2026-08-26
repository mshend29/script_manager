from __future__ import annotations

from pathlib import Path

from core.database import Database
from services.alias_service import CharacterAliasService
from services.alias_validation_service import AliasValidationService


ROOT = Path(__file__).resolve().parents[1]


def test_alias_ui_is_manual_reversible_and_source_safe():
    page = (ROOT / "pages" / "alias_data_page.py").read_text(encoding="utf-8")
    main = (ROOT / "main.py").read_text(encoding="utf-8")

    assert '"ALIASES"' in page
    assert 'QPushButton("Set as Alias of…")' in page
    assert 'QPushButton("Restore Selected Alias")' in page
    assert "self._alias_service.set_alias" in page
    assert "self._alias_service.restore_alias" in page
    assert "Source Excel dan label di SCRIPT tidak diubah" in page
    assert "AliasMainWindow" in main


def test_alias_service_rejects_chains(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    with database.connect() as connection:
        a = connection.execute(
            "INSERT INTO characters(name, normalized_name, is_active) VALUES('A', 'a', 1)"
        ).lastrowid
        b = connection.execute(
            "INSERT INTO characters(name, normalized_name, is_active) VALUES('B', 'b', 1)"
        ).lastrowid
        c = connection.execute(
            "INSERT INTO characters(name, normalized_name, is_active) VALUES('C', 'c', 1)"
        ).lastrowid

    service = CharacterAliasService(database)
    service.set_alias(source_character_id=int(a), canonical_character_id=int(b))

    try:
        service.set_alias(source_character_id=int(c), canonical_character_id=int(a))
    except ValueError as exc:
        assert "Target merupakan alias" in str(exc)
    else:
        raise AssertionError("Alias chain should be rejected")


def test_validation_detects_external_alias_chain_and_alias_aware_downstream(tmp_path):
    database = Database(tmp_path / "project.db")
    database.initialize()
    with database.connect() as connection:
        source = connection.execute(
            "INSERT INTO source_files(file_path, file_name, episode_number, is_active) VALUES('ep1.xlsx', 'ep1.xlsx', 1, 1)"
        ).lastrowid
        episode = connection.execute(
            "INSERT INTO episodes(episode_number, source_file_id, is_active) VALUES(1, ?, 1)",
            (source,),
        ).lastrowid
        a = connection.execute(
            "INSERT INTO characters(name, normalized_name, is_active) VALUES('Alias A', 'alias a', 1)"
        ).lastrowid
        b = connection.execute(
            "INSERT INTO characters(name, normalized_name, is_active) VALUES('Canonical B', 'canonical b', 1)"
        ).lastrowid
        c = connection.execute(
            "INSERT INTO characters(name, normalized_name, is_active) VALUES('Canonical C', 'canonical c', 1)"
        ).lastrowid
        talent = connection.execute(
            "INSERT INTO talents(name, normalized_name, is_active) VALUES('Talent', 'talent', 1)"
        ).lastrowid
        dialogue = connection.execute(
            """
            INSERT INTO dialogues(
                dialog_uid, episode_id, source_file_id, dialog_text, source_row, is_active
            ) VALUES('alias-validation', ?, ?, 'Line', 3, 1)
            """,
            (episode, source),
        ).lastrowid
        connection.execute(
            "INSERT INTO dialog_cast(dialogue_id, character_id, talent_id, position) VALUES(?, ?, ?, 0)",
            (dialogue, a, talent),
        )

        # Simulate corruption/manual DB editing that bypasses AliasService.
        connection.execute(
            """
            INSERT INTO character_alias(
                source_character_id, canonical_character_id,
                alias_name, normalized_alias
            ) VALUES(?, ?, 'Alias A', 'alias a')
            """,
            (a, b),
        )
        connection.execute(
            """
            INSERT INTO character_alias(
                source_character_id, canonical_character_id,
                alias_name, normalized_alias
            ) VALUES(?, ?, 'Canonical B', 'canonical b')
            """,
            (b, c),
        )
        connection.execute(
            """
            INSERT INTO stem_status(
                episode_id, talent_id, character_id, status
            ) VALUES(?, ?, ?, 'DELIVERED')
            """,
            (episode, talent, b),
        )

    issues = AliasValidationService(database).validate()
    codes = [issue.code for issue in issues]
    assert "ALIAS_CHAIN" in codes
    assert "DOWNSTREAM_BEFORE_RECORDED" in codes
