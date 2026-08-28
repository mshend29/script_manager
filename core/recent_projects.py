from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from core.app_paths import app_data_root


RECENT_PROJECTS_LIMIT = 10


@dataclass(frozen=True)
class RecentProject:
    project_id: str
    project_name: str
    file_path: str
    last_opened_at: str


class RecentProjectsStore:
    def __init__(
        self,
        path: str | Path | None = None,
        *,
        limit: int = RECENT_PROJECTS_LIMIT,
    ):
        self.path = (
            Path(path).expanduser()
            if path is not None
            else app_data_root() / "recent_projects.json"
        )
        self.limit = max(1, int(limit))

    def list(self, *, existing_only: bool = False) -> list[RecentProject]:
        items = self._read()
        if existing_only:
            items = [
                item
                for item in items
                if Path(item.file_path).expanduser().is_file()
            ]
        return items[: self.limit]

    def add(
        self,
        *,
        project_id: str,
        project_name: str,
        file_path: str | Path,
    ) -> RecentProject:
        resolved = str(
            Path(file_path).expanduser().resolve(strict=False)
        )
        item = RecentProject(
            project_id=str(project_id or "").strip(),
            project_name=str(project_name or "").strip(),
            file_path=resolved,
            last_opened_at=datetime.now().isoformat(timespec="seconds"),
        )

        existing = [
            row
            for row in self._read()
            if (
                row.project_id != item.project_id
                and Path(row.file_path).expanduser().resolve(strict=False)
                != Path(item.file_path).expanduser().resolve(strict=False)
            )
        ]
        self._write([item, *existing][: self.limit])
        return item

    def remove_path(self, file_path: str | Path) -> None:
        target = Path(file_path).expanduser().resolve(strict=False)
        self._write(
            [
                item
                for item in self._read()
                if Path(item.file_path).expanduser().resolve(strict=False)
                != target
            ]
        )

    def replace_project_path(
        self,
        *,
        project_id: str,
        old_path: str | Path,
        new_path: str | Path,
        project_name: str,
    ) -> RecentProject:
        self.remove_path(old_path)
        return self.add(
            project_id=project_id,
            project_name=project_name,
            file_path=new_path,
        )

    def _read(self) -> list[RecentProject]:
        if not self.path.is_file():
            return []

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return []

        if not isinstance(payload, list):
            return []

        result: list[RecentProject] = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            try:
                item = RecentProject(
                    project_id=str(row.get("project_id", "") or "").strip(),
                    project_name=str(row.get("project_name", "") or "").strip(),
                    file_path=str(row.get("file_path", "") or "").strip(),
                    last_opened_at=str(
                        row.get("last_opened_at", "") or ""
                    ).strip(),
                )
            except Exception:
                continue
            if not item.file_path:
                continue
            result.append(item)
        return result[: self.limit]

    def _write(self, items: Iterable[RecentProject]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(item) for item in items]
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp.replace(self.path)
