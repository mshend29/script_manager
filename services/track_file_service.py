from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.database import Database
from services.tracking_service import (
    AUTO_FILE_STATUS_NOTE,
    DELIVERED,
    READY_TO_STEM,
    REVISION,
    STEMMED,
)


_AUDIO_LIKE_SUFFIXES = {
    ".wav",
    ".wave",
    ".mp3",
    ".flac",
    ".aif",
    ".aiff",
    ".m4a",
    ".aac",
    ".ogg",
}
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f_]+')
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class TrackAudioSpec:
    sample_rate: int = 48000
    bit_depth: int = 24
    channels: int = 1
    file_format: str = "WAV"


@dataclass(frozen=True)
class AudioFileInfo:
    path: str
    sample_rate: int
    bit_depth: int
    channels: int
    format_tag: int


@dataclass(frozen=True)
class AudioFileCheck:
    path: str = ""
    exists: bool = False
    valid: bool = False
    info: AudioFileInfo | None = None
    problems: tuple[str, ...] = ()


@dataclass(frozen=True)
class TrackFileWarning:
    code: str
    message: str
    path: str = ""
    talent_id: int | None = None
    episode_number: int | None = None


@dataclass(frozen=True)
class TrackFileRow:
    episode_id: int
    episode_number: int
    character_id: int
    character_name: str
    aliases: tuple[str, ...]
    talent_id: int
    talent_name: str
    total_dialogues: int
    recorded_dialogues: int
    track_suggestion: str
    expected_filename: str
    output: AudioFileCheck
    delivered: AudioFileCheck
    file_status: str | None
    warnings: tuple[TrackFileWarning, ...] = ()


@dataclass(frozen=True)
class TrackFileHealth:
    total_tracks: int
    stemmed_tracks: int
    delivered_tracks: int
    total_episodes: int
    stemmed_episodes: int
    delivered_episodes: int
    warnings: int


@dataclass
class TrackFileInventory:
    rows: list[TrackFileRow] = field(default_factory=list)
    warnings: list[TrackFileWarning] = field(default_factory=list)
    output_folder: str = ""
    delivery_folder: str = ""

    def rows_for_talent(self, talent_id: int) -> list[TrackFileRow]:
        return [row for row in self.rows if row.talent_id == int(talent_id)]

    def health_for_talent(self, talent_id: int) -> TrackFileHealth:
        rows = self.rows_for_talent(talent_id)
        episode_rows: dict[int, list[TrackFileRow]] = {}
        for row in rows:
            episode_rows.setdefault(row.episode_number, []).append(row)

        stemmed_episodes = sum(
            1
            for group in episode_rows.values()
            if group and all(item.output.valid or item.delivered.valid for item in group)
        )
        delivered_episodes = sum(
            1
            for group in episode_rows.values()
            if group and all(item.delivered.valid for item in group)
        )

        row_warnings = sum(len(row.warnings) for row in rows)
        global_warnings = sum(
            1
            for warning in self.warnings
            if warning.talent_id in {None, int(talent_id)}
        )

        return TrackFileHealth(
            total_tracks=len(rows),
            stemmed_tracks=sum(
                1 for row in rows if row.output.valid or row.delivered.valid
            ),
            delivered_tracks=sum(1 for row in rows if row.delivered.valid),
            total_episodes=len(episode_rows),
            stemmed_episodes=stemmed_episodes,
            delivered_episodes=delivered_episodes,
            warnings=row_warnings + global_warnings,
        )


