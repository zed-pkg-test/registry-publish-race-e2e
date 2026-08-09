from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "organization": 'zed-pkg-test',
    "repository": 'registry-publish-race-e2e',
    "full_name": 'zed-pkg-test/registry-publish-race-e2e',
    "visibility": 'public',
    "lane": 'registry-concurrency',
    "tracking_issue": 'DEN-3286',
    "fleet_manifest_sha256": '5d1cf8cb7af82a81660bf2fe7536759c7b15bd01bef4a4a04730095ad998d056',
    "default_branch": "main",
}


class TestLaneBootstrap(unittest.TestCase):
    def test_machine_readable_identity(self) -> None:
        payload = json.loads((ROOT / "test-lane.json").read_text(encoding="utf-8"))
        for key, expected in EXPECTED.items():
            self.assertEqual(payload[key], expected, key)
        self.assertFalse(payload["force_push_allowed"])
        self.assertTrue(payload["semantic_conflict_resolution_required"])

    def test_readme_names_exact_target(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(EXPECTED["full_name"], readme)
        self.assertIn(EXPECTED["tracking_issue"], readme)

    def test_text_files_have_no_merge_markers(self) -> None:
        marker_pattern = re.compile(r"^(?:" + "<" * 7 + r"|" + "=" * 7 + r"|" + ">" * 7 + r")(?: |$)", re.MULTILINE)
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if path.stat().st_size > 1_000_000:
                continue
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(marker_pattern.search(text), str(path.relative_to(ROOT)))


if __name__ == "__main__":
    unittest.main()
