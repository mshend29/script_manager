from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.version import (
    APP_NAME,
    APP_VERSION,
    GITHUB_LATEST_RELEASE_API,
    GITHUB_RELEASES_URL,
)


_VERSION_RE = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:[-+].*)?$",
    re.IGNORECASE,
)


class UpdateStatus(str, Enum):
    UPDATE_AVAILABLE = "UPDATE_AVAILABLE"
    UP_TO_DATE = "UP_TO_DATE"
    NO_RELEASE = "NO_RELEASE"


@dataclass(frozen=True)
class UpdateCheckResult:
    status: UpdateStatus
    current_version: str
    latest_version: str = ""
    release_name: str = ""
    release_url: str = ""
    published_at: str = ""

    @property
    def has_release(self) -> bool:
        return bool(self.latest_version)

    @property
    def update_available(self) -> bool:
        return self.status == UpdateStatus.UPDATE_AVAILABLE


class UpdateCheckError(RuntimeError):
    pass


class UpdateService:
    def __init__(
        self,
        *,
        current_version: str = APP_VERSION,
        api_url: str = GITHUB_LATEST_RELEASE_API,
        releases_url: str = GITHUB_RELEASES_URL,
        timeout_seconds: float = 8.0,
    ):
        self.current_version = str(current_version).strip()
        self.api_url = str(api_url).strip()
        self.releases_url = str(releases_url).strip()
        self.timeout_seconds = max(1.0, float(timeout_seconds))

    def check(self) -> UpdateCheckResult:
        current = self._parse_version(self.current_version)

        request = Request(
            self.api_url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"{APP_NAME}/{self.current_version}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                payload = json.loads(
                    response.read().decode("utf-8")
                )
        except HTTPError as exc:
            if exc.code == 404:
                return UpdateCheckResult(
                    status=UpdateStatus.NO_RELEASE,
                    current_version=self.current_version,
                    release_url=self.releases_url,
                )
            raise UpdateCheckError(
                f"Update server merespons HTTP {exc.code}."
            ) from exc
        except URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise UpdateCheckError(
                f"Tidak dapat terhubung ke update server: {reason}"
            ) from exc
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise UpdateCheckError(
                "Respons update server tidak dapat dibaca."
            ) from exc

        if not isinstance(payload, dict):
            raise UpdateCheckError(
                "Respons update server tidak valid."
            )

        tag = str(payload.get("tag_name", "") or "").strip()
        if not tag:
            raise UpdateCheckError(
                "Release terbaru tidak memiliki version tag."
            )

        latest = self._parse_version(tag)
        status = (
            UpdateStatus.UPDATE_AVAILABLE
            if latest > current
            else UpdateStatus.UP_TO_DATE
        )

        return UpdateCheckResult(
            status=status,
            current_version=self.current_version,
            latest_version=self._format_version(latest),
            release_name=str(
                payload.get("name", "") or tag
            ).strip(),
            release_url=str(
                payload.get("html_url", "") or self.releases_url
            ).strip(),
            published_at=str(
                payload.get("published_at", "") or ""
            ).strip(),
        )

    @staticmethod
    def _parse_version(value: str) -> tuple[int, int, int]:
        text = str(value or "").strip()
        match = _VERSION_RE.fullmatch(text)
        if match is None:
            raise UpdateCheckError(
                f"Format version tidak didukung: {text!r}."
            )
        return (
            int(match.group("major")),
            int(match.group("minor")),
            int(match.group("patch")),
        )

    @staticmethod
    def _format_version(value: tuple[int, int, int]) -> str:
        return ".".join(str(part) for part in value)