class TrackFileService:
    """Derive Stemmed/Delivered state from output + delivery filesystem folders."""

    def __init__(
        self,
        database: Database,
        *,
        output_folder: str = "",
        delivery_folder: str = "",
        audio_spec: TrackAudioSpec | None = None,
    ):
        self.database = database
        self.output_folder = str(output_folder or "").strip()
        self.delivery_folder = str(delivery_folder or "").strip()
        self.audio_spec = audio_spec or TrackAudioSpec()

    def scan_and_sync(self) -> TrackFileInventory:
        expectations = self._get_expectations()
        aliases = self._get_episode_aliases()

        output_files, output_warnings = self._scan_folder(
            self.output_folder,
            folder_code="OUTPUT",
            expectations=expectations,
        )
        delivery_files, delivery_warnings = self._scan_folder(
            self.delivery_folder,
            folder_code="DELIVERY",
            expectations=expectations,
        )

        rows: list[TrackFileRow] = []
        matched_output: set[str] = set()
        matched_delivery: set[str] = set()

        for item in expectations:
            key = (
                item["episode_id"],
                item["character_id"],
                item["talent_id"],
            )
            alias_names = aliases.get(key, ())
            suggestion = build_track_suggestion(
                item["episode_number"],
                item["character_name"],
                alias_names,
                item["talent_name"],
            )
            expected_filename = suggestion + ".wav"
            filename_key = expected_filename.casefold()

            output_path = output_files.get(filename_key)
            delivery_path = delivery_files.get(filename_key)
            if output_path is not None:
                matched_output.add(filename_key)
            if delivery_path is not None:
                matched_delivery.add(filename_key)

            output_check = self._check_audio(output_path)
            delivery_check = self._check_audio(delivery_path)
            row_warnings: list[TrackFileWarning] = []

            row_warnings.extend(
                self._audio_warnings(
                    output_check,
                    code="INVALID_OUTPUT_FORMAT",
                    label="Stem / Export",
                    item=item,
                )
            )
            row_warnings.extend(
                self._audio_warnings(
                    delivery_check,
                    code="INVALID_DELIVERY_FORMAT",
                    label="Delivered",
                    item=item,
                )
            )

            if delivery_check.valid and not output_check.exists:
                row_warnings.append(
                    TrackFileWarning(
                        code="DELIVERED_WITHOUT_OUTPUT",
                        message=(
                            f"{expected_filename} ada di SETORAN tetapi tidak ada "
                            "di folder Stem / Export."
                        ),
                        path=delivery_check.path,
                        talent_id=item["talent_id"],
                        episode_number=item["episode_number"],
                    )
                )

            if delivery_check.valid:
                file_status = DELIVERED
            elif output_check.valid:
                file_status = STEMMED
            else:
                file_status = None

            if (
                file_status is not None
                and int(item["recorded_dialogues"]) < int(item["total_dialogues"])
            ):
                row_warnings.append(
                    TrackFileWarning(
                        code="FILE_BEFORE_RECORDING_COMPLETE",
                        message=(
                            f"{expected_filename} sudah ada tetapi recording checkbox "
                            "belum lengkap."
                        ),
                        path=(
                            delivery_check.path
                            if delivery_check.valid
                            else output_check.path
                        ),
                        talent_id=item["talent_id"],
                        episode_number=item["episode_number"],
                    )
                )

            rows.append(
                TrackFileRow(
                    episode_id=item["episode_id"],
                    episode_number=item["episode_number"],
                    character_id=item["character_id"],
                    character_name=item["character_name"],
                    aliases=tuple(alias_names),
                    talent_id=item["talent_id"],
                    talent_name=item["talent_name"],
                    total_dialogues=item["total_dialogues"],
                    recorded_dialogues=item["recorded_dialogues"],
                    track_suggestion=suggestion,
                    expected_filename=expected_filename,
                    output=output_check,
                    delivered=delivery_check,
                    file_status=file_status,
                    warnings=tuple(row_warnings),
                )
            )

        warnings = output_warnings + delivery_warnings
        warnings.extend(
            self._unexpected_file_warnings(
                output_files,
                matched_output,
                expectations,
                folder_label="Stem / Export",
            )
        )
        warnings.extend(
            self._unexpected_file_warnings(
                delivery_files,
                matched_delivery,
                expectations,
                folder_label="SETORAN",
            )
        )

        self._sync_status_cache(rows)

        return TrackFileInventory(
            rows=rows,
            warnings=warnings,
            output_folder=self.output_folder,
            delivery_folder=self.delivery_folder,
        )

    def _get_expectations(self) -> list[dict[str, int | str]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    e.id AS episode_id,
                    e.episode_number,
                    c.id AS character_id,
                    c.name AS character_name,
                    t.id AS talent_id,
                    t.name AS talent_name,
                    COUNT(DISTINCT d.id) AS total_dialogues,
                    COUNT(
                        DISTINCT CASE
                            WHEN COALESCE(rs.is_recorded, 0) = 1 THEN d.id
                        END
                    ) AS recorded_dialogues
                FROM dialog_cast AS dc
                JOIN dialogues AS d
                  ON d.id = dc.dialogue_id
                 AND d.is_active = 1
                JOIN episodes AS e
                  ON e.id = d.episode_id
                 AND e.is_active = 1
                JOIN characters AS c
                  ON c.id = dc.character_id
                 AND c.is_active = 1
                JOIN talents AS t
                  ON t.id = dc.talent_id
                 AND t.is_active = 1
                LEFT JOIN recording_status AS rs
                  ON rs.dialogue_id = d.id
                GROUP BY
                    e.id,
                    e.episode_number,
                    c.id,
                    c.name,
                    t.id,
                    t.name
                ORDER BY
                    e.episode_number,
                    c.name COLLATE NOCASE,
                    t.name COLLATE NOCASE
                """
            ).fetchall()

        return [
            {
                "episode_id": int(row["episode_id"]),
                "episode_number": int(row["episode_number"]),
                "character_id": int(row["character_id"]),
                "character_name": str(row["character_name"]),
                "talent_id": int(row["talent_id"]),
                "talent_name": str(row["talent_name"]),
                "total_dialogues": int(row["total_dialogues"] or 0),
                "recorded_dialogues": int(row["recorded_dialogues"] or 0),
            }
            for row in rows
        ]

    def _get_episode_aliases(
        self,
    ) -> dict[tuple[int, int, int], tuple[str, ...]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    d.episode_id,
                    ca.canonical_character_id AS character_id,
                    cad.talent_id,
                    ca.alias_name,
                    MIN(COALESCE(d.source_row, 999999999)) AS first_source_row
                FROM character_alias_dialogue AS cad
                JOIN character_alias AS ca
                  ON ca.id = cad.alias_id
                JOIN dialogues AS d
                  ON d.id = cad.dialogue_id
                 AND d.is_active = 1
                WHERE cad.talent_id IS NOT NULL
                GROUP BY
                    d.episode_id,
                    ca.canonical_character_id,
                    cad.talent_id,
                    ca.id,
                    ca.alias_name
                ORDER BY
                    d.episode_id,
                    ca.canonical_character_id,
                    cad.talent_id,
                    first_source_row,
                    ca.alias_name COLLATE NOCASE
                """
            ).fetchall()

        grouped: dict[tuple[int, int, int], list[str]] = {}
        for row in rows:
            key = (
                int(row["episode_id"]),
                int(row["character_id"]),
                int(row["talent_id"]),
            )
            name = str(row["alias_name"]).strip()
            if not name:
                continue
            existing = {item.casefold() for item in grouped.setdefault(key, [])}
            if name.casefold() not in existing:
                grouped[key].append(name)

        return {key: tuple(value) for key, value in grouped.items()}

    def _scan_folder(
        self,
        raw_folder: str,
        *,
        folder_code: str,
        expectations: list[dict[str, int | str]],
    ) -> tuple[dict[str, Path], list[TrackFileWarning]]:
        if not raw_folder:
            return {}, [
                TrackFileWarning(
                    code=f"{folder_code}_FOLDER_NOT_CONFIGURED",
                    message=f"{folder_code.title()} folder belum diatur di Project Settings.",
                )
            ]

        folder = Path(raw_folder)
        if not folder.is_dir():
            return {}, [
                TrackFileWarning(
                    code=f"{folder_code}_FOLDER_MISSING",
                    message=f"Folder tidak ditemukan: {folder}",
                    path=str(folder),
                )
            ]

        talent_tokens = {
            sanitize_filename_component(str(item["talent_name"])).casefold():
            int(item["talent_id"])
            for item in expectations
        }

        files: dict[str, Path] = {}
        warnings: list[TrackFileWarning] = []
        for child in folder.iterdir():
            if not child.is_file() or child.name.startswith("~$"):
                continue
            suffix = child.suffix.casefold()
            talent_id = _infer_talent_id(child.stem, talent_tokens)

            if suffix == ".wav":
                key = child.name.casefold()
                if key in files:
                    warnings.append(
                        TrackFileWarning(
                            code=f"DUPLICATE_{folder_code}_FILE",
                            message=f"Nama file duplikat: {child.name}",
                            path=str(child),
                            talent_id=talent_id,
                        )
                    )
                else:
                    files[key] = child
            elif suffix in _AUDIO_LIKE_SUFFIXES:
                warnings.append(
                    TrackFileWarning(
                        code=f"UNSUPPORTED_{folder_code}_AUDIO",
                        message=f"File audio harus WAV: {child.name}",
                        path=str(child),
                        talent_id=talent_id,
                    )
                )

        return files, warnings

    def _check_audio(self, path: Path | None) -> AudioFileCheck:
        if path is None:
            return AudioFileCheck()

        try:
            info = inspect_wav(path)
        except Exception as exc:
            return AudioFileCheck(
                path=str(path),
                exists=True,
                valid=False,
                problems=(f"WAV tidak dapat dibaca: {exc}",),
            )

        problems: list[str] = []
        if info.sample_rate != int(self.audio_spec.sample_rate):
            problems.append(
                f"sample rate {info.sample_rate} Hz, expected {self.audio_spec.sample_rate} Hz"
            )
        if info.bit_depth != int(self.audio_spec.bit_depth):
            problems.append(
                f"bit depth {info.bit_depth}, expected {self.audio_spec.bit_depth}"
            )
        if info.channels != int(self.audio_spec.channels):
            channel_label = "mono" if info.channels == 1 else f"{info.channels} channels"
            expected = (
                "mono"
                if int(self.audio_spec.channels) == 1
                else f"{self.audio_spec.channels} channels"
            )
            problems.append(f"{channel_label}, expected {expected}")
        if info.format_tag not in {1, 0xFFFE}:
            problems.append(f"WAV compression format {info.format_tag} bukan PCM")

        return AudioFileCheck(
            path=str(path),
            exists=True,
            valid=not problems,
            info=info,
            problems=tuple(problems),
        )

    @staticmethod
    def _audio_warnings(
        check: AudioFileCheck,
        *,
        code: str,
        label: str,
        item: dict[str, int | str],
    ) -> list[TrackFileWarning]:
        if not check.exists or check.valid:
            return []
        detail = "; ".join(check.problems) or "format audio tidak sesuai"
        return [
            TrackFileWarning(
                code=code,
                message=f"{label}: {Path(check.path).name} — {detail}.",
                path=check.path,
                talent_id=int(item["talent_id"]),
                episode_number=int(item["episode_number"]),
            )
        ]

    @staticmethod
    def _unexpected_file_warnings(
        files: dict[str, Path],
        matched: set[str],
        expectations: list[dict[str, int | str]],
        *,
        folder_label: str,
    ) -> list[TrackFileWarning]:
        talent_tokens = {
            sanitize_filename_component(str(item["talent_name"])).casefold():
            int(item["talent_id"])
            for item in expectations
        }
        warnings: list[TrackFileWarning] = []
        for key, path in files.items():
            if key in matched:
                continue
            warnings.append(
                TrackFileWarning(
                    code="UNEXPECTED_TRACK_FILE",
                    message=f"{folder_label}: file tidak cocok dengan expected track: {path.name}",
                    path=str(path),
                    talent_id=_infer_talent_id(path.stem, talent_tokens),
                )
            )
        return warnings

    def _sync_status_cache(self, rows: list[TrackFileRow]) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self.database.connect() as connection:
            for row in rows:
                existing = connection.execute(
                    """
                    SELECT status, note
                    FROM stem_status
                    WHERE episode_id = ?
                      AND talent_id = ?
                      AND character_id = ?
                    """,
                    (
                        row.episode_id,
                        row.talent_id,
                        row.character_id,
                    ),
                ).fetchone()

                if existing is not None and str(existing["status"]) == REVISION:
                    continue

                if row.file_status in {STEMMED, DELIVERED}:
                    connection.execute(
                        """
                        INSERT INTO stem_status(
                            episode_id, talent_id, character_id,
                            status, note, updated_at
                        )
                        VALUES(?, ?, ?, ?, ?, ?)
                        ON CONFLICT(episode_id, talent_id, character_id)
                        DO UPDATE SET
                            status = excluded.status,
                            note = excluded.note,
                            updated_at = excluded.updated_at
                        """,
                        (
                            row.episode_id,
                            row.talent_id,
                            row.character_id,
                            row.file_status,
                            AUTO_FILE_STATUS_NOTE,
                            now,
                        ),
                    )
                    continue

                connection.execute(
                    """
                    DELETE FROM stem_status
                    WHERE episode_id = ?
                      AND talent_id = ?
                      AND character_id = ?
                      AND (
                          status = ?
                          OR note = ?
                      )
                    """,
                    (
                        row.episode_id,
                        row.talent_id,
                        row.character_id,
                        READY_TO_STEM,
                        AUTO_FILE_STATUS_NOTE,
                    ),
                )


