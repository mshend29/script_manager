from __future__ import annotations

from services.windows_prerequisite_service import (
    GOOGLE_DRIVE_OFFICIAL_DOWNLOAD_URL,
    GOOGLE_DRIVE_UNINSTALL_GUID,
    GOOGLE_DRIVE_UNINSTALL_SUBKEY,
    GoogleDriveInstallationDetector,
    GoogleDriveInstallState,
    GoogleDriveRegistryEntry,
)


def test_non_windows_is_safe_and_does_not_probe_registry() -> None:
    called = False

    def probe():
        nonlocal called
        called = True
        raise AssertionError("registry probe must not run")

    report = GoogleDriveInstallationDetector(
        platform_name="linux",
        registry_probe=probe,
    ).detect()

    assert report.state == GoogleDriveInstallState.UNSUPPORTED_SYSTEM
    assert called is False


def test_missing_documented_uninstall_key_means_not_installed() -> None:
    report = GoogleDriveInstallationDetector(
        platform_name="win32",
        registry_probe=lambda: None,
    ).detect()

    assert report.state == GoogleDriveInstallState.NOT_INSTALLED
    assert report.installed is False
    assert GOOGLE_DRIVE_UNINSTALL_GUID in report.evidence


def test_documented_uninstall_key_presence_means_installed() -> None:
    report = GoogleDriveInstallationDetector(
        platform_name="win32",
        registry_probe=lambda: GoogleDriveRegistryEntry(
            display_name="Google Drive",
            display_version="99.0.0.0",
            install_location=r"C:\Program Files\Google\Drive File Stream",
            registry_view="64-bit",
        ),
    ).detect()

    assert report.state == GoogleDriveInstallState.INSTALLED
    assert report.installed is True
    assert report.display_name == "Google Drive"
    assert report.display_version == "99.0.0.0"
    assert report.install_location.endswith("Drive File Stream")
    assert "64-bit" in report.evidence


def test_partial_registry_entry_is_safe_installed_evidence() -> None:
    report = GoogleDriveInstallationDetector(
        platform_name="win32",
        registry_probe=lambda: GoogleDriveRegistryEntry(registry_view="64-bit"),
    ).detect()

    assert report.state == GoogleDriveInstallState.INSTALLED
    assert report.display_name == "Google Drive for desktop"


def test_registry_probe_error_is_reported_without_crashing() -> None:
    def probe():
        raise PermissionError("registry denied")

    report = GoogleDriveInstallationDetector(
        platform_name="win32",
        registry_probe=probe,
    ).detect()

    assert report.state == GoogleDriveInstallState.CHECK_ERROR
    assert "registry denied" in report.error


def test_contract_never_assumes_fixed_google_drive_letter() -> None:
    contract_text = " ".join(
        (
            GOOGLE_DRIVE_UNINSTALL_SUBKEY,
            GOOGLE_DRIVE_OFFICIAL_DOWNLOAD_URL,
        )
    )

    assert "G:\\" not in contract_text
    assert "G:/" not in contract_text


def test_official_google_download_endpoint_is_locked() -> None:
    assert GOOGLE_DRIVE_OFFICIAL_DOWNLOAD_URL == (
        "https://dl.google.com/drive-file-stream/GoogleDriveSetup.exe"
    )
