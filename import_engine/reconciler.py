from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from import_engine.parser import ParsedDialogueRow


class DialogueMatchKind(StrEnum):
    EXACT_SIGNATURE = "EXACT_SIGNATURE"
    ROW_CONTINUITY = "ROW_CONTINUITY"
    ORDERED_CONTINUITY = "ORDERED_CONTINUITY"


@dataclass(frozen=True)
class ExistingDialogueSnapshot:
    dialogue_id: int
    dialog_uid: str
    source_signature: str
    source_row: int | None
    time_in: str = ""
    time_out: str = ""
    dialog_text: str = ""
    episode_id: int | None = None
    is_active: bool = True


@dataclass(frozen=True)
class DialogueMatch:
    kind: DialogueMatchKind
    existing: ExistingDialogueSnapshot
    parsed: ParsedDialogueRow


@dataclass(frozen=True)
class DialogueAmbiguity:
    parsed: ParsedDialogueRow
    candidate_dialogue_ids: tuple[int, ...]


@dataclass
class DialogueReconciliationResult:
    matches: list[DialogueMatch] = field(default_factory=list)
    new_rows: list[ParsedDialogueRow] = field(default_factory=list)
    removed: list[ExistingDialogueSnapshot] = field(default_factory=list)
    ambiguities: list[DialogueAmbiguity] = field(default_factory=list)

    @property
    def has_ambiguities(self) -> bool:
        return bool(self.ambiguities)

    def match_for_source_row(self, source_row: int) -> DialogueMatch | None:
        for match in self.matches:
            if int(match.parsed.source_row) == int(source_row):
                return match
        return None


class DialogueReconciler:
    """Match parsed source rows to persistent dialogue records conservatively.

    Matching is deliberately source-file scoped. Callers must pass only the
    existing dialogues belonging to the source/episode being reconciled.

    The algorithm prefers evidence in this order:

    1. exact source signature + same source row,
    2. exact source signature groups with equal cardinality,
    3. unique source-row continuity after exact matches are consumed,
    4. a single remaining old/new pair (ordered continuity),
    5. ambiguity rather than guessing.

    Exact signature matching is performed before source-row continuity so an
    inserted row cannot steal the identity of a dialogue whose unchanged
    content simply shifted downward.
    """

    def reconcile(
        self,
        *,
        existing: list[ExistingDialogueSnapshot],
        parsed_rows: list[ParsedDialogueRow],
    ) -> DialogueReconciliationResult:
        result = DialogueReconciliationResult()

        remaining_existing: dict[int, ExistingDialogueSnapshot] = {
            int(item.dialogue_id): item for item in existing
        }
        remaining_parsed: dict[int, ParsedDialogueRow] = {
            index: row for index, row in enumerate(parsed_rows)
        }

        def pair(
            existing_id: int,
            parsed_index: int,
            kind: DialogueMatchKind,
        ) -> None:
            old = remaining_existing.pop(existing_id)
            new = remaining_parsed.pop(parsed_index)
            result.matches.append(
                DialogueMatch(
                    kind=kind,
                    existing=old,
                    parsed=new,
                )
            )

        # -------------------------------------------------------------
        # 1. Exact signature at the exact source row.
        # -------------------------------------------------------------
        for parsed_index, parsed in list(remaining_parsed.items()):
            candidates = [
                old
                for old in remaining_existing.values()
                if old.source_row == parsed.source_row
                and old.source_signature == parsed.source_signature
            ]
            if len(candidates) == 1:
                pair(
                    int(candidates[0].dialogue_id),
                    parsed_index,
                    DialogueMatchKind.EXACT_SIGNATURE,
                )

        # -------------------------------------------------------------
        # 2. Exact signature groups with equal cardinality.
        #    Equal duplicate groups are paired by source order. If counts
        #    differ, leave them unresolved for safer later evidence.
        # -------------------------------------------------------------
        signatures = sorted(
            {
                row.source_signature
                for row in remaining_parsed.values()
                if row.source_signature
            }
        )
        for signature in signatures:
            old_group = [
                old
                for old in remaining_existing.values()
                if old.source_signature == signature
            ]
            new_group = [
                (index, row)
                for index, row in remaining_parsed.items()
                if row.source_signature == signature
            ]
            if not old_group or len(old_group) != len(new_group):
                continue

            old_group.sort(
                key=lambda item: (
                    item.source_row if item.source_row is not None else 10**12,
                    item.dialogue_id,
                )
            )
            new_group.sort(key=lambda item: (item[1].source_row, item[0]))

            for old, (parsed_index, _row) in zip(
                old_group,
                new_group,
                strict=True,
            ):
                if (
                    int(old.dialogue_id) in remaining_existing
                    and parsed_index in remaining_parsed
                ):
                    pair(
                        int(old.dialogue_id),
                        parsed_index,
                        DialogueMatchKind.EXACT_SIGNATURE,
                    )

        # -------------------------------------------------------------
        # 3. Unique row continuity for mutable content revisions.
        # -------------------------------------------------------------
        for parsed_index, parsed in list(remaining_parsed.items()):
            candidates = [
                old
                for old in remaining_existing.values()
                if old.source_row == parsed.source_row
            ]
            if len(candidates) == 1:
                pair(
                    int(candidates[0].dialogue_id),
                    parsed_index,
                    DialogueMatchKind.ROW_CONTINUITY,
                )

        # -------------------------------------------------------------
        # 4. If exactly one pair remains, continuity is unambiguous even if
        #    both row and content changed.
        # -------------------------------------------------------------
        if len(remaining_existing) == 1 and len(remaining_parsed) == 1:
            existing_id = next(iter(remaining_existing))
            parsed_index = next(iter(remaining_parsed))
            pair(
                existing_id,
                parsed_index,
                DialogueMatchKind.ORDERED_CONTINUITY,
            )

        # -------------------------------------------------------------
        # 5. Never silently guess a many-to-many remainder.
        # -------------------------------------------------------------
        if remaining_existing and remaining_parsed:
            candidate_ids = tuple(sorted(remaining_existing))
            for _index, parsed in sorted(
                remaining_parsed.items(),
                key=lambda item: (item[1].source_row, item[0]),
            ):
                result.ambiguities.append(
                    DialogueAmbiguity(
                        parsed=parsed,
                        candidate_dialogue_ids=candidate_ids,
                    )
                )
            return result

        if remaining_parsed:
            result.new_rows.extend(
                row
                for _index, row in sorted(
                    remaining_parsed.items(),
                    key=lambda item: (item[1].source_row, item[0]),
                )
            )

        if remaining_existing:
            result.removed.extend(
                sorted(
                    remaining_existing.values(),
                    key=lambda item: (
                        item.source_row
                        if item.source_row is not None
                        else 10**12,
                        item.dialogue_id,
                    ),
                )
            )

        result.matches.sort(
            key=lambda match: (
                match.parsed.source_row,
                match.existing.dialogue_id,
            )
        )
        return result
