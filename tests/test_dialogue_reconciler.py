from __future__ import annotations

from import_engine.parser import ParsedDialogueRow
from import_engine.reconciler import (
    DialogueMatchKind,
    DialogueReconciler,
    ExistingDialogueSnapshot,
)


def _parsed(
    *,
    row: int,
    signature: str,
    dialogue: str = "Dialog",
) -> ParsedDialogueRow:
    return ParsedDialogueRow(
        source_row=row,
        time_in="00:00:01,000",
        time_out="00:00:02,000",
        dialogue=dialogue,
        raw_character="Hendra",
        raw_talent="Brama",
        characters=("Hendra",),
        talents=("Brama",),
        cast_pairs=(),
        dialog_uid=signature,
        status="OK",
    )


def _existing(
    *,
    dialogue_id: int,
    row: int,
    signature: str,
    text: str = "Dialog",
) -> ExistingDialogueSnapshot:
    return ExistingDialogueSnapshot(
        dialogue_id=dialogue_id,
        dialog_uid=f"dlg-{dialogue_id}",
        source_signature=signature,
        source_row=row,
        dialog_text=text,
    )


def test_exact_signature_survives_row_move() -> None:
    result = DialogueReconciler().reconcile(
        existing=[_existing(dialogue_id=10, row=3, signature="sig-a")],
        parsed_rows=[_parsed(row=8, signature="sig-a")],
    )

    assert not result.has_ambiguities
    assert not result.new_rows
    assert not result.removed
    assert len(result.matches) == 1
    assert result.matches[0].existing.dialogue_id == 10
    assert result.matches[0].kind == DialogueMatchKind.EXACT_SIGNATURE


def test_text_revision_uses_unique_row_continuity() -> None:
    result = DialogueReconciler().reconcile(
        existing=[
            _existing(
                dialogue_id=10,
                row=3,
                signature="old-signature",
                text="Dialog lama",
            )
        ],
        parsed_rows=[
            _parsed(
                row=3,
                signature="new-signature",
                dialogue="Dialog revisi",
            )
        ],
    )

    assert len(result.matches) == 1
    assert result.matches[0].existing.dialogue_id == 10
    assert result.matches[0].kind == DialogueMatchKind.ROW_CONTINUITY


def test_single_moved_and_changed_row_uses_ordered_continuity() -> None:
    result = DialogueReconciler().reconcile(
        existing=[_existing(dialogue_id=10, row=3, signature="old")],
        parsed_rows=[_parsed(row=9, signature="new")],
    )

    assert len(result.matches) == 1
    assert result.matches[0].existing.dialogue_id == 10
    assert result.matches[0].kind == DialogueMatchKind.ORDERED_CONTINUITY


def test_inserted_row_does_not_steal_shifted_exact_match() -> None:
    result = DialogueReconciler().reconcile(
        existing=[
            _existing(dialogue_id=10, row=3, signature="sig-halo"),
            _existing(dialogue_id=11, row=4, signature="sig-joko"),
        ],
        parsed_rows=[
            _parsed(row=3, signature="sig-new", dialogue="Inserted"),
            _parsed(row=4, signature="sig-halo", dialogue="Halo"),
            _parsed(row=5, signature="sig-joko", dialogue="Joko"),
        ],
    )

    assert not result.has_ambiguities
    assert len(result.matches) == 2
    assert {
        (match.existing.dialogue_id, match.parsed.source_row)
        for match in result.matches
    } == {(10, 4), (11, 5)}
    assert [row.source_row for row in result.new_rows] == [3]


def test_equal_duplicate_signature_groups_match_by_source_order() -> None:
    result = DialogueReconciler().reconcile(
        existing=[
            _existing(dialogue_id=10, row=3, signature="same"),
            _existing(dialogue_id=11, row=4, signature="same"),
        ],
        parsed_rows=[
            _parsed(row=8, signature="same"),
            _parsed(row=9, signature="same"),
        ],
    )

    assert not result.has_ambiguities
    assert [
        (match.existing.dialogue_id, match.parsed.source_row)
        for match in result.matches
    ] == [(10, 8), (11, 9)]


def test_duplicate_new_rows_are_both_preserved_as_new() -> None:
    result = DialogueReconciler().reconcile(
        existing=[],
        parsed_rows=[
            _parsed(row=3, signature="same"),
            _parsed(row=4, signature="same"),
        ],
    )

    assert not result.matches
    assert not result.has_ambiguities
    assert [row.source_row for row in result.new_rows] == [3, 4]


def test_many_to_many_changed_remainder_is_ambiguous_not_guessed() -> None:
    result = DialogueReconciler().reconcile(
        existing=[
            _existing(dialogue_id=10, row=3, signature="old-a"),
            _existing(dialogue_id=11, row=4, signature="old-b"),
        ],
        parsed_rows=[
            _parsed(row=8, signature="new-a"),
            _parsed(row=9, signature="new-b"),
        ],
    )

    assert not result.matches
    assert not result.new_rows
    assert not result.removed
    assert result.has_ambiguities
    assert len(result.ambiguities) == 2
    assert all(
        ambiguity.candidate_dialogue_ids == (10, 11)
        for ambiguity in result.ambiguities
    )


def test_unmatched_existing_dialogue_is_removed_when_no_new_candidate() -> None:
    result = DialogueReconciler().reconcile(
        existing=[_existing(dialogue_id=10, row=3, signature="old")],
        parsed_rows=[],
    )

    assert not result.matches
    assert not result.new_rows
    assert not result.has_ambiguities
    assert [item.dialogue_id for item in result.removed] == [10]
