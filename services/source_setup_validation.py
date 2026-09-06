from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from import_engine.episode_extractor import (
    EpisodeExtractionError,
    extract_episode_number,
)
from import_engine.scanner import SUPPORTED_EXTENSIONS
from services.project_setup_validation import (
    SetupValidationIssue,
    looks_like_browser_url,
)
from services.source_filename_service import (
    SourceFilenameAnalysis,
    analyze_source_filenames,
)


@dataclass(frozen=True)
class SourceEpisodeMapping:
    file_path: str
    file_name: str
    episode_number: int
    raw_value: str


@dataclass(frozen=True)
class SourceFilenameValidation:
    source_folder: str
    candidate_count: int
    analysis: SourceFilenameAnalysis | None
    mappings: tuple[SourceEpisodeMapping, ...]
    issues: tuple[SetupValidationIssue, ...]

    @property
    def errors(self) -> tuple[SetupValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[SetupValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def is_valid(self) -> bool:
        return not self.errors

    @property
    def file_count(self) -> int:
        return self.candidate_count

    @property
    def episode_numbers(self) -> tuple[int, ...]:
        return tuple(sorted({mapping.episode_number for mapping in self.mappings}))

    @property
    def missing_episodes(self) -> tuple[int, ...]:
        episodes = self.episode_numbers
        if len(episodes) < 2:
            return ()
        expected = set(range(episodes[0], episodes[-1] + 1))
        return tuple(sorted(expected.difference(episodes)))

    @property
    def preview_mappings(self) -> tuple[SourceEpisodeMapping, ...]:
        if not self.mappings:
            return ()
        ordered = tuple(
            sorted(
                self.mappings,
                key=lambda item: (
                    item.episode_number,
                    item.file_name.casefold(),
                    item.file_path.casefold(),
                ),
            )
        )
        indexes = sorted({0, len(ordered) // 2, len(ordered) - 1})
        return tuple(ordered[index] for index in indexes)


def validate_source_filenames(
    source_folder: str | Path,
    *,
    episode_before: str = "",
    episode_after: str = "",
) -> SourceFilenameValidation:
    raw_folder = str(source_folder or "").strip()
    issues: list[SetupValidationIssue] = []

    if not raw_folder:
        return SourceFilenameValidation(
            source_folder="",
            candidate_count=0,
            analysis=None,
            mappings=(),
            issues=(
                SetupValidationIssue(
                    "source_folder",
                    "Folder Sumber wajib dipilih.",
                ),
            ),
        )

    if looks_like_browser_url(raw_folder):
        return SourceFilenameValidation(
            source_folder=raw_folder,
            candidate_count=0,
            analysis=None,
            mappings=(),
            issues=(
                SetupValidationIssue(
                    "source_folder",
                    "Folder Sumber harus berupa filesystem path, bukan URL browser.",
                ),
            ),
        )

    root = Path(raw_folder).expanduser()
    if not root.exists():
        return SourceFilenameValidation(
            source_folder=str(root),
            candidate_count=0,
            analysis=None,
            mappings=(),
            issues=(
                SetupValidationIssue(
                    "source_folder",
                    f"Folder Sumber tidak ditemukan: {root}",
                ),
            ),
        )
    if not root.is_dir():
        return SourceFilenameValidation(
            source_folder=str(root),
            candidate_count=0,
            analysis=None,
            mappings=(),
            issues=(
                SetupValidationIssue(
                    "source_folder",
                    f"Folder Sumber bukan folder: {root}",
                ),
            ),
        )

    candidates = tuple(
        sorted(
            (
                path
                for path in root.rglob("*")
                if (
                    path.is_file()
                    and path.suffix.lower() in SUPPORTED_EXTENSIONS
                    and not path.name.startswith("~$")
                )
            ),
            key=lambda path: str(path).casefold(),
        )
    )
    analysis = analyze_source_filenames([path.name for path in candidates])

    if not candidates:
        return SourceFilenameValidation(
            source_folder=str(root),
            candidate_count=0,
            analysis=analysis,
            mappings=(),
            issues=(
                SetupValidationIssue(
                    "source_folder",
                    "Tidak ada file .xlsx/.xlsm pada Folder Sumber.",
                ),
            ),
        )

    if len(analysis.patterns) > 1:
        issues.append(
            SetupValidationIssue(
                "source_pattern",
                f"Ditemukan {len(analysis.patterns)} pola filename. "
                "Sumber proyek baru harus memakai satu pola yang konsisten.",
            )
        )
    elif (
        len(analysis.filenames) > 1
        and analysis.patterns
        and not analysis.patterns[0].is_episode_candidate
    ):
        issues.append(
            SetupValidationIssue(
                "source_pattern",
                "Pola filename memiliki lebih dari satu bagian angka yang berubah. "
                "Delimiter tetap divalidasi terhadap seluruh file.",
                severity="warning",
            )
        )

    mappings: list[SourceEpisodeMapping] = []
    episode_paths: dict[int, list[str]] = {}
    for path in candidates:
        try:
            extraction = extract_episode_number(
                path.name,
                before=episode_before,
                after=episode_after,
            )
        except EpisodeExtractionError as exc:
            issues.append(
                SetupValidationIssue(
                    "source_filename",
                    f"{path.name}: {exc}",
                )
            )
            continue

        resolved = str(path.resolve())
        mappings.append(
            SourceEpisodeMapping(
                file_path=resolved,
                file_name=path.name,
                episode_number=extraction.episode_number,
                raw_value=extraction.raw_value,
            )
        )
        episode_paths.setdefault(extraction.episode_number, []).append(resolved)

    duplicate_episodes = {
        episode: paths
        for episode, paths in episode_paths.items()
        if len(paths) > 1
    }
    for episode, paths in sorted(duplicate_episodes.items()):
        names = ", ".join(Path(path).name for path in paths)
        issues.append(
            SetupValidationIssue(
                "source_episode",
                f"Episode {episode} terbaca dari lebih dari satu file: {names}",
            )
        )

    result = SourceFilenameValidation(
        source_folder=str(root),
        candidate_count=len(candidates),
        analysis=analysis,
        mappings=tuple(mappings),
        issues=tuple(issues),
    )
    if (
        len(mappings) == len(candidates)
        and not duplicate_episodes
        and result.missing_episodes
    ):
        missing = ", ".join(str(value) for value in result.missing_episodes)
        issues.append(
            SetupValidationIssue(
                "source_episode_gap",
                f"Gap episode terdeteksi: {missing}",
                severity="warning",
            )
        )
        result = SourceFilenameValidation(
            source_folder=str(root),
            candidate_count=len(candidates),
            analysis=analysis,
            mappings=tuple(mappings),
            issues=tuple(issues),
        )

    return result
