from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal


SUPPORTED_AUDIO_SAMPLE_RATES = (44100, 48000, 96000, 192000)
SUPPORTED_AUDIO_BIT_DEPTHS = (16, 24, 32)
SUPPORTED_AUDIO_CHANNELS = (1, 2)

PROJECT_SETTINGS_FIELD_GROUPS: dict[str, tuple[str, ...]] = {
    "identity": (
        "project_name",
        "project_code",
        "client_name",
        "start_date",
    ),
    "source": (
        "source_folder",
        "episode_before",
        "episode_after",
    ),
    "audio": (
        "stem_output_folder",
        "delivery_folder",
        "audio_format",
        "audio_sample_rate",
        "audio_bit_depth",
        "audio_channels",
    ),
    "links": (
        "main_drive_url",
        "material_drive_url",
        "delivery_drive_url",
    ),
}

# The destination directory for a brand-new .smproj is intentionally transient
# wizard state. ``project_folder`` remains the runtime/read-only path of an
# already-created project file and is not persisted in project settings.
NEW_PROJECT_BLOCKING_FIELDS = frozenset(
    {
        "project_name",
        "project_code",
        "client_name",
        "start_date",
        "source_folder",
        "stem_output_folder",
        "delivery_folder",
        "audio_format",
        "audio_sample_rate",
        "audio_bit_depth",
        "audio_channels",
    }
)
NEW_PROJECT_OPTIONAL_FIELDS = frozenset(
    {
        "main_drive_url",
        "material_drive_url",
        "delivery_drive_url",
    }
)
NEW_PROJECT_WARNING_FIELDS = frozenset(
    {
        "episode_before",
        "episode_after",
    }
)


@dataclass(frozen=True)
class ProjectSettingsIssue:
    field: str
    message: str
    severity: Literal["error", "warning"] = "error"


@dataclass
class ProjectSettings:
    project_name: str = ""
    project_code: str = ""
    client_name: str = ""
    start_date: str = field(default_factory=lambda: date.today().isoformat())

    # Runtime-only display value. For .smproj projects this contains the
    # current project file path and is intentionally not persisted.
    project_folder: str = ""

    source_folder: str = ""
    stem_output_folder: str = ""
    delivery_folder: str = ""

    audio_format: str = "WAV"
    audio_sample_rate: int = 48000
    audio_bit_depth: int = 24
    audio_channels: int = 1

    episode_before: str = ""
    episode_after: str = ""

    main_drive_url: str = ""
    material_drive_url: str = ""
    delivery_drive_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_persistent_dict(self) -> dict[str, Any]:
        data = self.to_dict()
        data.pop("project_folder", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectSettings":
        allowed = cls.__dataclass_fields__.keys()
        cleaned = {key: value for key, value in data.items() if key in allowed}
        return cls(**cleaned)

    def normalized(self) -> "ProjectSettings":
        """Single normalization path shared by New Project and Settings."""
        data = self.to_dict()

        for key in (
            "project_folder",
            "source_folder",
            "stem_output_folder",
            "delivery_folder",
        ):
            value = str(data.get(key, "") or "").strip()
            if value:
                data[key] = str(Path(value).expanduser())

        for key, value in data.items():
            if isinstance(value, str):
                data[key] = value.strip()

        data["audio_format"] = "WAV"

        sample_rate = int(data.get("audio_sample_rate", 48000) or 48000)
        data["audio_sample_rate"] = (
            sample_rate
            if sample_rate in SUPPORTED_AUDIO_SAMPLE_RATES
            else 48000
        )

        bit_depth = int(data.get("audio_bit_depth", 24) or 24)
        data["audio_bit_depth"] = (
            bit_depth
            if bit_depth in SUPPORTED_AUDIO_BIT_DEPTHS
            else 24
        )

        channels = int(data.get("audio_channels", 1) or 1)
        data["audio_channels"] = (
            channels
            if channels in SUPPORTED_AUDIO_CHANNELS
            else 1
        )

        return ProjectSettings.from_dict(data)


def validate_project_settings_contract(
    settings: ProjectSettings,
    *,
    strict_new_project: bool = False,
) -> tuple[ProjectSettingsIssue, ...]:
    """Validate field presence and supported persisted values only.

    Filesystem reachability, delimiter/source validation, URL syntax, and
    workbook preflight belong to their dedicated Phase 11 validation gates.
    """
    normalized = settings.normalized()
    issues: list[ProjectSettingsIssue] = []

    identity_required = (
        ("project_name", "Nama Proyek wajib diisi."),
        ("project_code", "Kode Proyek wajib diisi."),
        ("client_name", "Klien wajib diisi."),
        ("start_date", "Tanggal Mulai wajib diisi."),
    )
    for field_name, message in identity_required:
        if not str(getattr(normalized, field_name, "") or "").strip():
            issues.append(ProjectSettingsIssue(field_name, message))

    if strict_new_project:
        for field_name, message in (
            ("source_folder", "Folder Sumber Naskah wajib diisi."),
            (
                "stem_output_folder",
                "Folder Stem / Mixdown / Export wajib diisi.",
            ),
            ("delivery_folder", "Folder Setoran wajib diisi."),
        ):
            if not str(getattr(normalized, field_name, "") or "").strip():
                issues.append(ProjectSettingsIssue(field_name, message))

    return tuple(issues)
