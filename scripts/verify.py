#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
metadata_path = ROOT / "test-lane.json"
metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
required = {
    "schema_version",
    "organization",
    "repository",
    "full_name",
    "visibility",
    "lane",
    "description",
    "tracking_issue",
    "bootstrap_date",
    "fleet_manifest_sha256",
    "default_branch",
}
missing = sorted(required - metadata.keys())
if missing:
    raise SystemExit(f"missing test-lane fields: {missing}")
if metadata["full_name"] != f"{metadata['organization']}/{metadata['repository']}":
    raise SystemExit("test-lane identity is inconsistent")
if metadata["visibility"] not in {"public", "private"}:
    raise SystemExit("test-lane visibility is invalid")
result = subprocess.run(
    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
    cwd=ROOT,
    check=False,
)
raise SystemExit(result.returncode)
