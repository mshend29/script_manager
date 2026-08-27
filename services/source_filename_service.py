from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from import_engine.scanner import SUPPORTED_EXTENSIONS


_DIGIT_RUN = re.compile(r"(\d+)")


@dataclass(frozen=True)
class SourceFilenamePattern:
    pattern: str
    count: int
    examples: tuple[str, ...]
    varying_number_runs: int

    @property
    def is_episode_candidate(self) -> bool:
        return self.varying_number_runs == 1


@dataclass(frozen=True)
class SourceFilenameAnalysis:
    filenames: tuple[str, ...]
    patterns: tuple[SourceFilenamePattern, ...]

    @property
    def representative_filename(self) -> str:
        if not self.patterns or not self.patterns[0].examples:
            return ""
        return self.patterns[0].examples[0]

    @property
    def is_consistent(self) -> bool:
        return (
            len(self.patterns) == 1
            and bool(self.patterns)
            and self.patterns[0].is_episode_candidate
        )


def read_source_filenames(source_folder: str | Path) -> SourceFilenameAnalysis:
    root = Path(source_folder).expanduser()
    if not root.exists():
        raise ValueError(f"Source Folder tidak ditemukan:\n{root}")
    if not root.is_dir():
        raise ValueError(f"Source Folder bukan folder:\n{root}")

    names = sorted(
        {
            path.name
            for path in root.rglob("*")
            if (
                path.is_file()
                and path.suffix.lower() in SUPPORTED_EXTENSIONS
                and not path.name.startswith("~$")
            )
        },
        key=str.casefold,
    )
    return analyze_source_filenames(names)


def analyze_source_filenames(
    filenames: list[str] | tuple[str, ...],
) -> SourceFilenameAnalysis:
    names = tuple(sorted({str(name) for name in filenames}, key=str.casefold))
    grouped: dict[tuple[str, ...], list[tuple[str, tuple[str, ...]]]] = {}

    for name in names:
        parts = tuple(_DIGIT_RUN.split(name))
        non_numbers = tuple(parts[::2])
        numbers = tuple(parts[1::2])
        signature = (*non_numbers, f"#runs={len(numbers)}")
        grouped.setdefault(signature, []).append((name, numbers))

    patterns: list[SourceFilenamePattern] = []
    for entries in grouped.values():
        first_name, first_numbers = entries[0]
        values_by_position: list[set[str]] = [
            set() for _ in range(len(first_numbers))
        ]
        for _name, numbers in entries:
            for index, value in enumerate(numbers):
                values_by_position[index].add(value)

        varying = {
            index
            for index, values in enumerate(values_by_position)
            if len(values) > 1
        }
        pattern_parts = list(_DIGIT_RUN.split(first_name))
        for number_index in range(len(first_numbers)):
            token_index = 1 + number_index * 2
            if number_index in varying:
                pattern_parts[token_index] = "{number}"
        pattern = "".join(pattern_parts)

        examples = tuple(name for name, _numbers in entries[:3])
        patterns.append(
            SourceFilenamePattern(
                pattern=pattern,
                count=len(entries),
                examples=examples,
                varying_number_runs=len(varying),
            )
        )

    patterns.sort(
        key=lambda item: (
            -item.count,
            item.pattern.casefold(),
        )
    )
    return SourceFilenameAnalysis(
        filenames=names,
        patterns=tuple(patterns),
    )
