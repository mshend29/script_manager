from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from core.project_settings import ProjectSettings
from services.project_setup_validation import (
    SetupValidationIssue,
    looks_like_browser_url,
)


@dataclass(frozen=True)
class FolderLinksSetupValidation:
    issues: tuple[SetupValidationIssue, ...]

    @property
    def errors(self) -> tuple[SetupValidationIssue, ...]:
        return tuple(
            issue for issue in self.issues if issue.severity == "error"
        )

    @property
    def warnings(self) -> tuple[SetupValidationIssue, ...]:
        return tuple(
            issue for issue in self.issues if issue.severity == "warning"
        )

    @property
    def is_valid(self) -> bool:
        return not self.errors


def validate_folder_links_setup(
    settings: ProjectSettings,
) -> FolderLinksSetupValidation:
    """Validate the wizard Folder & Links milestone without network access.

    Operational folders were deeply validated in milestones 2 and 3. This gate
    keeps the filesystem-vs-browser distinction explicit, validates optional
    browser-link syntax, and prevents ambiguous source/output folder overlap.
    It never performs an HTTP request.
    """
    issues: list[SetupValidationIssue] = []

    for field, label in (
        ("source_folder", "Folder Naskah"),
        ("stem_output_folder", "Folder Stem"),
        ("delivery_folder", "Folder Setoran"),
    ):
        value = str(getattr(settings, field, "") or "").strip()
        if not value:
            issues.append(
                SetupValidationIssue(
                    field,
                    f"{label} belum dikonfigurasi.",
                )
            )
        elif looks_like_browser_url(value):
            issues.append(
                SetupValidationIssue(
                    field,
                    f"{label} harus berupa filesystem path, bukan URL browser.",
                )
            )

    issues.extend(validate_operational_folder_relationships(settings))

    for field, label in (
        ("main_drive_url", "Drive Utama"),
        ("material_drive_url", "Material"),
        ("delivery_drive_url", "Setoran"),
    ):
        value = str(getattr(settings, field, "") or "").strip()
        if value and not looks_like_browser_url(value):
            issues.append(
                SetupValidationIssue(
                    field,
                    f"{label} harus berupa URL http/https yang valid atau dikosongkan.",
                )
            )

    return FolderLinksSetupValidation(tuple(issues))


def validate_operational_folder_relationships(
    settings: ProjectSettings,
) -> tuple[SetupValidationIssue, ...]:
    """Return safety issues for relationships between operational folders.

    Source must stay separate from generated audio/output folders so production
    files can never be mistaken for script source. Stem and Setoran may point to
    the same folder for a legacy/simplified workflow, but the ambiguity is made
    explicit as a warning.
    """
    source = _folder_key(settings.source_folder)
    stem = _folder_key(settings.stem_output_folder)
    delivery = _folder_key(settings.delivery_folder)
    issues: list[SetupValidationIssue] = []

    if source and stem and source == stem:
        issues.append(
            SetupValidationIssue(
                "stem_output_folder",
                "Folder Stem tidak boleh sama dengan Folder Sumber Naskah.",
            )
        )

    if source and delivery and source == delivery:
        issues.append(
            SetupValidationIssue(
                "delivery_folder",
                "Folder Setoran tidak boleh sama dengan Folder Sumber Naskah.",
            )
        )

    if stem and delivery and stem == delivery:
        issues.append(
            SetupValidationIssue(
                "delivery_folder",
                (
                    "Folder Stem dan Folder Setoran sama. Ini diperbolehkan, "
                    "tetapi file export dan setoran dapat tercampur."
                ),
                severity="warning",
            )
        )

    return tuple(issues)


def _folder_key(value: str) -> str:
    raw = str(value or "").strip()
    if not raw or looks_like_browser_url(raw):
        return ""

    try:
        resolved = Path(raw).expanduser().resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        resolved = Path(raw).expanduser()
    return os.path.normcase(str(resolved))
