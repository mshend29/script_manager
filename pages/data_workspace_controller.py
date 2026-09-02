from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.database import Database
from services.data_service import (
    CharacterAdminRow,
    DataOverview,
    DataService,
    SourceAdminRow,
    TalentAdminRow,
    UnresolvedCastRow,
)
from services.review_service import ReviewService, ReviewedDialogueRow
from services.validation_service import (
    ValidationIssue,
    ValidationService,
    ValidationSummary,
)


@dataclass(frozen=True)
class ReviewWorkspaceRows:
    unresolved: tuple[UnresolvedCastRow, ...]
    reviewed: tuple[ReviewedDialogueRow, ...]


class DataWorkspaceController:
    """Application-facing controller for the DATA workspace.

    The Qt page owns rendering, selection, filters, and operator dialogs.
    This controller owns the service graph and all DATA-domain reads/writes.
    """

    def __init__(self, database: Database | None = None) -> None:
        self.database: Database | None = None
        self.data: DataService | None = None
        self.review: ReviewService | None = None
        self.validation: ValidationService | None = None
        self.bind_database(database)

    @property
    def is_bound(self) -> bool:
        return self.database is not None and self.data is not None

    def bind_database(self, database: Database | None) -> None:
        self.database = database
        self.data = DataService(database) if database is not None else None
        self.review = ReviewService(database) if database is not None else None
        self.validation = (
            ValidationService(database) if database is not None else None
        )

    def get_review_rows(self) -> ReviewWorkspaceRows:
        if self.data is None or self.review is None:
            return ReviewWorkspaceRows(unresolved=(), reviewed=())

        reviewed_ids = self.review.get_active_non_dialogue_ids()
        unresolved = tuple(
            row
            for row in self.data.get_unresolved_cast()
            if row.dialogue_id not in reviewed_ids
        )
        reviewed = tuple(self.review.get_non_dialogues())
        return ReviewWorkspaceRows(
            unresolved=unresolved,
            reviewed=reviewed,
        )

    def get_overview(self) -> DataOverview:
        return self._require_data().get_overview()

    def get_characters(self) -> list[CharacterAdminRow]:
        return self._require_data().get_characters()

    def get_talents(self) -> list[TalentAdminRow]:
        return self._require_data().get_talents()

    def get_sources(self) -> list[SourceAdminRow]:
        return self._require_data().get_sources()

    def get_talent_options(self) -> list[tuple[int, str]]:
        return self._require_data().get_talent_options()

    def get_active_non_dialogue_count(self) -> int:
        return (
            self.review.get_active_non_dialogue_count()
            if self.review is not None
            else 0
        )

    def validate(self) -> list[ValidationIssue]:
        if self.validation is None:
            return []
        return self.validation.validate()

    def summarize(
        self,
        issues: list[ValidationIssue],
    ) -> ValidationSummary:
        if self.validation is None:
            return ValidationSummary(
                system_errors=0,
                needs_review=0,
                workflow_warnings=0,
            )
        return self.validation.summarize(issues)

    def mark_non_dialogue(self, dialogue_id: int) -> None:
        if self.review is None:
            raise RuntimeError("DATA workspace belum terhubung ke project.")
        self.review.mark_non_dialogue(int(dialogue_id))

    def restore_to_review(self, dialogue_id: int) -> None:
        if self.review is None:
            raise RuntimeError("DATA workspace belum terhubung ke project.")
        self.review.restore_to_review(int(dialogue_id))

    def add_missing_character(
        self,
        dialogue_id: int,
        name: str,
    ) -> int:
        service = self._require_data()
        character_id = service.ensure_character(name)
        service.assign_missing_character(
            int(dialogue_id),
            int(character_id),
        )
        return int(character_id)

    def add_talent_and_lock(
        self,
        character_id: int,
        name: str,
    ) -> int:
        service = self._require_data()
        talent_id = service.ensure_talent(name)
        service.set_locked_mapping(
            int(character_id),
            int(talent_id),
        )
        return int(talent_id)

    def set_locked_mapping(
        self,
        character_id: int,
        talent_id: int,
    ) -> None:
        self._require_data().set_locked_mapping(
            int(character_id),
            int(talent_id),
        )

    def unlock_mapping(self, character_id: int) -> None:
        self._require_data().unlock_mapping(int(character_id))

    def backup_database(self) -> Path:
        return self._require_data().backup_database()

    def rebuild_indexes(self) -> None:
        self._require_data().rebuild_indexes()

    def _require_data(self) -> DataService:
        if self.data is None:
            raise RuntimeError("DATA workspace belum terhubung ke project.")
        return self.data
