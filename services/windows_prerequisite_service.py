from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable


GOOGLE_DRIVE_UNINSTALL_GUID = "{6BBAE539-2232-434A-A4E5-9A33560C6283}"
GOOGLE_DRIVE_UNINSTALL_SUBKEY = (
    "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\"
    + GOOGLE_DRIVE_UNINSTALL_GUID
)
GOOGLE_DRIVE_OFFICIAL_DOWNLOAD_URL = (
    "https://dl.google.com/drive-file-stream/GoogleDriveSetup.exe"
)
GOOGLE_DRIVE_HELP_URL = "https://support.google.com/drive/answer/10838124"
GOOGLE_DRIVE_PROCESS_NAME = "GoogleDriveFS.exe"
GOOGLE_DRIVE_VOLUME_LABEL = "Google Drive"


class GoogleDriveInstallState(str, Enum):
    UNSUPPORTED_SYSTEM = "UNSUPPORTED_SYSTEM"
    NOT_INSTALLED = "NOT_INSTALLED"
    INSTALLED = "INSTALLED"
    CHECK_ERROR = "CHECK_ERROR"


class GoogleDriveReadinessState(str, Enum):
    UNSUPPORTED_SYSTEM = "UNSUPPORTED_SYSTEM"
    NOT_INSTALLED = "NOT_INSTALLED"
    INSTALLED_NOT_RUNNING = "INSTALLED_NOT_RUNNING"
    RUNNING_NOT_READY = "RUNNING_NOT_READY"
    READY = "READY"
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


@dataclass(frozen=True)
class GoogleDriveReadinessReport:
    state: GoogleDriveReadinessState
    installation: GoogleDriveInstallationReport
    running: bool = False
    filesystem_ready: bool = False
    drive_roots: tuple[str, ...] = ()
    drivefs_data_dir: str = ""
    error: str = ""

    @property
    def installed(self) -> bool:
        return self.installation.installed

    @property
    def ready(self) -> bool:
        return self.state == GoogleDriveReadinessState.READY


RegistryProbe = Callable[[], GoogleDriveRegistryEntry | None]
ProcessProbe = Callable[[], bool]
FilesystemProbe = Callable[[], tuple[str, ...]]
DriveFsDataProbe = Callable[[], str]
DriveLauncher = Callable[[GoogleDriveInstallationReport], bool]


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


class GoogleDriveReadinessService:
    """Report whether an installed Google Drive is usable as a Windows filesystem.

    Installation, running state, and filesystem readiness are intentionally
    separate. Readiness never inspects Google credentials or account tokens.
    """

    def __init__(
        self,
        *,
        platform_name: str | None = None,
        installation_detector: GoogleDriveInstallationDetector | None = None,
        process_probe: ProcessProbe | None = None,
        filesystem_probe: FilesystemProbe | None = None,
        drivefs_data_probe: DriveFsDataProbe | None = None,
        launcher: DriveLauncher | None = None,
    ) -> None:
        self.platform_name = str(platform_name or sys.platform)
        self.installation_detector = installation_detector or (
            GoogleDriveInstallationDetector(platform_name=self.platform_name)
        )
        self.process_probe = process_probe or _is_google_drive_process_running
        self.filesystem_probe = filesystem_probe or _find_google_drive_roots
        self.drivefs_data_probe = drivefs_data_probe or _google_drivefs_data_dir
        self.launcher = launcher or _launch_google_drive

    def check(self) -> GoogleDriveReadinessReport:
        installation = self.installation_detector.detect()

        if installation.state == GoogleDriveInstallState.UNSUPPORTED_SYSTEM:
            return GoogleDriveReadinessReport(
                state=GoogleDriveReadinessState.UNSUPPORTED_SYSTEM,
                installation=installation,
            )

        if installation.state == GoogleDriveInstallState.NOT_INSTALLED:
            return GoogleDriveReadinessReport(
                state=GoogleDriveReadinessState.NOT_INSTALLED,
                installation=installation,
            )

        if installation.state == GoogleDriveInstallState.CHECK_ERROR:
            return GoogleDriveReadinessReport(
                state=GoogleDriveReadinessState.CHECK_ERROR,
                installation=installation,
                error=installation.error,
            )

        drivefs_data_dir = ""
        try:
            drivefs_data_dir = str(self.drivefs_data_probe() or "")
        except Exception:
            # This path is only supporting evidence. It does not determine
            # whether the Drive filesystem is ready for Script Manager.
            drivefs_data_dir = ""

        try:
            drive_roots = tuple(
                str(value)
                for value in self.filesystem_probe()
                if str(value).strip()
            )
        except Exception as exc:
            return GoogleDriveReadinessReport(
                state=GoogleDriveReadinessState.CHECK_ERROR,
                installation=installation,
                drivefs_data_dir=drivefs_data_dir,
                error=f"Google Drive filesystem check failed: {exc}",
            )

        if drive_roots:
            return GoogleDriveReadinessReport(
                state=GoogleDriveReadinessState.READY,
                installation=installation,
                running=True,
                filesystem_ready=True,
                drive_roots=drive_roots,
                drivefs_data_dir=drivefs_data_dir,
            )

        try:
            running = bool(self.process_probe())
        except Exception as exc:
            return GoogleDriveReadinessReport(
                state=GoogleDriveReadinessState.CHECK_ERROR,
                installation=installation,
                drivefs_data_dir=drivefs_data_dir,
                error=f"Google Drive process check failed: {exc}",
            )

        if running:
            state = GoogleDriveReadinessState.RUNNING_NOT_READY
        else:
            state = GoogleDriveReadinessState.INSTALLED_NOT_RUNNING

        return GoogleDriveReadinessReport(
            state=state,
            installation=installation,
            running=running,
            filesystem_ready=False,
            drivefs_data_dir=drivefs_data_dir,
        )

    def launch(self) -> bool:
        installation = self.installation_detector.detect()
        if not installation.installed:
            return False
        try:
            return bool(self.launcher(installation))
        except Exception:  # pragma: no cover - platform/backend boundary
            return False


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


