from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.database import Database
from services.audit_service import AuditService
from services.track_file_service import (
    TrackFileRow,
    sanitize_filename_component,
    track_filename_matches,
)


RENAME_MATCHED = "MATCHED"
RENAME_ALREADY_EXPECTED = "ALREADY_EXPECTED"
RENAME_AMBIGUOUS = "AMBIGUOUS"
RENAME_COLLISION = "COLLISION"
RENAME_UNMATCHED = "UNMATCHED"

MATCH_SEMANTIC = "semantic"
MATCH_SIMPLE_EXPORT = "simple-export"


@dataclass(frozen=True)
class SimpleExportFilename:
    episode_number: int
    track_name: str


@dataclass(frozen=True)
class TrackRenameItem:
    source_path: str
    target_path: str
    status: str
    match_kind: str
    episode_number: int | None
    character_id: int | None
    character_name: str
    talent_id: int | None
    talent_name: str
    detail: str = ""

    @property
    def can_rename(self) -> bool:
        return self.status == RENAME_MATCHED


@dataclass
class TrackRenamePlan:
    items: list[TrackRenameItem] = field(default_factory=list)
    output_folder: str = ""
    talent_id: int | None = None
    talent_name: str = ""
    episode_number: int | None = None

    @property
    def matched(self) -> int:
        return sum(1 for item in self.items if item.status == RENAME_MATCHED)

    @property
    def already_expected(self) -> int:
        return sum(
            1
            for item in self.items
            if item.status == RENAME_ALREADY_EXPECTED
        )

    @property
    def ambiguous(self) -> int:
        return sum(1 for item in self.items if item.status == RENAME_AMBIGUOUS)

    @property
    def collisions(self) -> int:
        return sum(1 for item in self.items if item.status == RENAME_COLLISION)

    @property
    def unmatched(self) -> int:
        return sum(1 for item in self.items if item.status == RENAME_UNMATCHED)

    @property
    def rename_items(self) -> list[TrackRenameItem]:
        return [item for item in self.items if item.can_rename]


