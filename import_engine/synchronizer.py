from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.database import Database
from import_engine.parser import ScriptParseResult
from import_engine.resolver import CharacterTalentResolver
from import_engine.scanner import SourceScanResult


@dataclass
class DialogueSyncReport:
    dialogues_added: int = 0
    dialogues_updated: int = 0
    dialogues_reactivated: int = 0
    dialogues_deactivated: int = 0
    cast_links: int = 0
    auto_locked: int = 0
    unresolved_cast: int = 0
    warnings: list[str] = field(default_factory=list)


class DialogueSynchronizer:
    """Synchronize source metadata and parsed dialogues in one SQLite transaction."""

    def synchronize(
        self,
        *,
        database: Database,
        scan: SourceScanResult,
        parse_results: dict[str, ScriptParseResult],
        synced_at: str,
    ) -> DialogueSyncReport:
        report = DialogueSyncReport()
        scanned_by_path = {item.file_path: item for item in scan.files}

        with database.connect() as connection:
            existing_source_rows = connection.execute(
                """
                SELECT
                    id,
                    file_path,
                    fingerprint,
                    is_active
                FROM source_files
                """
            ).fetchall()
            existing_by_path = {
                str(row["file_path"]): row for row in existing_source_rows
            }

            # -------------------------------------------------
            # SOURCES THAT DISAPPEARED
            # -------------------------------------------------

            missing_paths = set(existing_by_path) - set(scanned_by_path)

            for file_path in missing_paths:
                source_row = existing_by_path[file_path]
                source_file_id = int(source_row["id"])

                active_dialogues = connection.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM dialogues
                    WHERE source_file_id = ? AND is_active = 1
                    """,
                    (source_file_id,),
                ).fetchone()
                report.dialogues_deactivated += int(
                    active_dialogues["total"] if active_dialogues else 0
                )

                connection.execute(
                    """
                    UPDATE dialogues
                    SET is_active = 0,
                        updated_at = ?
                    WHERE source_file_id = ?
                      AND is_active = 1
                    """,
                    (synced_at, source_file_id),
                )

                connection.execute(
                    """
                    UPDATE source_files
                    SET is_active = 0,
                        last_seen_at = ?
                    WHERE id = ?
                    """,
                    (synced_at, source_file_id),
                )

                connection.execute(
                    """
                    UPDATE episodes
                    SET is_active = 0
                    WHERE source_file_id = ?
                    """,
                    (source_file_id,),
                )

            # -------------------------------------------------
            # UPSERT SOURCE FILES + EPISODES
            # -------------------------------------------------

            source_context: dict[str, tuple[int, int]] = {}
            changed_episode_numbers: dict[int, int] = {}

            for item in scan.files:
                existing = existing_by_path.get(item.file_path)
                changed = False

                if existing is None:
                    cursor = connection.execute(
                        """
                        INSERT INTO source_files(
                            file_path,
                            file_name,
                            episode_number,
                            file_size,
                            modified_at,
                            fingerprint,
                            is_active,
                            imported_at,
                            last_seen_at
                        )
                        VALUES(?, ?, ?, ?, ?, ?, 1, ?, ?)
                        """,
                        (
                            item.file_path,
                            item.file_name,
                            item.episode_number,
                            item.file_size,
                            item.modified_at,
                            item.fingerprint,
                            synced_at,
                            synced_at,
                        ),
                    )
                    source_file_id = int(cursor.lastrowid)
                else:
                    source_file_id = int(existing["id"])
                    changed = (
                        str(existing["fingerprint"] or "")
                        != item.fingerprint
                    )

                    connection.execute(
                        """
                        UPDATE source_files
                        SET file_name = ?,
                            episode_number = ?,
                            file_size = ?,
                            modified_at = ?,
                            fingerprint = ?,
                            is_active = 1,
                            imported_at = CASE
                                WHEN ? THEN ?
                                ELSE imported_at
                            END,
                            last_seen_at = ?
                        WHERE id = ?
                        """,
                        (
                            item.file_name,
                            item.episode_number,
                            item.file_size,
                            item.modified_at,
                            item.fingerprint,
                            1 if changed else 0,
                            synced_at,
                            synced_at,
                            source_file_id,
                        ),
                    )

                connection.execute(
                    """
                    INSERT INTO episodes(
                        episode_number,
                        source_file_id,
                        title,
                        is_active
                    )
                    VALUES(?, ?, ?, 1)
                    ON CONFLICT(episode_number)
                    DO UPDATE SET
                        source_file_id = excluded.source_file_id,
                        title = excluded.title,
                        is_active = 1
                    """,
                    (
                        item.episode_number,
                        source_file_id,
                        Path(item.file_name).stem,
                    ),
                )

                episode_row = connection.execute(
                    """
                    SELECT id
                    FROM episodes
                    WHERE episode_number = ?
                    """,
                    (item.episode_number,),
                ).fetchone()
                episode_id = int(episode_row["id"])
                source_context[item.file_path] = (
                    source_file_id,
                    episode_id,
                )

                if changed:
                    changed_episode_numbers[episode_id] = item.episode_number

            # A changed source invalidates downstream approval for that episode.
            # Recording checkboxes remain untouched. REVISION is deliberately
            # preserved because it already represents work that needs attention.
            for episode_id, episode_number in changed_episode_numbers.items():
                cursor = connection.execute(
                    """
                    DELETE FROM stem_status
                    WHERE episode_id = ?
                      AND status IN ('READY_TO_STEM', 'STEMMED', 'DELIVERED')
                    """,
                    (episode_id,),
                )
                invalidated = max(int(cursor.rowcount or 0), 0)
                if invalidated:
                    report.warnings.append(
                        f"Episode {episode_number}: {invalidated} status tracking "
                        "downstream direset karena source berubah."
                    )

            # -------------------------------------------------
            # RESOLVER PREPARATION + AUTO-LOCK LEARNING
            # -------------------------------------------------

            resolver = CharacterTalentResolver(connection)
            parsed_values = list(parse_results.values())
            resolver.ensure_entities(parsed_values, timestamp=synced_at)
            resolver_report = resolver.learn_from_single_rows(
                parsed_values,
                timestamp=synced_at,
            )
            report.auto_locked += resolver_report.auto_locked
            report.warnings.extend(resolver_report.warnings)

            # -------------------------------------------------
            # DIALOGUES FOR NEW / CHANGED FILES ONLY
            # -------------------------------------------------

            for file_path, parse_result in parse_results.items():
                source_file_id, episode_id = source_context[file_path]

                existing_dialogues = connection.execute(
                    """
                    SELECT id, dialog_uid, is_active
                    FROM dialogues
                    WHERE source_file_id = ?
                       OR episode_id = ?
                    """,
                    (source_file_id, episode_id),
                ).fetchall()
                existing_by_uid = {
                    str(row["dialog_uid"]): row for row in existing_dialogues
                }
                current_uids = {row.dialog_uid for row in parse_result.rows}

                for existing_dialogue in existing_dialogues:
                    uid = str(existing_dialogue["dialog_uid"])
                    if uid in current_uids:
                        continue
                    if int(existing_dialogue["is_active"] or 0) != 1:
                        continue

                    connection.execute(
                        """
                        UPDATE dialogues
                        SET is_active = 0,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (synced_at, int(existing_dialogue["id"])),
                    )
                    report.dialogues_deactivated += 1

                for parsed_row in parse_result.rows:
                    existing_dialogue = existing_by_uid.get(parsed_row.dialog_uid)

                    if existing_dialogue is None:
                        cursor = connection.execute(
                            """
                            INSERT INTO dialogues(
                                dialog_uid,
                                episode_id,
                                source_file_id,
                                time_in,
                                time_out,
                                dialog_text,
                                source_row,
                                is_active,
                                created_at,
                                updated_at
                            )
                            VALUES(?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                            """,
                            (
                                parsed_row.dialog_uid,
                                episode_id,
                                source_file_id,
                                parsed_row.time_in,
                                parsed_row.time_out,
                                parsed_row.dialogue,
                                parsed_row.source_row,
                                synced_at,
                                synced_at,
                            ),
                        )
                        dialogue_id = int(cursor.lastrowid)
                        report.dialogues_added += 1
                    else:
                        dialogue_id = int(existing_dialogue["id"])
                        was_active = int(existing_dialogue["is_active"] or 0) == 1

                        connection.execute(
                            """
                            UPDATE dialogues
                            SET episode_id = ?,
                                source_file_id = ?,
                                time_in = ?,
                                time_out = ?,
                                dialog_text = ?,
                                source_row = ?,
                                is_active = 1,
                                updated_at = ?
                            WHERE id = ?
                            """,
                            (
                                episode_id,
                                source_file_id,
                                parsed_row.time_in,
                                parsed_row.time_out,
                                parsed_row.dialogue,
                                parsed_row.source_row,
                                synced_at,
                                dialogue_id,
                            ),
                        )
                        report.dialogues_updated += 1
                        if not was_active:
                            report.dialogues_reactivated += 1

                    # Recording state is intentionally insert-only.
                    # Existing rows keep their checkbox state across Refresh.
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO recording_status(
                            dialogue_id,
                            is_recorded,
                            recorded_at,
                            updated_at
                        )
                        VALUES(?, 0, NULL, ?)
                        """,
                        (dialogue_id, synced_at),
                    )

                    # Rebuild source provenance, effective cast and alias
                    # provenance together. dialog_source_cast intentionally
                    # ignores manual Character Mapping so Unlock can restore
                    # the latest source/resolver baseline.
                    connection.execute(
                        "DELETE FROM character_alias_dialogue WHERE dialogue_id = ?",
                        (dialogue_id,),
                    )
                    connection.execute(
                        "DELETE FROM dialog_source_cast WHERE dialogue_id = ?",
                        (dialogue_id,),
                    )
                    connection.execute(
                        """
                        DELETE FROM dialog_cast
                        WHERE dialogue_id = ?
                        """,
                        (dialogue_id,),
                    )

                    source_cast, _source_warnings = resolver.resolve_row(
                        parsed_row,
                        timestamp=synced_at,
                        apply_manual_overrides=False,
                    )
                    for position, cast_member in enumerate(source_cast):
                        connection.execute(
                            """
                            INSERT INTO dialog_source_cast(
                                dialogue_id,
                                character_id,
                                talent_id,
                                position,
                                resolution_source
                            )
                            VALUES(?, ?, ?, ?, ?)
                            """,
                            (
                                dialogue_id,
                                cast_member.character_id,
                                cast_member.talent_id,
                                position,
                                cast_member.source,
                            ),
                        )

                    resolved_cast, cast_warnings = resolver.resolve_row(
                        parsed_row,
                        timestamp=synced_at,
                        apply_manual_overrides=True,
                    )
                    report.warnings.extend(
                        f"Episode {parse_result.episode_number} row "
                        f"{parsed_row.source_row}: {warning}"
                        for warning in cast_warnings
                    )

                    for position, cast_member in enumerate(resolved_cast):
                        connection.execute(
                            """
                            INSERT INTO dialog_cast(
                                dialogue_id,
                                character_id,
                                talent_id,
                                position
                            )
                            VALUES(?, ?, ?, ?)
                            """,
                            (
                                dialogue_id,
                                cast_member.character_id,
                                cast_member.talent_id,
                                position,
                            ),
                        )

                        for alias_id in cast_member.alias_ids:
                            connection.execute(
                                """
                                INSERT INTO character_alias_dialogue(
                                    alias_id,
                                    dialogue_id,
                                    talent_id,
                                    position,
                                    created_canonical
                                ) VALUES(?, ?, ?, ?, 1)
                                """,
                                (
                                    int(alias_id),
                                    dialogue_id,
                                    cast_member.talent_id,
                                    position,
                                ),
                            )

                        report.cast_links += 1
                        if cast_member.talent_id is None:
                            report.unresolved_cast += 1

            connection.execute(
                """
                INSERT INTO app_meta(key, value)
                VALUES('last_source_sync_at', ?)
                ON CONFLICT(key)
                DO UPDATE SET value = excluded.value
                """,
                (synced_at,),
            )

        return report
