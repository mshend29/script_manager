from __future__ import annotations

import sys
import time

from core.version import APP_VERSION
from services.update_service import (
    UpdateCheckError,
    UpdateService,
    UpdateStatus,
)


def verify_published_release(
    *,
    attempts: int = 6,
    delay_seconds: float = 5.0,
) -> int:
    last_error = ""

    for attempt in range(1, max(1, int(attempts)) + 1):
        try:
            result = UpdateService(
                current_version=APP_VERSION,
                timeout_seconds=15.0,
            ).check()
        except UpdateCheckError as exc:
            last_error = str(exc)
        else:
            if (
                result.status == UpdateStatus.UP_TO_DATE
                and result.latest_version == APP_VERSION
                and result.release_url
            ):
                print(
                    "Published release verified by UpdateService: "
                    f"{result.latest_version} -> {result.release_url}"
                )
                return 0

            last_error = (
                "latest release mismatch: "
                f"status={result.status.value}, "
                f"latest={result.latest_version!r}, "
                f"expected={APP_VERSION!r}"
            )

        if attempt < attempts:
            time.sleep(max(0.0, float(delay_seconds)))

    print(
        "Published release was not visible to UpdateService: "
        f"{last_error}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(verify_published_release())
