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

    project_folder: str = ""
    source_folder: str = ""

    episode_before: str = ""
    episode_after: str = ""

    main_drive_url: str = ""
    material_drive_url: str = ""
    delivery_drive_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectSettings":
        allowed = cls.__dataclass_fields__.keys()
        cleaned = {key: value for key, value in data.items() if key in allowed}
        return cls(**cleaned)

    def normalized(self) -> "ProjectSettings":
        data = self.to_dict()

        for key in ("project_folder", "source_folder"):
            value = str(data.get(key, "") or "").strip()
            if value:
                data[key] = str(Path(value).expanduser())

        for key, value in data.items():
            if isinstance(value, str):
                data[key] = value.strip()

        return ProjectSettings.from_dict(data)
