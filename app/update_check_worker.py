from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from services.update_service import UpdateService


class UpdateCheckWorker(QObject):
    completed = Signal(object)
    failed = Signal(object)

    def __init__(self, service: UpdateService | None = None):
        super().__init__()
        self.service = service or UpdateService()

    @Slot()
    def run(self) -> None:
        try:
            result = self.service.check()
        except Exception as exc:
            self.failed.emit(exc)
            return

        self.completed.emit(result)
