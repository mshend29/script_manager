from __future__ import annotations

import hashlib
from pathlib import Path

CHUNK_SIZE = 1024 * 1024


def calculate_file_fingerprint(
    path: str | Path,
) -> str:
    """
    Menghasilkan SHA-256 berdasarkan isi file.

    Dengan fingerprint ini aplikasi dapat mengetahui
    apakah file Excel benar-benar berubah.
    """

    file_path = Path(path)

    digest = hashlib.sha256()

    with file_path.open("rb") as handle:
        while chunk := handle.read(CHUNK_SIZE):
            digest.update(chunk)

    return digest.hexdigest()
