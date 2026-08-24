from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


class EpisodeExtractionError(ValueError):
    pass


@dataclass(frozen=True)
class EpisodeExtractionResult:
    episode_number: int
    raw_value: str


def extract_episode_number(
    file_name: str,
    before: str = "",
    after: str = "",
) -> EpisodeExtractionResult:
    """
    Ekstrak nomor episode dari nama file berdasarkan delimiter project.

    Contoh:
        file_name = "AA23_EP001_SCRIPT.xlsx"
        before = "EP"
        after = "_"

        hasil:
        episode_number = 1
        raw_value = "001"

    Jika delimiter kosong semua,
    angka pertama pada nama file akan digunakan.
    """

    stem = Path(file_name).stem.strip()

    if not stem:
        raise EpisodeExtractionError("Nama file kosong.")

    start = 0

    # ---------------------------------
    # DELIMITER SEBELUM NOMOR EPISODE
    # ---------------------------------

    if before:
        before_index = stem.find(before)

        if before_index < 0:
            raise EpisodeExtractionError(f'Delimiter awal "{before}" tidak ditemukan.')

        start = before_index + len(before)

    # ---------------------------------
    # DELIMITER SESUDAH NOMOR EPISODE
    # ---------------------------------

    if after:
        end = stem.find(
            after,
            start,
        )

        if end < 0:
            raise EpisodeExtractionError(f'Delimiter akhir "{after}" tidak ditemukan.')

        candidate = stem[start:end].strip()

    else:
        # Kalau delimiter akhir kosong,
        # cari angka pertama setelah delimiter awal.

        remainder = stem[start:]

        match = re.search(
            r"\d+",
            remainder,
        )

        candidate = match.group(0) if match else ""

    # ---------------------------------
    # VALIDASI
    # ---------------------------------

    if not candidate:
        raise EpisodeExtractionError("Nomor episode tidak ditemukan.")

    if not re.fullmatch(
        r"\d+",
        candidate,
    ):
        raise EpisodeExtractionError(
            f'Hasil ekstraksi "{candidate}" bukan nomor episode.'
        )

    episode_number = int(candidate)

    if episode_number < 1:
        raise EpisodeExtractionError("Nomor episode harus lebih besar dari 0.")

    return EpisodeExtractionResult(
        episode_number=episode_number,
        raw_value=candidate,
    )
