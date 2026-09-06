from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from core.project_filename import new_project_destination
from core.project_settings import ProjectSettings


@dataclass(frozen=True)
class SetupValidationIssue:
    field: str
    message: str
    severity: str = "error"


@dataclass(frozen=True)
class ProjectDestinationValidation:
    parent_folder: Path | None
    destination_file: Path | None
    issues: tuple[SetupValidationIssue, ...]

    @property
    def is_valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)


def looks_like_browser_url(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    parsed = urlparse(text)
    return parsed.scheme.casefold() in {"http", "https"} and bool(parsed.netloc)


def validate_project_identity_destination(
    settings: ProjectSettings,
    parent_folder: str | Path,
    *,
    verify_writable: bool = False,
) -> ProjectDestinationValidation:
    normalized = settings.normalized()
    issues: list[SetupValidationIssue] = []

    for field_name, label in (
        ("project_name", "Nama Proyek"),
        ("project_code", "Kode Proyek"),
        ("client_name", "Klien"),
    ):
        if not str(getattr(normalized, field_name, "") or "").strip():
            issues.append(
                SetupValidationIssue(field_name, f"{label} wajib diisi.")
            )

    start_date = str(normalized.start_date or "").strip()
    if not start_date:
        issues.append(
            SetupValidationIssue("start_date", "Tanggal Mulai wajib diisi.")
        )
    else:
        try:
            date.fromisoformat(start_date)
        except ValueError:
            issues.append(
                SetupValidationIssue(
                    "start_date",
                    "Tanggal Mulai tidak valid.",
                )
            )

    raw_parent = str(parent_folder or "").strip()
    if not raw_parent:
        issues.append(
            SetupValidationIssue(
                "project_destination",
                "Lokasi penyimpanan proyek wajib dipilih.",
            )
        )
        return ProjectDestinationValidation(None, None, tuple(issues))

    if looks_like_browser_url(raw_parent):
        issues.append(
            SetupValidationIssue(
                "project_destination",
                "Lokasi proyek harus berupa folder filesystem, bukan URL browser.",
            )
        )
        return ProjectDestinationValidation(None, None, tuple(issues))

    parent = Path(raw_parent).expanduser()
    destination: Path | None = None
    if normalized.project_name.strip() and normalized.project_code.strip():
        destination = new_project_destination(
            parent,
            normalized.project_code,
            normalized.project_name,
        )

    if parent.exists():
        if not parent.is_dir():
            issues.append(
                SetupValidationIssue(
                    "project_destination",
                    "Lokasi penyimpanan proyek bukan folder.",
                )
            )
        elif not os.access(parent, os.W_OK):
            issues.append(
                SetupValidationIssue(
                    "project_destination",
                    "Folder penyimpanan proyek tidak dapat ditulis.",
                )
            )
        elif verify_writable:
            write_error = _probe_directory_write(parent)
            if write_error:
                issues.append(
                    SetupValidationIssue(
                        "project_destination",
                        f"Folder penyimpanan proyek tidak dapat ditulis: {write_error}",
                    )
                )
    else:
        nearest = _nearest_existing_parent(parent)
        if nearest is None or not nearest.is_dir() or not os.access(nearest, os.W_OK):
            issues.append(
                SetupValidationIssue(
                    "project_destination",
                    "Folder tujuan belum ada dan parent-nya tidak dapat ditulis.",
                )
            )
        else:
            issues.append(
                SetupValidationIssue(
                    "project_destination",
                    "Folder tujuan belum ada. Klik Buat Folder untuk membuatnya.",
                )
            )

    if destination is not None and destination.exists():
        issues.append(
            SetupValidationIssue(
                "project_file",
                f"File proyek sudah ada: {destination}",
            )
        )

    return ProjectDestinationValidation(parent, destination, tuple(issues))


def create_project_destination_folder(parent_folder: str | Path) -> Path:
    raw = str(parent_folder or "").strip()
    if not raw:
        raise ValueError("Lokasi penyimpanan proyek belum diisi.")
    if looks_like_browser_url(raw):
        raise ValueError("Lokasi proyek harus berupa folder filesystem, bukan URL browser.")

    path = Path(raw).expanduser()
    if path.exists() and not path.is_dir():
        raise ValueError("Lokasi penyimpanan proyek bukan folder.")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _nearest_existing_parent(path: Path) -> Path | None:
    candidate = path
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            return None
        candidate = parent
    return candidate


def _probe_directory_write(path: Path) -> str:
    probe_path: Path | None = None
    handle = None
    try:
        handle = tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=".script_manager_write_test_",
            dir=path,
            delete=False,
        )
        probe_path = Path(handle.name)
        handle.write(b"ok")
        handle.flush()
        os.fsync(handle.fileno())
    except OSError as exc:
        return str(exc)
    finally:
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
        if probe_path is not None:
            try:
                probe_path.unlink(missing_ok=True)
            except OSError:
                pass
    return ""
