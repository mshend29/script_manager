from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from core.project_settings import ProjectSettings
from services.audio_setup_validation import validate_audio_setup
from services.folder_links_setup_validation import (
    validate_operational_folder_relationships,
)
from services.project_setup_validation import SetupValidationIssue, looks_like_browser_url
from services.source_setup_validation import validate_source_filenames


SOURCE_FIELDS = (
    "source_folder",
    "episode_before",
    "episode_after",
)
TRACKING_FIELDS = (
    "stem_output_folder",
    "delivery_folder",
    "audio_format",
    "audio_sample_rate",
    "audio_bit_depth",
    "audio_channels",
)
LINK_FIELDS = (
    "main_drive_url",
    "material_drive_url",
    "delivery_drive_url",
)
IDENTITY_FIELDS = (
    "project_name",
    "project_code",
    "client_name",
    "start_date",
)


@dataclass(frozen=True)
class ProjectSettingsChangeValidation:
    issues: tuple[SetupValidationIssue, ...]
    source_changed: bool
    tracking_changed: bool
    links_changed: bool

    @property
    def errors(self) -> tuple[SetupValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[SetupValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def is_valid(self) -> bool:
        return not self.errors


def settings_change_flags(
    baseline: ProjectSettings,
    candidate: ProjectSettings,
) -> tuple[bool, bool, bool]:
    old = baseline.normalized()
    new = candidate.normalized()
    return (
        _group_changed(old, new, SOURCE_FIELDS),
        _group_changed(old, new, TRACKING_FIELDS),
        _group_changed(old, new, LINK_FIELDS),
    )


def validate_existing_project_settings_change(
    baseline: ProjectSettings,
    candidate: ProjectSettings,
    *,
    verify_writable: bool = False,
) -> ProjectSettingsChangeValidation:
    """Validate edits without making an existing project fragile when drives are offline.

    Values that are unchanged from the persisted project are treated as legacy/existing
    configuration. If an existing filesystem location is temporarily unavailable, it
    produces a warning instead of preventing Save. A field that the user changes is
    validated as new configuration and errors block Save.
    """

    old = baseline.normalized()
    new = candidate.normalized()
    source_changed, tracking_changed, links_changed = settings_change_flags(old, new)
    issues: list[SetupValidationIssue] = []

    _validate_identity(old, new, issues)

    if source_changed:
        source_validation = validate_source_filenames(
            new.source_folder,
            episode_before=new.episode_before,
            episode_after=new.episode_after,
        )
        issues.extend(source_validation.issues)
    else:
        _warn_existing_folder(
            "source_folder",
            "Folder Sumber",
            new.source_folder,
            issues,
            require_writable=False,
        )

    audio_validation = validate_audio_setup(
        new,
        verify_writable=verify_writable,
    )
    for issue in audio_validation.issues:
        changed = _field_value(old, issue.field) != _field_value(new, issue.field)
        if changed:
            issues.append(issue)
        else:
            issues.append(
                SetupValidationIssue(
                    issue.field,
                    _existing_warning_message(issue.message),
                    severity="warning",
                )
            )

    _validate_folder_relationships(old, new, issues)
    _validate_links(old, new, issues)

    return ProjectSettingsChangeValidation(
        issues=_deduplicate_issues(issues),
        source_changed=source_changed,
        tracking_changed=tracking_changed,
        links_changed=links_changed,
    )


def _validate_identity(
    old: ProjectSettings,
    new: ProjectSettings,
    issues: list[SetupValidationIssue],
) -> None:
    labels = {
        "project_name": "Nama Proyek",
        "project_code": "Kode Proyek",
        "client_name": "Klien",
        "start_date": "Tanggal Mulai",
    }
    for field in IDENTITY_FIELDS:
        value = str(getattr(new, field, "") or "").strip()
        if value:
            continue
        changed = _field_value(old, field) != _field_value(new, field)
        issues.append(
            SetupValidationIssue(
                field,
                (
                    f"{labels[field]} wajib diisi."
                    if changed
                    else f"{labels[field]} pada project existing masih kosong."
                ),
                severity="error" if changed else "warning",
            )
        )

    start_value = str(new.start_date or "").strip()
    if start_value:
        try:
            date.fromisoformat(start_value)
        except ValueError:
            changed = _field_value(old, "start_date") != _field_value(new, "start_date")
            issues.append(
                SetupValidationIssue(
                    "start_date",
                    (
                        "Tanggal Mulai tidak valid."
                        if changed
                        else "Tanggal Mulai existing tidak valid."
                    ),
                    severity="error" if changed else "warning",
                )
            )


def _warn_existing_folder(
    field: str,
    label: str,
    raw_value: str,
    issues: list[SetupValidationIssue],
    *,
    require_writable: bool,
) -> None:
    raw = str(raw_value or "").strip()
    if not raw:
        issues.append(
            SetupValidationIssue(
                field,
                f"{label} belum dikonfigurasi pada project existing.",
                severity="warning",
            )
        )
        return
    if looks_like_browser_url(raw):
        issues.append(
            SetupValidationIssue(
                field,
                f"{label} existing berisi URL, bukan filesystem path.",
                severity="warning",
            )
        )
        return

    path = Path(raw).expanduser()
    if not path.exists():
        issues.append(
            SetupValidationIssue(
                field,
                f"{label} existing sedang tidak tersedia: {path}",
                severity="warning",
            )
        )
        return
    if not path.is_dir():
        issues.append(
            SetupValidationIssue(
                field,
                f"{label} existing bukan folder: {path}",
                severity="warning",
            )
        )
        return
    if not os.access(path, os.R_OK):
        issues.append(
            SetupValidationIssue(
                field,
                f"{label} existing saat ini tidak dapat dibaca.",
                severity="warning",
            )
        )
    if require_writable and not os.access(path, os.W_OK):
        issues.append(
            SetupValidationIssue(
                field,
                f"{label} existing saat ini tidak dapat ditulis.",
                severity="warning",
            )
        )


def _validate_folder_relationships(
    old: ProjectSettings,
    new: ProjectSettings,
    issues: list[SetupValidationIssue],
) -> None:
    old_issues = {
        (issue.field, issue.message)
        for issue in validate_operational_folder_relationships(old)
    }

    for issue in validate_operational_folder_relationships(new):
        if issue.severity == "warning":
            issues.append(issue)
            continue

        if (issue.field, issue.message) in old_issues:
            issues.append(
                SetupValidationIssue(
                    issue.field,
                    _existing_warning_message(issue.message),
                    severity="warning",
                )
            )
        else:
            issues.append(issue)


def _validate_links(
    old: ProjectSettings,
    new: ProjectSettings,
    issues: list[SetupValidationIssue],
) -> None:
    labels = {
        "main_drive_url": "Drive Utama",
        "material_drive_url": "Material",
        "delivery_drive_url": "Setoran",
    }
    for field in LINK_FIELDS:
        value = str(getattr(new, field, "") or "").strip()
        if not value:
            continue
        if looks_like_browser_url(value):
            continue
        changed = _field_value(old, field) != _field_value(new, field)
        issues.append(
            SetupValidationIssue(
                field,
                (
                    f"{labels[field]} harus berupa URL http/https yang valid atau dikosongkan."
                    if changed
                    else f"{labels[field]} existing bukan URL http/https yang valid."
                ),
                severity="error" if changed else "warning",
            )
        )


def _existing_warning_message(message: str) -> str:
    text = str(message or "").strip()
    if not text:
        return "Konfigurasi existing sedang tidak tersedia."
    return "Konfigurasi existing: " + text


def _group_changed(
    old: ProjectSettings,
    new: ProjectSettings,
    fields: tuple[str, ...],
) -> bool:
    return any(_field_value(old, field) != _field_value(new, field) for field in fields)


def _field_value(settings: ProjectSettings, field: str) -> object:
    value = getattr(settings, field, "")
    return value.strip() if isinstance(value, str) else value


def _deduplicate_issues(
    issues: list[SetupValidationIssue],
) -> tuple[SetupValidationIssue, ...]:
    seen: set[tuple[str, str, str]] = set()
    ordered: list[SetupValidationIssue] = []
    for issue in issues:
        key = (issue.field, issue.message, issue.severity)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(issue)
    return tuple(ordered)