def _is_google_drive_process_running() -> bool:
    if sys.platform != "win32":
        return False

    completed = subprocess.run(
        [
            "tasklist",
            "/FI",
            f"IMAGENAME eq {GOOGLE_DRIVE_PROCESS_NAME}",
            "/FO",
            "CSV",
            "/NH",
        ],
        capture_output=True,
        text=True,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        timeout=5,
    )
    output = f"{completed.stdout}\n{completed.stderr}".casefold()
    return GOOGLE_DRIVE_PROCESS_NAME.casefold() in output


def _find_google_drive_roots() -> tuple[str, ...]:
    """Return mounted Windows volumes whose label identifies Google Drive."""

    if sys.platform != "win32":
        return ()

    import ctypes

    kernel32 = ctypes.windll.kernel32
    required = kernel32.GetLogicalDriveStringsW(0, None)
    if required <= 0:
        return ()

    buffer = ctypes.create_unicode_buffer(required + 1)
    length = kernel32.GetLogicalDriveStringsW(required, buffer)
    if length <= 0:
        return ()

    roots: list[str] = []
    for root in buffer[:length].split("\x00"):
        root = str(root or "").strip()
        if not root:
            continue

        volume_name = ctypes.create_unicode_buffer(261)
        ok = kernel32.GetVolumeInformationW(
            root,
            volume_name,
            len(volume_name),
            None,
            None,
            None,
            None,
            0,
        )
        if not ok:
            continue

        if GOOGLE_DRIVE_VOLUME_LABEL.casefold() in volume_name.value.casefold():
            roots.append(root)

    return tuple(roots)


def _google_drivefs_data_dir() -> str:
    if sys.platform != "win32":
        return ""

    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if not local_app_data:
        return ""

    candidate = Path(local_app_data) / "Google" / "DriveFS"
    return str(candidate) if candidate.is_dir() else ""


def _launch_google_drive(installation: GoogleDriveInstallationReport) -> bool:
    if sys.platform != "win32":
        return False

    executable = _find_google_drive_executable(installation)
    if executable is None:
        return False

    subprocess.Popen(
        [str(executable)],
        cwd=str(executable.parent),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return True


def _find_google_drive_executable(
    installation: GoogleDriveInstallationReport,
) -> Path | None:
    candidates: list[Path] = []

    install_location = str(installation.install_location or "").strip()
    if install_location:
        location = Path(install_location)
        candidates.append(location / GOOGLE_DRIVE_PROCESS_NAME)
        if location.is_dir():
            candidates.extend(
                location.glob(f"*/{GOOGLE_DRIVE_PROCESS_NAME}")
            )

    for environment_name in ("ProgramFiles", "ProgramFiles(x86)"):
        base_text = os.environ.get(environment_name, "").strip()
        if not base_text:
            continue
        base = Path(base_text) / "Google" / "Drive File Stream"
        candidates.append(base / GOOGLE_DRIVE_PROCESS_NAME)
        if base.is_dir():
            candidates.extend(base.glob(f"*/{GOOGLE_DRIVE_PROCESS_NAME}"))

    existing = [path for path in candidates if path.is_file()]
    if not existing:
        return None

    return max(existing, key=lambda path: str(path.parent).casefold())
