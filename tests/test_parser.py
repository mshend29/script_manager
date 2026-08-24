from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from import_engine.parser import ScriptParser


class ScriptParserTests(unittest.TestCase):
    def _save_workbook(self, workbook: Workbook) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        path = Path(temp_dir.name) / "episode.xlsx"
        workbook.save(path)
        return path

    def test_detects_header_and_parses_multi_cast(self) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "SCRIPT"

        sheet.append(["Catatan"])
        sheet.append(["IN", "OUT", "DIALOG", "TOKOH", "TALENT"])
        sheet.append(
            [
                "00:00:01,000",
                "00:00:02,000",
                "Kita pergi sekarang",
                "-Indah -Teguh",
                "Anisa - Brama",
            ]
        )
        sheet.append(
            [
                "00:00:03,000",
                "00:00:04,000",
                "Baik",
                "Bima",
                "Dika",
            ]
        )

        result = ScriptParser().parse(
            self._save_workbook(workbook),
            episode_number=7,
        )

        self.assertEqual(result.layout.detection, "header")
        self.assertEqual(result.dialogue_count, 2)

        first = result.rows[0]
        self.assertEqual(first.characters, ("Indah", "Teguh"))
        self.assertEqual(first.talents, ("Anisa", "Brama"))
        self.assertEqual(len(first.cast_pairs), 2)
        self.assertEqual(first.status, "OK")

    def test_legacy_a_to_e_fallback_requires_script_like_rows(self) -> None:
        workbook = Workbook()
        sheet = workbook.active

        sheet.append(["Judul Episode"])
        sheet.append(["Mulai", "Selesai", "Teks Lokal", "Pemeran", "Pengisi"])
        sheet.append(
            [
                "00:00:01,000",
                "00:00:02,000",
                "Halo",
                "Bima",
                "Dika",
            ]
        )
        sheet.append(
            [
                "00:00:02,100",
                "00:00:03,000",
                "Apa kabar",
                "Bima",
                "Dika",
            ]
        )

        result = ScriptParser().parse(
            self._save_workbook(workbook),
            episode_number=8,
        )

        self.assertEqual(result.layout.detection, "legacy-a-e")
        self.assertEqual(result.dialogue_count, 2)

    def test_cast_count_mismatch_is_not_guessed(self) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["IN", "OUT", "DIALOG", "TOKOH", "TALENT"])
        sheet.append(
            [
                "00:00:01,000",
                "00:00:02,000",
                "Bersama",
                "Hendra - Joko",
                "Brama",
            ]
        )

        result = ScriptParser().parse(
            self._save_workbook(workbook),
            episode_number=9,
        )

        row = result.rows[0]
        self.assertIn("CAST_COUNT_MISMATCH", row.status)
        self.assertEqual(row.cast_pairs, ())
        self.assertTrue(result.warnings)


if __name__ == "__main__":
    unittest.main()
