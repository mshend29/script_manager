from __future__ import annotations

import io
import json
from urllib.error import HTTPError, URLError

import pytest

from services import update_service as update_service_module
from services.update_service import (
    UpdateCheckError,
    UpdateService,
    UpdateStatus,
)


class FakeResponse:
    def __init__(self, payload: dict):
        self._data = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._data


def test_update_available_when_latest_release_is_newer(monkeypatch):
    monkeypatch.setattr(
        update_service_module,
        "urlopen",
        lambda request, timeout: FakeResponse(
            {
                "tag_name": "v0.2.0",
                "name": "Script Manager 0.2.0",
                "html_url": "https://example.com/releases/v0.2.0",
                "published_at": "2026-08-28T10:00:00Z",
            }
        ),
    )

    result = UpdateService(current_version="0.1.0").check()

    assert result.status == UpdateStatus.UPDATE_AVAILABLE
    assert result.update_available
    assert result.has_release
    assert result.current_version == "0.1.0"
    assert result.latest_version == "0.2.0"
    assert result.release_name == "Script Manager 0.2.0"
    assert result.release_url.endswith("/v0.2.0")


def test_up_to_date_when_latest_release_matches_current(monkeypatch):
    monkeypatch.setattr(
        update_service_module,
        "urlopen",
        lambda request, timeout: FakeResponse(
            {
                "tag_name": "v0.1.0",
                "name": "Script Manager 0.1.0",
                "html_url": "https://example.com/releases/v0.1.0",
            }
        ),
    )

    result = UpdateService(current_version="0.1.0").check()

    assert result.status == UpdateStatus.UP_TO_DATE
    assert not result.update_available
    assert result.latest_version == "0.1.0"


def test_no_release_is_valid_status_not_error(monkeypatch):
    def no_release(request, timeout):
        raise HTTPError(
            url="https://api.example.com/releases/latest",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=io.BytesIO(),
        )

    monkeypatch.setattr(
        update_service_module,
        "urlopen",
        no_release,
    )

    result = UpdateService(
        current_version="0.1.0",
        releases_url="https://example.com/releases",
    ).check()

    assert result.status == UpdateStatus.NO_RELEASE
    assert not result.has_release
    assert result.release_url == "https://example.com/releases"


def test_network_failure_becomes_update_check_error(monkeypatch):
    def offline(request, timeout):
        raise URLError("offline")

    monkeypatch.setattr(
        update_service_module,
        "urlopen",
        offline,
    )

    with pytest.raises(
        UpdateCheckError,
        match="Tidak dapat terhubung",
    ):
        UpdateService(current_version="0.1.0").check()


def test_invalid_release_tag_is_rejected(monkeypatch):
    monkeypatch.setattr(
        update_service_module,
        "urlopen",
        lambda request, timeout: FakeResponse(
            {
                "tag_name": "release-next",
                "html_url": "https://example.com/releases/next",
            }
        ),
    )

    with pytest.raises(
        UpdateCheckError,
        match="Format version tidak didukung",
    ):
        UpdateService(current_version="0.1.0").check()
