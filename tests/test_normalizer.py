from __future__ import annotations

import unittest

from import_engine.normalizer import (
    normalize_key,
    normalize_timecode,
    split_cast_value,
)
from import_engine.parser import build_dialog_uid


class NormalizerTests(unittest.TestCase):
    def test_leading_dash_is_not_part_of_character_key(self) -> None:
        self.assertEqual(normalize_key("-Hendra"), "hendra")
        self.assertEqual(normalize_key("HENDRA"), "hendra")

    def test_square_bracket_wrapper_is_decoration_for_names(self) -> None:
        self.assertEqual(normalize_key("[Crowded]"), "crowded")
        self.assertEqual(normalize_key("Crowded"), "crowded")
        self.assertEqual(
            normalize_key("[Crowded Anak kecil]"),
            normalize_key("Crowded Anak kecil"),
        )

    def test_split_writer_dash_variants(self) -> None:
        self.assertEqual(
            split_cast_value("-Indah -Teguh"),
            ["Indah", "Teguh"],
        )
        self.assertEqual(
            split_cast_value("Hendra - Joko"),
            ["Hendra", "Joko"],
        )

    def test_split_real_source_dash_comma_variant(self) -> None:
        self.assertEqual(
            split_cast_value("-Bima, \n-Indah"),
            ["Bima", "Indah"],
        )

    def test_ampersand_is_supported_when_used_as_separator(self) -> None:
        self.assertEqual(
            split_cast_value("ibu baju hitam &\nibu baju biru"),
            ["ibu baju hitam", "ibu baju biru"],
        )
        self.assertEqual(
            split_cast_value("Vega & Brama"),
            ["Vega", "Brama"],
        )

    def test_duplicate_cast_values_are_preserved_for_position_pairing(self) -> None:
        self.assertEqual(
            split_cast_value("- Vega\n- Vega"),
            ["Vega", "Vega"],
        )

    def test_internal_hyphen_is_preserved(self) -> None:
        self.assertEqual(
            split_cast_value("Bapak berjas-dasi"),
            ["Bapak berjas-dasi"],
        )

    def test_timecode_separator_is_normalized(self) -> None:
        self.assertEqual(
            normalize_timecode("00:01:02.5"),
            "00:01:02,500",
        )

    def test_trailing_timecode_separator_is_zero_filled(self) -> None:
        self.assertEqual(
            normalize_timecode("00:00:10,"),
            "00:00:10,000",
        )
        self.assertEqual(
            normalize_timecode("00:00:11."),
            "00:00:11,000",
        )

    def test_dialog_uid_ignores_character_case_and_order(self) -> None:
        first = build_dialog_uid(
            episode_number=3,
            characters=("Hendra", "Joko"),
            talents=("Brama", "Dika"),
            time_in="00:00:01,000",
            time_out="00:00:02,000",
            dialogue="Kita harus pergi",
        )
        second = build_dialog_uid(
            episode_number=3,
            characters=("joko", "-HENDRA"),
            talents=("Dika", "Brama"),
            time_in="00:00:01.000",
            time_out="00:00:02.000",
            dialogue="  KITA   harus\npergi ",
        )

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
