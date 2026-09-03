from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import uuid

from core.database import Database
from import_engine.parser import ParsedDialogueRow, ScriptParseResult
from import_engine.resolver import CharacterTalentResolver
from import_engine.scanner import SourceScanResult
from import_engine.source_change_plan import (
    SourceChangePlan,
    SourceChangePlanBuilder,
)


@dataclass(frozen=True)
class TrackingScope:
    episode_id: int
    episode_number: int
    talent_id: int
    character_id: int


@dataclass(frozen=True)
class TrackingInvalidation:
    episode_id: int
    episode_number: int
    talent_id: int
    talent_name: str
    character_id: int
    character_name: str
    reasons: tuple[str, ...]


@dataclass
class DialogueSyncReport:
    dialogues_added: int = 0
    dialogues_updated: int = 0
    dialogues_reactivated: int = 0
    dialogues_deactivated: int = 0
    cast_links: int = 0
    auto_locked: int = 0
    unresolved_cast: int = 0
    tracking_invalidations: list[TrackingInvalidation] = field(
        default_factory=list
    )
    warnings: list[str] = field(default_factory=list)


class DialogueSynchronizer:
    """Apply an already-reconciled source plan in one SQLite transaction."""

    def synchronize(
        self,
        *,
        database: Database,
        scan: SourceScanResult,
        parse_results: dict[str, ScriptParseResult],
        synced_at: str,
        plan: SourceChangePlan | None = None,
    ) -> DialogueSyncReport:
        report = DialogueSyncReport()

        if plan is None:
            plan = SourceChangePlanBuilder(database).build(
                scan=scan,
                parse_results=parse_results,
            )

        if plan.has_ambiguities:
            raise RuntimeError(
                "Source refresh memiliki dialogue lineage ambigu:\n"
                + "\n".join(plan.ambiguity_messages)
            )

        with database.connect() as connection:
            current_token = SourceChangePlanBuilder.compute_database_token(
                connection
            )
            if current_token != plan.database_token:
                raise RuntimeError(
                    "Database berubah setelah Source Change Plan dibuat. "
                    "Jalankan Source Sync lagi."
                )

            pending_tracking: dict[TrackingScope, set[str]] = {}

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
            # SOURCES THAT DISAPPEARED — EXACTLY AS PLANNED
            # -------------------------------------------------

            for missing in plan.missing_sources:
                old_scopes = self._dialogue_scopes(
                    connection,
                    missing.active_dialogue_ids,
                )
                for scopes in old_scopes.values():
                    self._queue_tracking_invalidation(
                        pending_tracking,
                        scopes,
                        "SOURCE_MISSING",
                    )

                if missing.active_dialogue_ids:
                    placeholders = ",".join(
                        "?" for _ in missing.active_dialogue_ids
                    )
                    connection.execute(
                        f"""
                        UPDATE dialogues
                        SET is_active = 0,
                            updated_at = ?
                        WHERE id IN ({placeholders})
                          AND is_active = 1
                        """,
                        (synced_at, *missing.active_dialogue_ids),
                    )
                    report.dialogues_deactivated += len(
                        missing.active_dialogue_ids
                    )

                connection.execute(
                    """
                    UPDATE source_files
                    SET is_active = 0,
                        last_seen_at = ?
                    WHERE id = ?
                    """,
                    (synced_at, missing.source_file_id),
                )

                connection.execute(
                    """
                    UPDATE episodes
                    SET is_active = 0
                    WHERE source_file_id = ?
                    """,
                    (missing.source_file_id,),
                )

            # -------------------------------------------------
            # UPSERT SOURCE FILES + EPISODES
            # -------------------------------------------------

            source_context: dict[str, tuple[int, int]] = {}

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
            # DIALOGUES — EXECUTE THE APPROVED PLAN
            # -------------------------------------------------

            for file_path, file_plan in plan.file_plans.items():
                source_file_id, episode_id = source_context[file_path]

                old_ids = [
                    int(match.existing.dialogue_id)
                    for match in file_plan.matches
                ] + [
                    int(old.dialogue_id)
                    for old in file_plan.removals
                ]
                old_scopes = self._dialogue_scopes(
                    connection,
                    old_ids,
                )

                for old in file_plan.removals:
                    dialogue_id = int(old.dialogue_id)
                    self._queue_tracking_invalidation(
                        pending_tracking,
                        old_scopes.get(dialogue_id, set()),
                        "DIALOG_REMOVED",
                    )
                    if not old.is_active:
                        continue
                    cursor = connection.execute(
                        """
                        UPDATE dialogues
                        SET is_active = 0,
                            updated_at = ?
                        WHERE id = ?
                          AND is_active = 1
                        """,
                        (synced_at, dialogue_id),
                    )
                    if int(cursor.rowcount or 0) > 0:
                        report.dialogues_deactivated += 1

                work_rows: list[tuple[int, ParsedDialogueRow]] = []
                matched_rows: list[tuple[int, object]] = []
                added_ids: list[int] = []

                for match in file_plan.matches:
                    parsed_row = match.parsed
                    dialogue_id = int(match.existing.dialogue_id)
                    was_active = bool(match.existing.is_active)

                    connection.execute(
                        """
                        UPDATE dialogues
                        SET source_signature = ?,
                            episode_id = ?,
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
                            parsed_row.source_signature,
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
                    work_rows.append((dialogue_id, parsed_row))
                    matched_rows.append((dialogue_id, match))

                for parsed_row in file_plan.additions:
                    dialog_uid = self._allocate_dialog_uid(
                        connection,
                        parsed_row.source_signature,
                    )
                    cursor = connection.execute(
                        """
                        INSERT INTO dialogues(
                            dialog_uid,
                            source_signature,
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
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                        """,
                        (
                            dialog_uid,
                            parsed_row.source_signature,
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
                    work_rows.append((dialogue_id, parsed_row))
                    added_ids.append(dialogue_id)

                for dialogue_id, parsed_row in work_rows:
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

                    self._rebuild_cast(
                        connection=connection,
                        resolver=resolver,
                        dialogue_id=dialogue_id,
                        parsed_row=parsed_row,
                        episode_number=file_plan.episode_number,
                        timestamp=synced_at,
                        report=report,
                    )

                new_ids = [
                    dialogue_id for dialogue_id, _match in matched_rows
                ] + added_ids
                new_scopes = self._dialogue_scopes(
                    connection,
                    new_ids,
                )

                for dialogue_id in added_ids:
                    self._queue_tracking_invalidation(
                        pending_tracking,
                        new_scopes.get(dialogue_id, set()),
                        "DIALOG_ADDED",
                    )

                for dialogue_id, match in matched_rows:
                    before = old_scopes.get(dialogue_id, set())
                    after = new_scopes.get(dialogue_id, set())
                    signature_changed = (
                        match.existing.source_signature
                        != match.parsed.source_signature
                    )

                    if signature_changed:
                        self._queue_tracking_invalidation(
                            pending_tracking,
                            before | after,
                            "SOURCE_REVISED",
                        )
                    elif before != after:
                        self._queue_tracking_invalidation(
                            pending_tracking,
                            before | after,
                            "CAST_CHANGED",
                        )

            self._apply_tracking_invalidations(
                connection,
                pending_tracking,
                report,
            )

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

    @staticmethod
    def _queue_tracking_invalidation(
        pending: dict[TrackingScope, set[str]],
        scopes: set[TrackingScope],
        reason: str,
    ) -> None:
        for scope in scopes:
            pending.setdefault(scope, set()).add(str(reason))

    @staticmethod
    def _dialogue_scopes(
        connection,
        dialogue_ids,
    ) -> dict[int, set[TrackingScope]]:
        ids = sorted({int(value) for value in dialogue_ids})
        if not ids:
            return {}

        placeholders = ",".join("?" for _ in ids)
        rows = connection.execute(
            f"""
            SELECT DISTINCT
                d.id AS dialogue_id,
                e.id AS episode_id,
                e.episode_number,
                dc.talent_id,
                dc.character_id
            FROM dialogues AS d
            JOIN episodes AS e ON e.id = d.episode_id
            JOIN dialog_cast AS dc ON dc.dialogue_id = d.id
            WHERE d.id IN ({placeholders})
              AND dc.talent_id IS NOT NULL
            """,
            ids,
        ).fetchall()

        result: dict[int, set[TrackingScope]] = {}
        for row in rows:
            dialogue_id = int(row["dialogue_id"])
            result.setdefault(dialogue_id, set()).add(
                TrackingScope(
                    episode_id=int(row["episode_id"]),
                    episode_number=int(row["episode_number"]),
                    talent_id=int(row["talent_id"]),
                    character_id=int(row["character_id"]),
                )
            )
        return result

    @staticmethod
    def _apply_tracking_invalidations(
        connection,
        pending: dict[TrackingScope, set[str]],
        report: DialogueSyncReport,
    ) -> None:
        for scope, reasons in sorted(
            pending.items(),
            key=lambda item: (
                item[0].episode_number,
                item[0].talent_id,
                item[0].character_id,
            ),
        ):
            cursor = connection.execute(
                """
                DELETE FROM stem_status
                WHERE episode_id = ?
                  AND talent_id = ?
                  AND character_id = ?
                  AND status IN ('READY_TO_STEM', 'STEMMED', 'DELIVERED')
                """,
                (
                    scope.episode_id,
                    scope.talent_id,
                    scope.character_id,
                ),
            )
            if int(cursor.rowcount or 0) <= 0:
                continue

            labels = connection.execute(
                """
                SELECT
                    c.name AS character_name,
                    t.name AS talent_name
                FROM characters AS c
                JOIN talents AS t ON t.id = ?
                WHERE c.id = ?
                """,
                (scope.talent_id, scope.character_id),
            ).fetchone()

            character_name = (
                str(labels["character_name"])
                if labels is not None
                else f"Character {scope.character_id}"
            )
            talent_name = (
                str(labels["talent_name"])
                if labels is not None
                else f"Talent {scope.talent_id}"
            )
            reason_tuple = tuple(sorted(reasons))
            report.tracking_invalidations.append(
                TrackingInvalidation(
                    episode_id=scope.episode_id,
                    episode_number=scope.episode_number,
                    talent_id=scope.talent_id,
                    talent_name=talent_name,
                    character_id=scope.character_id,
                    character_name=character_name,
                    reasons=reason_tuple,
                )
            )
            report.warnings.append(
                f"Episode {scope.episode_number}: tracking downstream "
                f"{character_name} / {talent_name} direset "
                f"({', '.join(reason_tuple)})."
            )

    @staticmethod
    def _allocate_dialog_uid(connection, source_signature: str) -> str:
        preferred = str(source_signature or "").strip()
        if not preferred:
            preferred = f"dlg-{uuid.uuid4().hex}"

        exists = connection.execute(
            "SELECT 1 FROM dialogues WHERE dialog_uid = ?",
            (preferred,),
        ).fetchone()
        if exists is None:
            return preferred

        while True:
            candidate = f"{preferred}:{uuid.uuid4().hex[:12]}"
            exists = connection.execute(
                "SELECT 1 FROM dialogues WHERE dialog_uid = ?",
                (candidate,),
            ).fetchone()
            if exists is None:
                return candidate

    @staticmethod
    def _rebuild_cast(
        *,
        connection,
        resolver: CharacterTalentResolver,
        dialogue_id: int,
        parsed_row: ParsedDialogueRow,
        episode_number: int,
        timestamp: str,
        report: DialogueSyncReport,
    ) -> None:
        connection.execute(
            "DELETE FROM character_alias_dialogue WHERE dialogue_id = ?",
            (dialogue_id,),
        )
        connection.execute(
            "DELETE FROM dialog_source_cast WHERE dialogue_id = ?",
            (dialogue_id,),
        )
        connection.execute(
            "DELETE FROM dialog_cast WHERE dialogue_id = ?",
            (dialogue_id,),
        )

        source_cast, _source_warnings = resolver.resolve_row(
            parsed_row,
            timestamp=timestamp,
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
            timestamp=timestamp,
            apply_manual_overrides=True,
        )
        report.warnings.extend(
            f"Episode {episode_number} row "
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