class TrackRenameService:
    """Safely normalize exported stem filenames to expected project names."""

    def __init__(
        self,
        database: Database,
        *,
        output_folder: str,
    ):
        self.database = database
        self.output_folder = str(output_folder or "").strip()

    def build_plan(
        self,
        rows: list[TrackFileRow],
        *,
        talent_id: int,
        episode_number: int | None = None,
        selected_source_path: str | None = None,
    ) -> TrackRenamePlan:
        folder = Path(self.output_folder)
        scoped_rows = [
            row
            for row in rows
            if (
                row.talent_id == int(talent_id)
                and (
                    episode_number is None
                    or row.episode_number == int(episode_number)
                )
            )
        ]

        talent_name = (
            scoped_rows[0].talent_name if scoped_rows else ""
        )
        plan = TrackRenamePlan(
            output_folder=self.output_folder,
            talent_id=int(talent_id),
            talent_name=talent_name,
            episode_number=(
                int(episode_number)
                if episode_number is not None
                else None
            ),
        )

        if not folder.is_dir() or not scoped_rows:
            return plan

        if selected_source_path:
            candidate = Path(selected_source_path)
            files = [candidate] if candidate.is_file() else []
        else:
            files = sorted(
                (
                    path
                    for path in folder.iterdir()
                    if (
                        path.is_file()
                        and path.suffix.casefold() == ".wav"
                        and not path.name.startswith("~$")
                    )
                ),
                key=lambda path: path.name.casefold(),
            )

        target_usage: dict[str, list[Path]] = {}
        preliminary: list[TrackRenameItem] = []

        for path in files:
            item = self._classify_file(
                path,
                scoped_rows,
                include_unmatched=bool(selected_source_path),
            )
            if item is None:
                continue
            preliminary.append(item)
            if item.target_path:
                target_usage.setdefault(
                    str(Path(item.target_path)).casefold(),
                    [],
                ).append(path)

        for item in preliminary:
            if not item.target_path:
                plan.items.append(item)
                continue

            target_key = str(Path(item.target_path)).casefold()
            if (
                item.status == RENAME_MATCHED
                and len(target_usage.get(target_key, [])) > 1
            ):
                plan.items.append(
                    TrackRenameItem(
                        **{
                            **item.__dict__,
                            "status": RENAME_AMBIGUOUS,
                            "detail": (
                                "Lebih dari satu source file mengarah ke "
                                "expected filename yang sama."
                            ),
                        }
                    )
                )
                continue
            plan.items.append(item)

        plan.items.sort(
            key=lambda item: (
                item.episode_number
                if item.episode_number is not None
                else 999999999,
                item.character_name.casefold(),
                Path(item.source_path).name.casefold(),
            )
        )
        return plan

    def execute(self, plan: TrackRenamePlan) -> list[TrackRenameItem]:
        items = list(plan.rename_items)
        if not items:
            return []

        # Revalidate every source/target immediately before touching files.
        targets: set[str] = set()
        for item in items:
            source = Path(item.source_path)
            target = Path(item.target_path)
            if not source.is_file():
                raise FileNotFoundError(
                    f"Source file tidak ditemukan: {source}"
                )
            if source.parent != target.parent:
                raise ValueError(
                    "Rename hanya boleh dilakukan di folder Stem / Export "
                    "yang sama."
                )

            target_key = str(target).casefold()
            if target_key in targets:
                raise FileExistsError(
                    f"Duplicate rename target: {target.name}"
                )
            targets.add(target_key)

            if (
                target.exists()
                and source.resolve() != target.resolve()
            ):
                raise FileExistsError(
                    f"Target sudah ada dan tidak akan ditimpa: {target.name}"
                )

        completed: list[tuple[Path, Path]] = []
        try:
            for item in items:
                source = Path(item.source_path)
                target = Path(item.target_path)

                # Case-insensitive equality means the file is already equivalent
                # on Windows; avoid a risky case-only rename through Drive Desktop.
                if source.name.casefold() == target.name.casefold():
                    continue

                if target.exists():
                    raise FileExistsError(
                        f"Target sudah ada dan tidak akan ditimpa: {target.name}"
                    )

                source.rename(target)
                completed.append((source, target))
        except Exception:
            # Best-effort rollback. Never overwrite a source during rollback.
            for source, target in reversed(completed):
                try:
                    if target.exists() and not source.exists():
                        target.rename(source)
                except OSError:
                    pass
            raise

        now = datetime.now().isoformat(timespec="seconds")
        AuditService(self.database).record(
            event_type="TRACK_FILE",
            action="BATCH_RENAME_TO_EXPECTED",
            entity_type="talent",
            entity_id=plan.talent_id,
            summary=(
                f"{len(completed)} Stem / Export file renamed to expected "
                f"filename for {plan.talent_name or 'selected talent'}."
            ),
            details={
                "episode_number": plan.episode_number,
                "renamed": [
                    {
                        "from": str(source),
                        "to": str(target),
                    }
                    for source, target in completed
                ],
            },
            created_at=now,
        )

        completed_targets = {str(target).casefold() for _, target in completed}
        return [
            item
            for item in items
            if str(Path(item.target_path)).casefold() in completed_targets
        ]

    def _classify_file(
        self,
        path: Path,
        rows: list[TrackFileRow],
        *,
        include_unmatched: bool,
    ) -> TrackRenameItem | None:
        semantic_matches = [
            row
            for row in rows
            if track_filename_matches(
                path.name,
                episode_number=row.episode_number,
                canonical_character=row.character_name,
                aliases=row.aliases,
                talent_name=row.talent_name,
            )
        ]

        if len(semantic_matches) == 1:
            return self._item_for_row(
                path,
                semantic_matches[0],
                match_kind=MATCH_SEMANTIC,
            )
        if len(semantic_matches) > 1:
            return TrackRenameItem(
                source_path=str(path),
                target_path="",
                status=RENAME_AMBIGUOUS,
                match_kind=MATCH_SEMANTIC,
                episode_number=None,
                character_id=None,
                character_name="",
                talent_id=None,
                talent_name="",
                detail="File cocok dengan lebih dari satu expected identity.",
            )

        simple = parse_simple_export_filename(path.name)
        if simple is None:
            if not include_unmatched:
                return None
            return TrackRenameItem(
                source_path=str(path),
                target_path="",
                status=RENAME_UNMATCHED,
                match_kind=MATCH_SIMPLE_EXPORT,
                episode_number=None,
                character_id=None,
                character_name="",
                talent_id=None,
                talent_name="",
                detail="Filename tidak mengikuti format {episode}_{track}.wav.",
            )

        candidates = [
            row
            for row in rows
            if (
                row.episode_number == simple.episode_number
                and _track_name_key(row.character_name)
                == _track_name_key(simple.track_name)
            )
        ]

        if len(candidates) == 1:
            return self._item_for_row(
                path,
                candidates[0],
                match_kind=MATCH_SIMPLE_EXPORT,
            )

        if len(candidates) > 1:
            names = ", ".join(
                sorted(
                    {
                        f"{row.character_name} / {row.talent_name}"
                        for row in candidates
                    },
                    key=str.casefold,
                )
            )
            return TrackRenameItem(
                source_path=str(path),
                target_path="",
                status=RENAME_AMBIGUOUS,
                match_kind=MATCH_SIMPLE_EXPORT,
                episode_number=simple.episode_number,
                character_id=None,
                character_name=simple.track_name,
                talent_id=rows[0].talent_id if rows else None,
                talent_name=rows[0].talent_name if rows else "",
                detail=f"Track name ambigu: {names}",
            )

        if not include_unmatched:
            return None
        return TrackRenameItem(
            source_path=str(path),
            target_path="",
            status=RENAME_UNMATCHED,
            match_kind=MATCH_SIMPLE_EXPORT,
            episode_number=simple.episode_number,
            character_id=None,
            character_name=simple.track_name,
            talent_id=rows[0].talent_id if rows else None,
            talent_name=rows[0].talent_name if rows else "",
            detail="Tidak ada expected track yang cocok pada scope talent ini.",
        )

    @staticmethod
    def _item_for_row(
        source: Path,
        row: TrackFileRow,
        *,
        match_kind: str,
    ) -> TrackRenameItem:
        target = source.parent / row.expected_filename

        if source.name.casefold() == target.name.casefold():
            status = RENAME_ALREADY_EXPECTED
            detail = "Filename sudah sesuai expected."
        elif target.exists():
            status = RENAME_COLLISION
            detail = (
                "Expected filename sudah ada. File tidak akan ditimpa."
            )
        else:
            status = RENAME_MATCHED
            detail = (
                "Simplified DAW export dikenali."
                if match_kind == MATCH_SIMPLE_EXPORT
                else "Identity valid; dapat dinormalisasi ke preferred expected name."
            )

        return TrackRenameItem(
            source_path=str(source),
            target_path=str(target),
            status=status,
            match_kind=match_kind,
            episode_number=row.episode_number,
            character_id=row.character_id,
            character_name=row.character_name,
            talent_id=row.talent_id,
            talent_name=row.talent_name,
            detail=detail,
        )


def parse_simple_export_filename(
    filename: str,
) -> SimpleExportFilename | None:
    path = Path(str(filename))
    if path.suffix.casefold() != ".wav":
        return None

    stem = path.stem
    if "_" not in stem:
        return None

    episode_text, track_name = stem.split("_", 1)
    episode_text = episode_text.strip()
    track_name = sanitize_filename_component(
        track_name,
        uppercase=True,
    )

    if not episode_text.isdigit() or not track_name:
        return None

    return SimpleExportFilename(
        episode_number=int(episode_text),
        track_name=track_name,
    )


def _track_name_key(value: str) -> str:
    return sanitize_filename_component(
        value,
        uppercase=True,
    ).casefold()
