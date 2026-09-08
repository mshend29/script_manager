from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from typing import Callable


GOOGLE_DRIVE_UNINSTALL_GUID = "{6BBAE539-2232-434A-A4E5-9A33560C6283}"
GOOGLE_DRIVE_UNINSTALL_SUBKEY = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\"
    + GOOGLE_DRIVE_UNINSTALL_GUID
)
GOOGLE_DRIVE_OFFICIAL_DOWNLOAD_URL = (
    "https://dl.google.com/drive-file-stream/GoogleDriveSetup.exe"
)


class GoogleDriveInstallState(str, Enum):
    UNSUPPORTED_SYSTEM = "UNSUPPORTED_SYSTEM"
    NOT_INSTALLED = "NOT_INSTALLED"
    INSTALLED = "INSTALLED"
    CHECK_ERROR = "CHECK_ERROR"


@dataclass(frozen=True)
class GoogleDriveRegistryEntry:
    display_name: str = ""
    display_version: str = ""
    install_location: str = ""
    uninstall_string: str = ""
    registry_view: str = ""


@dataclass(frozen=True)
class GoogleDriveInstallationReport:
    state: GoogleDriveInstallState
    display_name: str = ""
    display_version: str = ""
    install_location: str = ""
    evidence: str = ""
    error: str = ""

    @property
    def installed(self) -> bool:
        return self.state == GoogleDriveInstallState.INSTALLED


RegistryProbe = Callable[[], GoogleDriveRegistryEntry | None]


class GoogleDriveInstallationDetector:
    """Detect the documented Google Drive for desktop Windows installation.

    The detector deliberately answers only whether the product is installed.
    Google account sign-in and project-folder readiness remain separate
    application-level concerns.
    """

    def __init__(
        self,
        *,
        platform_name: str | None = None,
        registry_probe: RegistryProbe | None = None,
    ) -> None:
        self.platform_name = str(platform_name or sys.platform)
        self.registry_probe = registry_probe or _probe_google_drive_registry

    def detect(self) -> GoogleDriveInstallationReport:
        if self.platform_name != "win32":
            return GoogleDriveInstallationReport(
                state=GoogleDriveInstallState.UNSUPPORTED_SYSTEM,
                evidence="Google Drive Windows prerequisite check skipped on non-Windows OS.",
            )

        try:
            entry = self.registry_probe()
        except Exception as exc:  # pragma: no cover - platform/backend boundary
            return GoogleDriveInstallationReport(
                state=GoogleDriveInstallState.CHECK_ERROR,
                evidence=GOOGLE_DRIVE_UNINSTALL_SUBKEY,
                error=str(exc),
            )

        if entry is None:
            return GoogleDriveInstallationReport(
                state=GoogleDriveInstallState.NOT_INSTALLED,
                evidence=GOOGLE_DRIVE_UNINSTALL_SUBKEY,
            )

        evidence = GOOGLE_DRIVE_UNINSTALL_SUBKEY
        if entry.registry_view:
            evidence = f"{evidence} [{entry.registry_view}]"

        return GoogleDriveInstallationReport(
            state=GoogleDriveInstallState.INSTALLED,
            display_name=str(entry.display_name or "Google Drive for desktop"),
            display_version=str(entry.display_version or ""),
            install_location=str(entry.install_location or ""),
            evidence=evidence,
        )


def _probe_google_drive_registry() -> GoogleDriveRegistryEntry | None:
    """Probe Google's documented uninstall key in both Windows registry views."""

    import winreg

    access_modes = (
        ("64-bit", winreg.KEY_READ | winreg.KEY_WOW64_64KEY),
        ("32-bit", winreg.KEY_READ | winreg.KEY_WOW64_32KEY),
    )
    access_errors: list[OSError] = []

    for view_name, access in access_modes:
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                GOOGLE_DRIVE_UNINSTALL_SUBKEY,
                0,
                access,
            ) as key:
                return GoogleDriveRegistryEntry(
                    display_name=_query_registry_string(key, "DisplayName"),
                    display_version=_query_registry_string(key, "DisplayVersion"),
                    install_location=_query_registry_string(key, "InstallLocation"),
                    uninstall_string=_query_registry_string(key, "UninstallString"),
                    registry_view=view_name,
                )
        except FileNotFoundError:
            continue
        except OSError as exc:
            access_errors.append(exc)

    if access_errors:
        raise RuntimeError(
            "Google Drive installation registry could not be read: "
            + "; ".join(str(exc) for exc in access_errors)
        )

    return None


def _query_registry_string(key, value_name: str) -> str:
    import winreg

    try:
        value, _value_type = winreg.QueryValueEx(key, value_name)
    except FileNotFoundError:
        return ""
    return str(value or "").strip()
