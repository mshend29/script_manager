from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from core.project_settings import (
    SUPPORTED_AUDIO_BIT_DEPTHS,
    SUPPORTED_AUDIO_CHANNELS,
    SUPPORTED_AUDIO_SAMPLE_RATES,
    ProjectSettings,
)
from services.project_setup_validation import (
    SetupValidationIssue,
    looks_like_browser_url,
)


@dataclass(frozen=True)
class AudioFolderState:
    field: str
    label: str
    path: Path | None
    exists: bool = False
    can_create: bool = False


@dataclass(frozen=True)
class AudioSetupValidation:
    stem_folder: AudioFolderState
    delivery_folder: AudioFolderState
    issues: tuple[SetupValidationIssue, ...]

    @property
    def errors(self) -> tuple[SetupValidationIssue, ...]:
        return tuple(
            issue for issue in self.issues if issue.severity == "error"
        )

    @property
    def is_valid(self) -> bool:
        return not self.errors


def validate_audio_setup(
    settings: ProjectSettings,
    *,
    verify_writable: bool = False,
) -> AudioSetupValidation:
    issues: list[SetupValidationIssue] = []

    stem_state = _validate_folder(
        field="stem_output_folder",
        label="Folder Stem / Mixdown / Export",
        raw_value=settings.stem_output_folder,
        issues=issues,
        verify_writable=verify_writable,
    )
    delivery_state = _validate_folder(
        field="delivery_folder",
        label="Folder Setoran",
        raw_value=settings.delivery_folder,
        issues=issues,
        verify_writable=verify_writable,
    )

    if str(settings.audio_format or "").strip().upper() != "WAV":
        issues.append(
            SetupValidationIssue(
                "audio_format",
                "Format audio proyek baru harus WAV.",
            )
        )

    if settings.audio_sample_rate not in SUPPORTED_AUDIO_SAMPLE_RATES:
        issues.append(
            SetupValidationIssue(
                "audio_sample_rate",
                "Laju Sampel tidak didukung aplikasi.",
            )
        )

    if settings.audio_bit_depth not in SUPPORTED_AUDIO_BIT_DEPTHS:
        issues.append(
            SetupValidationIssue(
                "audio_bit_depth",
                "Kedalaman Bit tidak didukung aplikasi.",
            )
        )

    if settings.audio_channels not in SUPPORTED_AUDIO_CHANNELS:
        issues.append(
            SetupValidationIssue(
                "audio_channels",
                "Konfigurasi Kanal tidak didukung aplikasi.",
            )
        )

    return AudioSetupValidation(
        stem_folder=stem_state,
        delivery_folder=delivery_state,
        issues=tuple(issues),
    )


def create_audio_output_folder(folder: str | Path) -> Path:
    raw = str(folder or "").strip()
    if not raw:
        raise ValueError("Folder output belum diisi.")
    if looks_like_browser_url(raw):
        raise ValueError(
            "Folder output harus berupa filesystem path, bukan URL browser."
        )

    path = Path(raw).expanduser()
    if path.exists() and not path.is_dir():
        raise ValueError("Path output bukan folder.")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _validate_folder(
    *,
    field: str,
    label: str,
    raw_value: str,
    issues: list[SetupValidationIssue],
    verify_writable: bool,
) -> AudioFolderState:
    raw = str(raw_value or "").strip()
    if not raw:
        issues.append(
            SetupValidationIssue(field, f"{label} wajib diisi.")
        )
        return AudioFolderState(field=field, label=label, path=None)

    if looks_like_browser_url(raw):
        issues.append(
            SetupValidationIssue(
                field,
                f"{label} harus berupa filesystem path, bukan URL browser.",
            )
        )
        return AudioFolderState(field=field, label=label, path=None)

    path = Path(raw).expanduser()
    if not path.exists():
        nearest = _nearest_existing_parent(path)
        can_create = bool(
            nearest is not None
            and nearest.is_dir()
            and os.access(nearest, os.W_OK)
        )
        message = (
            f"{label} belum ada. Klik Buat Folder untuk membuatnya."
            if can_create
            else f"{label} belum ada dan parent-nya tidak dapat ditulis."
        )
        issues.append(SetupValidationIssue(field, message))
        return AudioFolderState(
            field=field,
            label=label,
            path=path,
            exists=False,
            can_create=can_create,
        )

    if not path.is_dir():
        issues.append(
            SetupValidationIssue(field, f"{label} bukan folder.")
        )
        return AudioFolderState(
            field=field,
            label=label,
            path=path,
            exists=True,
        )

    if not os.access(path, os.R_OK):
        issues.append(
            SetupValidationIssue(field, f"{label} tidak dapat dibaca.")
        )
    if not os.access(path, os.W_OK):
        issues.append(
            SetupValidationIssue(field, f"{label} tidak dapat ditulis.")
        )
    elif verify_writable:
        error = _probe_directory_write(path)
        if error:
            issues.append(
                SetupValidationIssue(
                    field,
                    f"{label} tidak dapat ditulis: {error}",
                )
            )

    return AudioFolderState(
        field=field,
        label=label,
        path=path,
        exists=True,
        can_create=False,
    )


def _nearest_existing_parent(path: Path) -> Path | None:
    candidate = path
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            return None
        candidate = parent
    return candidate


def _probe_directory_write(path: Path) -> str:
    probe_path: Path | None = None
    handle = None
    try:
        handle = tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=".script_manager_audio_write_test_",
            dir=path,
            delete=False,
        )
        probe_path = Path(handle.name)
        handle.write(b"ok")
        handle.flush()
        os.fsync(handle.fileno())
    except OSError as exc:
        return str(exc)
    finally:
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
        if probe_path is not None:
            try:
                probe_path.unlink(missing_ok=True)
            except OSError:
                pass
    return ""
