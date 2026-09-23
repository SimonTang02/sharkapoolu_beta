from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from application_bot.artifacts import capture_long_page, save_fill_test_artifact


class FakePage:
    url = "https://example.test/application"

    def screenshot(self, *, path: str, full_page: bool) -> None:
        Path(path).write_bytes(b"private screenshot")

    def title(self) -> str:
        return "Review"


class FillTestArtifactTests(unittest.TestCase):
    def test_artifacts_are_append_only_and_do_not_store_field_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            first = save_fill_test_artifact(
                FakePage(), output, adapter="workday", stage="Review", status="draft_saved"
            )
            second = save_fill_test_artifact(
                FakePage(), output, adapter="workday", stage="Review", status="draft_saved"
            )
            self.assertNotEqual(first["screenshot_path"], second["screenshot_path"])
            lines = (output / "fill_tests/index.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            record = json.loads(lines[0])
            self.assertFalse(record["submit_clicked"])
            self.assertNotIn("fields", record)
            self.assertEqual(record["screenshot_paths"], [record["screenshot_path"]])
            self.assertEqual(record["capture"]["mode"], "full_page")

    def test_long_capture_keeps_legacy_page_doubles_working(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "long.png"
            result = capture_long_page(FakePage(), path)
            self.assertEqual(result["screenshot_paths"], [str(path)])
            self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