def sanitize_filename_component(value: str, *, uppercase: bool = False) -> str:
    text = _INVALID_FILENAME_CHARS.sub(" ", str(value or ""))
    text = _WHITESPACE.sub(" ", text).strip(" .")
    if uppercase:
        text = text.upper()
    return text or "UNKNOWN"


def build_track_suggestion(
    episode_number: int,
    canonical_character: str,
    aliases: tuple[str, ...] | list[str],
    talent_name: str,
) -> str:
    canonical = sanitize_filename_component(canonical_character, uppercase=True)
    alias_parts: list[str] = []
    seen = {canonical.casefold()}
    for alias in aliases:
        clean = sanitize_filename_component(alias, uppercase=True)
        if clean.casefold() in seen:
            continue
        seen.add(clean.casefold())
        alias_parts.append(clean)

    character_part = " ".join([canonical, *alias_parts])
    talent_part = sanitize_filename_component(talent_name)
    return f"{int(episode_number)}_{character_part}_{talent_part}"


def inspect_wav(path: str | Path) -> AudioFileInfo:
    wav_path = Path(path)
    with wav_path.open("rb") as handle:
        header = handle.read(12)
        if len(header) != 12 or header[:4] not in {b"RIFF", b"RF64"} or header[8:] != b"WAVE":
            raise ValueError("bukan RIFF/WAVE")

        format_tag = channels = sample_rate = bit_depth = None
        while True:
            chunk_header = handle.read(8)
            if len(chunk_header) < 8:
                break
            chunk_id, chunk_size = struct.unpack("<4sI", chunk_header)
            data = handle.read(chunk_size)
            if chunk_size % 2:
                handle.read(1)

            if chunk_id == b"fmt ":
                if len(data) < 16:
                    raise ValueError("chunk fmt terlalu pendek")
                (
                    format_tag,
                    channels,
                    sample_rate,
                    _byte_rate,
                    _block_align,
                    bit_depth,
                ) = struct.unpack("<HHIIHH", data[:16])
                break

        if None in {format_tag, channels, sample_rate, bit_depth}:
            raise ValueError("chunk fmt tidak ditemukan")

    return AudioFileInfo(
        path=str(wav_path),
        sample_rate=int(sample_rate),
        bit_depth=int(bit_depth),
        channels=int(channels),
        format_tag=int(format_tag),
    )


def _infer_talent_id(
    stem: str,
    talent_tokens: dict[str, int],
) -> int | None:
    if "_" not in stem:
        return None
    talent_part = sanitize_filename_component(stem.rsplit("_", 1)[-1]).casefold()
    return talent_tokens.get(talent_part)
