from __future__ import annotations

from dataclasses import dataclass, field


DATA_PAGE_NAMES = frozenset({"SCRIPT", "DIALOG", "TRACKING", "DATA"})


@dataclass
class ProjectDataRevisionState:
    """Track which data workspaces need a database reload.

    This object is intentionally Qt-free so the refresh contract can be tested
    in the lightweight CI environment. MainWindow owns the Qt signal that
    announces revision changes.
    """

    revision: int = 0
    _dirty_pages: set[str] = field(default_factory=set)

    @property
    def dirty_pages(self) -> frozenset[str]:
        return frozenset(self._dirty_pages)

    def reset(self, *, mark_dirty: bool = False) -> None:
        self.revision = 0
        self._dirty_pages.clear()
        if mark_dirty:
            self._dirty_pages.update(DATA_PAGE_NAMES)

    def mark_changed(self) -> int:
        self.revision += 1
        self._dirty_pages.update(DATA_PAGE_NAMES)
        return self.revision

    def mark_all_dirty(self) -> None:
        self._dirty_pages.update(DATA_PAGE_NAMES)

    def mark_dirty(self, page_name: str) -> None:
        normalized = str(page_name or "").strip().upper()
        if normalized in DATA_PAGE_NAMES:
            self._dirty_pages.add(normalized)

    def is_dirty(self, page_name: str) -> bool:
        return str(page_name).upper() in self._dirty_pages

    def consume(self, page_name: str) -> bool:
        normalized = str(page_name).upper()
        if normalized not in self._dirty_pages:
            return False
        self._dirty_pages.remove(normalized)
        return True

    def mark_clean(self, page_name: str) -> None:
        self._dirty_pages.discard(str(page_name).upper())
