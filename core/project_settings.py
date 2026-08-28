from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any


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
            if sample_rate in {44100, 48000, 96000, 192000}
            else 48000
        )

        bit_depth = int(data.get("audio_bit_depth", 24) or 24)
        data["audio_bit_depth"] = (
            bit_depth if bit_depth in {16, 24, 32} else 24
        )

        channels = int(data.get("audio_channels", 1) or 1)
        data["audio_channels"] = channels if channels in {1, 2} else 1

        return ProjectSettings.from_dict(data)
