from __future__ import annotations

from dataclasses import dataclass

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
    def is_valid(self) -> bool:
        return not self.errors


def validate_folder_links_setup(
    settings: ProjectSettings,
) -> FolderLinksSetupValidation:
    """Validate the wizard Folder & Links milestone without network access.

    Operational folders were deeply validated in milestones 2 and 3. This gate
    keeps the filesystem-vs-browser distinction explicit and validates only the
    syntax of optional browser links; it never performs an HTTP request.
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
