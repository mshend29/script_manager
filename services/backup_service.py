from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

from core.database import Database


_SAFE_REASON = re.compile(r"[^a-z0-9_-]+")


class BackupService:
    def __init__(self, database: Database, *, keep: int = 20):
        self.database = database
        self.keep = max(1, int(keep))

    def create(self, reason: str = "manual") -> Path:
        backup_dir = self.database.path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        reason_key = _SAFE_REASON.sub(
            "-",
            str(reason or "manual").strip().casefold(),
        ).strip("-") or "manual"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        target = backup_dir / f"project_{reason_key}_{stamp}.db"

        with self.database.connect() as source:
            destination = sqlite3.connect(target)
            try:
                source.backup(destination)
            finally:
                destination.close()

        self._prune(backup_dir)
        return target

    def list_backups(self) -> list[Path]:
        backup_dir = self.database.path.parent / "backups"
        if not backup_dir.exists():
            return []
        return sorted(
            backup_dir.glob("project_*.db"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

    def _prune(self, backup_dir: Path) -> None:
        backups = sorted(
            backup_dir.glob("project_*.db"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for stale in backups[self.keep:]:
            try:
                stale.unlink()
            except OSError:
                pass
