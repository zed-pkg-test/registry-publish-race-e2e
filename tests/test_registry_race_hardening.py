from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.registry_atomicity_model import FileRegistry, ImmutableVersionConflict, IntegrityError, PackageKey, SimulatedCrash


class RegistryRaceHardeningTests(unittest.TestCase):
    def test_competing_publishers_choose_one_immutable_winner(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            registry = FileRegistry(Path(raw) / "registry")
            key = PackageKey("acme", "widget", "9.9.9")
            payloads = [b"payload-a", b"payload-b"] * 16

            def publish(payload: bytes):
                try:
                    return ("ok", registry.publish(key, payload), payload)
                except ImmutableVersionConflict:
                    return ("conflict", None, payload)

            with ThreadPoolExecutor(max_workers=16) as pool:
                outcomes = list(pool.map(publish, payloads))

            winners = [item for item in outcomes if item[0] == "ok"]
            conflicts = [item for item in outcomes if item[0] == "conflict"]
            self.assertTrue(winners)
            self.assertTrue(conflicts)
            winner_payloads = {item[2] for item in winners}
            self.assertEqual(len(winner_payloads), 1)
            winner = next(iter(winner_payloads))
            self.assertEqual(registry.resolve(key), winner)
            self.assertEqual(registry.orphaned_blobs(), [])
            self.assertEqual(len(list((registry.root / "metadata").rglob("*.json"))), 1)

    def test_crash_race_followed_by_retry_does_not_publish_stale_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            registry = FileRegistry(Path(raw) / "registry")
            key = PackageKey("acme", "widget", "2.0.0")
            with self.assertRaises(SimulatedCrash):
                registry.publish(key, b"winner-bytes", crash_after_blob=True)
            self.assertEqual(len(registry.orphaned_blobs()), 1)

            registry.publish(key, b"winner-bytes")
            self.assertEqual(registry.resolve(key), b"winner-bytes")
            self.assertEqual(registry.orphaned_blobs(), [])
            with self.assertRaises(ImmutableVersionConflict):
                registry.publish(key, b"stale-competitor")
            self.assertEqual(registry.resolve(key), b"winner-bytes")

    def test_metadata_missing_or_corrupt_blob_fails_closed_after_snapshot_restore(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            live = FileRegistry(root / "live")
            key = PackageKey("acme", "widget", "3.0.0")
            live.publish(key, b"verified-payload")
            snapshot = root / "snapshot"
            live.snapshot_to(snapshot)

            restored = FileRegistry.restore_from(snapshot, root / "restored")
            digest = next(iter(restored.referenced_digests()))
            (restored.blobs / digest).unlink()
            with self.assertRaises(IntegrityError):
                restored.resolve(key)


if __name__ == "__main__":
    unittest.main()
