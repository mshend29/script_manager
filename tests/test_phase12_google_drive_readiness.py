from __future__ import annotations

from services.windows_prerequisite_service import (
    GoogleDriveInstallationDetector,
    GoogleDriveInstallState,
    GoogleDriveReadinessService,
    GoogleDriveReadinessState,
    GoogleDriveRegistryEntry,
)


def _installed_detector() -> GoogleDriveInstallationDetector:
    return GoogleDriveInstallationDetector(
        platform_name="win32",
        registry_probe=lambda: GoogleDriveRegistryEntry(
            display_name="Google Drive",
            display_version="99.0",
            install_location=r"C:\Program Files\Google\Drive File Stream",
            registry_view="64-bit",
        ),
    )


def test_not_installed_maps_to_readiness_without_other_probes() -> None:
    process_called = False
    filesystem_called = False

    def process_probe() -> bool:
        nonlocal process_called
        process_called = True
        return False

    def filesystem_probe() -> tuple[str, ...]:
        nonlocal filesystem_called
        filesystem_called = True
        return ()

    service = GoogleDriveReadinessService(
        platform_name="win32",
        installation_detector=GoogleDriveInstallationDetector(
            platform_name="win32",
            registry_probe=lambda: None,
        ),
        process_probe=process_probe,
        filesystem_probe=filesystem_probe,
        drivefs_data_probe=lambda: "",
    )

    report = service.check()

    assert report.state == GoogleDriveReadinessState.NOT_INSTALLED
    assert report.installation.state == GoogleDriveInstallState.NOT_INSTALLED
    assert process_called is False
    assert filesystem_called is False


def test_installed_but_not_running_is_distinct_state() -> None:
    report = GoogleDriveReadinessService(
        platform_name="win32",
        installation_detector=_installed_detector(),
        process_probe=lambda: False,
        filesystem_probe=lambda: (),
        drivefs_data_probe=lambda: r"C:\Users\User\AppData\Local\Google\DriveFS",
    ).check()

    assert report.state == GoogleDriveReadinessState.INSTALLED_NOT_RUNNING
    assert report.installed is True
    assert report.running is False
    assert report.filesystem_ready is False
    assert report.drivefs_data_dir.endswith("DriveFS")


def test_running_but_no_mounted_filesystem_is_not_ready() -> None:
    report = GoogleDriveReadinessService(
        platform_name="win32",
        installation_detector=_installed_detector(),
        process_probe=lambda: True,
        filesystem_probe=lambda: (),
        drivefs_data_probe=lambda: "",
    ).check()

    assert report.state == GoogleDriveReadinessState.RUNNING_NOT_READY
    assert report.running is True
    assert report.ready is False


def test_mounted_google_drive_volume_means_ready_without_fixed_drive_letter() -> None:
    process_called = False

    def process_probe() -> bool:
        nonlocal process_called
        process_called = True
        return False

    report = GoogleDriveReadinessService(
        platform_name="win32",
        installation_detector=_installed_detector(),
        process_probe=process_probe,
        filesystem_probe=lambda: ("R:\\",),
        drivefs_data_probe=lambda: "",
    ).check()

    assert report.state == GoogleDriveReadinessState.READY
    assert report.ready is True
    assert report.filesystem_ready is True
    assert report.drive_roots == ("R:\\",)
    assert process_called is False
    assert "G:\\" not in " ".join(report.drive_roots)


def test_filesystem_probe_failure_is_diagnostic_not_crash() -> None:
    def filesystem_probe() -> tuple[str, ...]:
        raise PermissionError("volume query denied")

    report = GoogleDriveReadinessService(
        platform_name="win32",
        installation_detector=_installed_detector(),
        process_probe=lambda: False,
        filesystem_probe=filesystem_probe,
        drivefs_data_probe=lambda: "",
    ).check()

    assert report.state == GoogleDriveReadinessState.CHECK_ERROR
    assert "volume query denied" in report.error


def test_process_probe_failure_is_diagnostic_not_crash() -> None:
    def process_probe() -> bool:
        raise RuntimeError("tasklist unavailable")

    report = GoogleDriveReadinessService(
        platform_name="win32",
        installation_detector=_installed_detector(),
        process_probe=process_probe,
        filesystem_probe=lambda: (),
        drivefs_data_probe=lambda: "",
    ).check()

    assert report.state == GoogleDriveReadinessState.CHECK_ERROR
    assert "tasklist unavailable" in report.error


def test_launch_only_runs_when_google_drive_is_installed() -> None:
    launched: list[str] = []
    installed = GoogleDriveReadinessService(
        platform_name="win32",
        installation_detector=_installed_detector(),
        process_probe=lambda: False,
        filesystem_probe=lambda: (),
        drivefs_data_probe=lambda: "",
        launcher=lambda report: launched.append(report.display_name) or True,
    )
    missing = GoogleDriveReadinessService(
        platform_name="win32",
        installation_detector=GoogleDriveInstallationDetector(
            platform_name="win32",
            registry_probe=lambda: None,
        ),
        launcher=lambda report: launched.append("unexpected") or True,
    )

    assert installed.launch() is True
    assert launched == ["Google Drive"]
    assert missing.launch() is False
    assert launched == ["Google Drive"]
