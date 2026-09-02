from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum

from core.database import Database
from import_engine.parser import ParsedDialogueRow, ScriptParseResult
from import_engine.reconciler import (
    DialogueAmbiguity,
    DialogueMatch,
    DialogueReconciler,
    ExistingDialogueSnapshot,
)
from import_engine.scanner import SourceScanResult


class SourceFileChangeKind(StrEnum):
    ADDED = "ADDED"
    CHANGED = "CHANGED"
    RESTORED = "RESTORED"


@dataclass(frozen=True)
class MissingSourcePlan:
    source_file_id: int
    file_path: str
    episode_number: int
    active_dialogue_ids: tuple[int, ...]


@dataclass
class SourceFileChangePlan:
    file_path: str
    episode_number: int
    source_file_id: int | None
    kind: SourceFileChangeKind
    matches: list[DialogueMatch] = field(default_factory=list)
    additions: list[ParsedDialogueRow] = field(default_factory=list)
    removals: list[ExistingDialogueSnapshot] = field(default_factory=list)
    ambiguities: list[DialogueAmbiguity] = field(default_factory=list)

    @property
    def has_ambiguities(self) -> bool:
        return bool(self.ambiguities)


@dataclass
class SourceChangePlan:
    database_token: str
    source_snapshot: tuple[tuple[str, str, int], ...]
    file_plans: dict[str, SourceFileChangePlan] = field(default_factory=dict)
    missing_sources: list[MissingSourcePlan] = field(default_factory=list)

    @property
    def has_ambiguities(self) -> bool:
        return any(plan.has_ambiguities for plan in self.file_plans.values())

    @property
    def ambiguity_messages(self) -> list[str]:
        messages: list[str] = []
        for plan in self.file_plans.values():
            for ambiguity in plan.ambiguities:
                candidates = ", ".join(
                    str(value) for value in ambiguity.candidate_dialogue_ids
                )
                messages.append(
                    f"Episode {plan.episode_number} row "
                    f"{ambiguity.parsed.source_row}: dialogue lineage ambigu "
                    f"(candidate ids: {candidates})."
                )
        return messages


class SourceChangePlanBuilder:
    def __init__(
        self,
        database: Database,
        reconciler: DialogueReconciler | None = None,
    ) -> None:
        self.database = database
        self.reconciler = reconciler or DialogueReconciler()

    def build(
        self,
        *,
        scan: SourceScanResult,
        parse_results: dict[str, ScriptParseResult],
    ) -> SourceChangePlan:
        with self.database.connect() as connection:
            database_token = self.compute_database_token(connection)
            source_rows = connection.execute(
                """
                SELECT id, file_path, fingerprint, is_active, episode_number
                FROM source_files
                ORDER BY id
                """
            ).fetchall()
            source_by_path = {
                str(row["file_path"]): row for row in source_rows
            }

            scanned_paths = {item.file_path for item in scan.files}
            missing_sources: list[MissingSourcePlan] = []
            for path, source in source_by_path.items():
                if path in scanned_paths:
                    continue
                if int(source["is_active"] or 0) != 1:
                    continue
                dialogue_rows = connection.execute(
                    """
                    SELECT id
                    FROM dialogues
                    WHERE source_file_id = ?
                      AND is_active = 1
                    ORDER BY id
                    """,
                    (int(source["id"]),),
                ).fetchall()
                missing_sources.append(
                    MissingSourcePlan(
                        source_file_id=int(source["id"]),
                        file_path=path,
                        episode_number=int(source["episode_number"] or 0),
                        active_dialogue_ids=tuple(
                            int(row["id"]) for row in dialogue_rows
                        ),
                    )
                )

            file_plans: dict[str, SourceFileChangePlan] = {}
            scan_by_path = {item.file_path: item for item in scan.files}

            for file_path, parse_result in parse_results.items():
                scanned = scan_by_path[file_path]
                source = source_by_path.get(file_path)

                if source is None:
                    kind = SourceFileChangeKind.ADDED
                    file_plans[file_path] = SourceFileChangePlan(
                        file_path=file_path,
                        episode_number=int(parse_result.episode_number),
                        source_file_id=None,
                        kind=kind,
                        additions=list(parse_result.rows),
                    )
                    continue

                source_active = int(source["is_active"] or 0) == 1
                fingerprint_changed = (
                    str(source["fingerprint"] or "")
                    != str(scanned.fingerprint or "")
                )
                kind = (
                    SourceFileChangeKind.CHANGED
                    if fingerprint_changed
                    else SourceFileChangeKind.RESTORED
                )

                where_active = "AND d.is_active = 1" if source_active else ""
                old_rows = connection.execute(
                    f"""
                    SELECT
                        d.id,
                        d.dialog_uid,
                        COALESCE(d.source_signature, d.dialog_uid) AS source_signature,
                        d.source_row,
                        d.time_in,
                        d.time_out,
                        d.dialog_text,
                        d.episode_id,
                        d.is_active
                    FROM dialogues AS d
                    WHERE d.source_file_id = ?
                    {where_active}
                    ORDER BY d.source_row, d.id
                    """,
                    (int(source["id"]),),
                ).fetchall()

                existing = [
                    ExistingDialogueSnapshot(
                        dialogue_id=int(row["id"]),
                        dialog_uid=str(row["dialog_uid"]),
                        source_signature=str(row["source_signature"] or ""),
                        source_row=(
                            int(row["source_row"])
                            if row["source_row"] is not None
                            else None
                        ),
                        time_in=str(row["time_in"] or ""),
                        time_out=str(row["time_out"] or ""),
                        dialog_text=str(row["dialog_text"] or ""),
                        episode_id=int(row["episode_id"]),
                        is_active=bool(int(row["is_active"] or 0)),
                    )
                    for row in old_rows
                ]
                reconciled = self.reconciler.reconcile(
                    existing=existing,
                    parsed_rows=list(parse_result.rows),
                )
                file_plans[file_path] = SourceFileChangePlan(
                    file_path=file_path,
                    episode_number=int(parse_result.episode_number),
                    source_file_id=int(source["id"]),
                    kind=kind,
                    matches=list(reconciled.matches),
                    additions=list(reconciled.new_rows),
                    removals=list(reconciled.removed),
                    ambiguities=list(reconciled.ambiguities),
                )

        return SourceChangePlan(
            database_token=database_token,
            source_snapshot=self.scan_snapshot(scan),
            file_plans=file_plans,
            missing_sources=missing_sources,
        )

    @staticmethod
    def scan_snapshot(
        scan: SourceScanResult,
    ) -> tuple[tuple[str, str, int], ...]:
        return tuple(
            sorted(
                (
                    str(item.file_path),
                    str(item.fingerprint or ""),
                    int(item.episode_number),
                )
                for item in scan.files
            )
        )

    @staticmethod
    def compute_database_token(connection) -> str:
        sources = [
            tuple(row)
            for row in connection.execute(
                """
                SELECT id, file_path, fingerprint, is_active, episode_number
                FROM source_files
                ORDER BY id
                """
            ).fetchall()
        ]
        dialogues = [
            tuple(row)
            for row in connection.execute(
                """
                SELECT
                    id,
                    dialog_uid,
                    COALESCE(source_signature, ''),
                    source_file_id,
                    episode_id,
                    COALESCE(time_in, ''),
                    COALESCE(time_out, ''),
                    dialog_text,
                    source_row,
                    is_active
                FROM dialogues
                ORDER BY id
                """
            ).fetchall()
        ]
        payload = json.dumps(
            {"sources": sources, "dialogues": dialogues},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
