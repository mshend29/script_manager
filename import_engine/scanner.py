from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from import_engine.episode_extractor import (
    EpisodeExtractionError,
    extract_episode_number,
)
from import_engine.file_fingerprint import (
    calculate_file_fingerprint,
)

SUPPORTED_EXTENSIONS = {
    ".xlsx",
    ".xlsm",
}


class SourceScanError(RuntimeError):
    pass


@dataclass(frozen=True)
class ScannedSourceFile:
    file_path: str

    file_name: str

    episode_number: int

    episode_raw: str

    file_size: int

    modified_at: str

    fingerprint: str


@dataclass(frozen=True)
class ScanProblem:
    file_path: str

    message: str


@dataclass
class SourceScanResult:
    source_folder: str

    files: list[ScannedSourceFile] = field(default_factory=list)

    problems: list[ScanProblem] = field(default_factory=list)

    duplicate_episodes: dict[
        int,
        list[str],
    ] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:

        return not self.problems and not self.duplicate_episodes


class SourceScanner:
    def scan(
        self,
        source_folder: str | Path,
        *,
        episode_before: str = "",
        episode_after: str = "",
    ) -> SourceScanResult:

        root = Path(source_folder).expanduser()

        # ---------------------------------
        # VALIDASI SOURCE FOLDER
        # ---------------------------------

        if not root.exists():
            raise SourceScanError(f"Source Folder tidak ditemukan:\n{root}")

        if not root.is_dir():
            raise SourceScanError(f"Source Folder bukan folder:\n{root}")

        result = SourceScanResult(source_folder=str(root))

        # ---------------------------------
        # CARI SEMUA FILE EXCEL
        # ---------------------------------

        candidates = sorted(
            (
                path
                for path in root.rglob("*")
                if (
                    path.is_file()
                    and path.suffix.lower() in SUPPORTED_EXTENSIONS
                    and not path.name.startswith("~$")
                )
            ),
            key=lambda p: str(p).lower(),
        )

        episode_paths: dict[
            int,
            list[str],
        ] = {}

        # ---------------------------------
        # SCAN FILE
        # ---------------------------------

        for path in candidates:
            try:
                extraction = extract_episode_number(
                    path.name,
                    before=episode_before,
                    after=episode_after,
                )

            except EpisodeExtractionError as exc:
                result.problems.append(
                    ScanProblem(
                        file_path=str(path),
                        message=str(exc),
                    )
                )

                continue

            # ---------------------------------
            # FILE INFORMATION
            # ---------------------------------

            try:
                stat = path.stat()

                fingerprint = calculate_file_fingerprint(path)

            except OSError as exc:
                result.problems.append(
                    ScanProblem(
                        file_path=str(path),
                        message=(f"File tidak dapat dibaca: {exc}"),
                    )
                )

                continue

            modified_at = datetime.fromtimestamp(stat.st_mtime).isoformat(  # noqa: DTZ006
                timespec="seconds"
            )

            scanned = ScannedSourceFile(
                file_path=str(path.resolve()),
                file_name=path.name,
                episode_number=(extraction.episode_number),
                episode_raw=(extraction.raw_value),
                file_size=stat.st_size,
                modified_at=modified_at,
                fingerprint=fingerprint,
            )

            result.files.append(scanned)

            episode_paths.setdefault(
                extraction.episode_number,
                [],
            ).append(str(path.resolve()))

        # ---------------------------------
        # DETEKSI DUPLICATE EPISODE
        # ---------------------------------

        result.duplicate_episodes = {
            episode: paths for episode, paths in episode_paths.items() if len(paths) > 1
        }

        return result
