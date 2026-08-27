from __future__ import annotations

from dataclasses import dataclass, field

from core.database import Database
from import_engine.normalizer import normalize_key
from import_engine.parser import ParsedDialogueRow, ScriptParseResult
from import_engine.scanner import SourceScanResult


@dataclass(frozen=True)
class SourceChangeItem:
    change_type: str
    episode_number: int
    source_row: int | None
    entity: str
    before: str
    after: str
    recording_affected: bool = False
    tracking_affected: bool = False


@dataclass
class SourceChangePreview:
    source_added: int = 0
    source_changed: int = 0
    source_restored: int = 0
    source_missing: int = 0
    dialogues_added: int = 0
    dialogues_removed: int = 0
    text_changed: int = 0
    cast_changed: int = 0
    recording_affected: int = 0
    tracking_affected: int = 0
    items: list[SourceChangeItem] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return any(
            (
                self.source_added,
                self.source_changed,
                self.source_restored,
                self.source_missing,
                self.dialogues_added,
                self.dialogues_removed,
                self.text_changed,
                self.cast_changed,
            )
        )

    @property
    def changed_episodes(self) -> int:
        return len(
            {
                item.episode_number
                for item in self.items
                if item.episode_number > 0
            }
        )


class SourceChangeService:
    """Build a read-only source refresh diff before database synchronization."""

    def __init__(self, database: Database):
        self.database = database

    def build(
        self,
        *,
        scan: SourceScanResult,
        parse_results: dict[str, ScriptParseResult],
    ) -> SourceChangePreview:
        preview = SourceChangePreview()
        scanned_by_path = {item.file_path: item for item in scan.files}

        with self.database.connect() as connection:
            sources = connection.execute(
                """
                SELECT
                    id,
                    file_path,
                    fingerprint,
                    is_active,
                    episode_number
                FROM source_files
                """
            ).fetchall()
            source_by_path = {
                str(row["file_path"]): row
                for row in sources
            }

            for path, source in source_by_path.items():
                if path in scanned_by_path:
                    continue
                if int(source["is_active"] or 0) != 1:
                    continue
                preview.source_missing += 1
                episode = int(source["episode_number"] or 0)
                preview.items.append(
                    SourceChangeItem(
                        change_type="SOURCE_MISSING",
                        episode_number=episode,
                        source_row=None,
                        entity="Source",
                        before=path,
                        after="File tidak ditemukan",
                        tracking_affected=self._episode_has_tracking(
                            connection,
                            episode,
                        ),
                    )
                )

            for item in scan.files:
                existing = source_by_path.get(item.file_path)
                if existing is None:
                    preview.source_added += 1
                elif (
                    str(existing["fingerprint"] or "")
                    != str(item.fingerprint or "")
                ):
                    preview.source_changed += 1
                elif int(existing["is_active"] or 0) != 1:
                    preview.source_restored += 1

            for file_path, parse_result in parse_results.items():
                existing_source = source_by_path.get(file_path)
                if existing_source is None:
                    for row in parse_result.rows:
                        preview.dialogues_added += 1
                        preview.items.append(
                            SourceChangeItem(
                                change_type="DIALOG_ADDED",
                                episode_number=int(
                                    parse_result.episode_number
                                ),
                                source_row=int(row.source_row),
                                entity=self._new_cast_text(row),
                                before="",
                                after=row.dialogue,
                            )
                        )
                    continue

                source_id = int(existing_source["id"])
                old_rows = connection.execute(
                    """
                    SELECT
                        d.id,
                        d.dialog_uid,
                        d.dialog_text,
                        d.source_row,
                        d.episode_id,
                        e.episode_number,
                        COALESCE(rs.is_recorded, 0) AS is_recorded
                    FROM dialogues AS d
                    JOIN episodes AS e ON e.id = d.episode_id
                    LEFT JOIN recording_status AS rs
                      ON rs.dialogue_id = d.id
                    WHERE d.source_file_id = ?
                      AND d.is_active = 1
                    ORDER BY d.source_row, d.id
                    """,
                    (source_id,),
                ).fetchall()

                old_by_uid = {
                    str(row["dialog_uid"]): row for row in old_rows
                }
                old_by_row = {
                    int(row["source_row"]): row
                    for row in old_rows
                    if row["source_row"] is not None
                }
                matched_old_ids: set[int] = set()

                for new_row in parse_result.rows:
                    old = old_by_uid.get(new_row.dialog_uid)
                    if old is not None:
                        matched_old_ids.add(int(old["id"]))
                        self._append_same_uid_cast_change(
                            preview,
                            connection,
                            old,
                            new_row,
                        )
                        continue

                    old = old_by_row.get(int(new_row.source_row))
                    if old is None:
                        preview.dialogues_added += 1
                        preview.items.append(
                            SourceChangeItem(
                                change_type="DIALOG_ADDED",
                                episode_number=int(
                                    parse_result.episode_number
                                ),
                                source_row=int(new_row.source_row),
                                entity=self._new_cast_text(new_row),
                                before="",
                                after=new_row.dialogue,
                            )
                        )
                        continue

                    matched_old_ids.add(int(old["id"]))
                    self._append_changed_row(
                        preview,
                        connection,
                        old,
                        new_row,
                    )

                for old in old_rows:
                    old_id = int(old["id"])
                    if old_id in matched_old_ids:
                        continue
                    preview.dialogues_removed += 1
                    recorded = bool(int(old["is_recorded"] or 0))
                    tracking = self._episode_id_has_tracking(
                        connection,
                        int(old["episode_id"]),
                    )
                    preview.recording_affected += int(recorded)
                    preview.tracking_affected += int(tracking)
                    preview.items.append(
                        SourceChangeItem(
                            change_type="DIALOG_REMOVED",
                            episode_number=int(old["episode_number"]),
                            source_row=(
                                int(old["source_row"])
                                if old["source_row"] is not None
                                else None
                            ),
                            entity=self._old_cast_text(
                                connection,
                                old_id,
                            ),
                            before=str(old["dialog_text"]),
                            after="",
                            recording_affected=recorded,
                            tracking_affected=tracking,
                        )
                    )

        preview.items.sort(
            key=lambda item: (
                item.episode_number,
                item.source_row if item.source_row is not None else -1,
                item.change_type,
                item.entity.casefold(),
            )
        )
        return preview

    def _append_same_uid_cast_change(
        self,
        preview: SourceChangePreview,
        connection,
        old,
        new_row: ParsedDialogueRow,
    ) -> None:
        before_talents = self._old_talent_keys(
            connection,
            int(old["id"]),
        )
        after_talents = {
            normalize_key(talent)
            for talent in new_row.talents
            if normalize_key(talent)
        }
        if before_talents == after_talents:
            return

        recorded = bool(int(old["is_recorded"] or 0))
        tracking = self._episode_id_has_tracking(
            connection,
            int(old["episode_id"]),
        )
        preview.cast_changed += 1
        preview.recording_affected += int(recorded)
        preview.tracking_affected += int(tracking)
        preview.items.append(
            SourceChangeItem(
                change_type="CAST_CHANGED",
                episode_number=int(old["episode_number"]),
                source_row=int(new_row.source_row),
                entity="Cast",
                before=self._old_cast_text(
                    connection,
                    int(old["id"]),
                ),
                after=self._new_cast_text(new_row),
                recording_affected=recorded,
                tracking_affected=tracking,
            )
        )

    def _append_changed_row(
        self,
        preview: SourceChangePreview,
        connection,
        old,
        new_row: ParsedDialogueRow,
    ) -> None:
        old_text = str(old["dialog_text"])
        text_changed = old_text.strip() != new_row.dialogue.strip()

        before_cast = self._old_cast_text(
            connection,
            int(old["id"]),
        )
        after_cast = self._new_cast_text(new_row)
        before_talents = self._old_talent_keys(
            connection,
            int(old["id"]),
        )
        after_talents = {
            normalize_key(talent)
            for talent in new_row.talents
            if normalize_key(talent)
        }
        cast_changed = before_talents != after_talents

        recorded = bool(int(old["is_recorded"] or 0))
        tracking = self._episode_id_has_tracking(
            connection,
            int(old["episode_id"]),
        )

        if text_changed:
            preview.text_changed += 1
        if cast_changed:
            preview.cast_changed += 1
        if not text_changed and not cast_changed:
            # UID can change because of source character spelling/timecode even
            # when the visible text/talent set is stable. Surface it as cast
            # identity change so the user still sees the affected source row.
            cast_changed = True
            preview.cast_changed += 1

        preview.recording_affected += int(recorded)
        preview.tracking_affected += int(tracking)

        change_type = (
            "TEXT_AND_CAST_CHANGED"
            if text_changed and cast_changed
            else "TEXT_CHANGED"
            if text_changed
            else "CAST_CHANGED"
        )
        before = old_text
        after = new_row.dialogue
        entity = f"{before_cast} → {after_cast}" if cast_changed else "Dialogue"

        preview.items.append(
            SourceChangeItem(
                change_type=change_type,
                episode_number=int(old["episode_number"]),
                source_row=int(new_row.source_row),
                entity=entity,
                before=before,
                after=after,
                recording_affected=recorded,
                tracking_affected=tracking,
            )
        )

    @staticmethod
    def _new_cast_text(row: ParsedDialogueRow) -> str:
        if row.cast_pairs:
            return ", ".join(
                f"{pair.character} / {pair.talent}"
                for pair in row.cast_pairs
            )
        characters = ", ".join(row.characters) or "Character Unknown"
        talents = ", ".join(row.talents) or "Talent Unknown"
        return f"{characters} / {talents}"

    @staticmethod
    def _old_cast_text(connection, dialogue_id: int) -> str:
        rows = connection.execute(
            """
            SELECT
                c.name AS character_name,
                COALESCE(t.name, 'Talent Unknown') AS talent_name
            FROM dialog_cast AS dc
            JOIN characters AS c ON c.id = dc.character_id
            LEFT JOIN talents AS t ON t.id = dc.talent_id
            WHERE dc.dialogue_id = ?
            ORDER BY dc.position, dc.id
            """,
            (int(dialogue_id),),
        ).fetchall()
        if not rows:
            return "Character Unknown / Talent Unknown"
        return ", ".join(
            f"{row['character_name']} / {row['talent_name']}"
            for row in rows
        )

    @staticmethod
    def _old_talent_keys(connection, dialogue_id: int) -> set[str]:
        rows = connection.execute(
            """
            SELECT t.name
            FROM dialog_cast AS dc
            JOIN talents AS t ON t.id = dc.talent_id
            WHERE dc.dialogue_id = ?
            """,
            (int(dialogue_id),),
        ).fetchall()
        return {
            normalize_key(str(row["name"]))
            for row in rows
            if normalize_key(str(row["name"]))
        }

    @staticmethod
    def _episode_id_has_tracking(connection, episode_id: int) -> bool:
        row = connection.execute(
            """
            SELECT 1
            FROM stem_status
            WHERE episode_id = ?
            LIMIT 1
            """,
            (int(episode_id),),
        ).fetchone()
        return row is not None

    @staticmethod
    def _episode_has_tracking(connection, episode_number: int) -> bool:
        row = connection.execute(
            """
            SELECT 1
            FROM stem_status AS ss
            JOIN episodes AS e ON e.id = ss.episode_id
            WHERE e.episode_number = ?
            LIMIT 1
            """,
            (int(episode_number),),
        ).fetchone()
        return row is not None
